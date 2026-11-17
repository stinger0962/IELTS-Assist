#!/usr/bin/env python3
"""Build a local, secret-free staging bundle from one exact Git commit.

Does not provision or launch anything. Requires git, Python 3, Node and npm.
Npm downloads locked public dependencies; no application/provider call occurs.
"""
import argparse
import gzip
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import tarfile
import tempfile

FRONTEND_FILES = {"frontend/index.html", "frontend/package.json", "frontend/package-lock.json",
                  "frontend/vite.config.ts", "frontend/tsconfig.json",
                  "frontend/tsconfig.app.json", "frontend/tsconfig.node.json"}
INSTRUCTIONS = """# Local staging bundle (not deployed)

This archive contains backend Python source and built frontend static assets.
No database, accounts, media inventory, TLS, gate, credentials or dependencies
are included. Build-manifest.json records the exact source revision and file
hashes; it does not prove operational readiness or infrastructure isolation.

Before running anything, follow the included staging runbook and obtain approval
for the isolated runtime, disposable PostgreSQL, HTTPS origin and access gate.
Install backend/requirements.txt in a new environment. Inject approved staging
configuration via the runtime's secret mechanism. From backend/, use only:

    uvicorn app.staging:create_app --factory --host 127.0.0.1 --port 8001

Do not substitute app.main:app or modify production's entry point. The staging
factory must validate before schema initialization. Do not start against an
unverified database. No credentials are generated or included by this bundle.

Serve frontend/ static files and route /api to the guarded backend on the same
approved origin. The frontend is built with VITE_API_URL=/api. SPA fallback must
handle /checkout/return and /checkout/cancel, not swallow API requests. An approved
edge must gate UI/API/media with only the canonical webhook POST exception in
the runbook; this archive intentionally contains no unverified proxy/gate config.
Do not expose the backend directly. Review HTTPS, access control, media mapping,
synthetic fixture seeding and browser behavior separately before Stripe testing.
"""


def selected(path):
    """Explicit source allowlist. No working-tree files or arbitrary backend data."""
    if PurePosixPath(path).is_absolute():
        return False
    parts = PurePosixPath(path).parts
    if any(p in {"..", ".", "__tests__", "fixtures"} or p.startswith(".") for p in parts):
        return False
    return (path in FRONTEND_FILES or path == "backend/requirements.txt"
            or path == "docs/qa/dashboard-only-sandbox-staging.md"
            or (path.startswith("backend/app/") and path.endswith(".py"))
            or (path.startswith("frontend/src/") and Path(path).suffix in {
                ".ts", ".tsx", ".css", ".svg", ".json"}))


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args])


def export_sources(repo, revision, destination):
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("Use a full 40-character commit SHA")
    actual = git(repo, "rev-parse", "--verify", revision + "^{commit}").decode().strip()
    if actual != revision:
        raise ValueError("Revision does not identify the requested commit")
    for entry in git(repo, "ls-tree", "-rz", revision).split(b"\0"):
        if not entry:
            continue
        metadata, raw_path = entry.split(b"\t", 1)
        path = raw_path.decode()
        if not selected(path):
            continue
        mode, kind, blob = metadata.decode().split()
        if mode not in {"100644", "100755"} or kind != "blob":
            raise ValueError("Selected source must be a regular tracked file")
        target = destination / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(git(repo, "cat-file", "blob", blob))
    if not (destination / "backend/app/staging.py").is_file():
        raise ValueError("Revision lacks the opt-in staging guard")


def build_environment(work):
    home = work / "build-home"
    home.mkdir()
    return {"PATH": os.environ.get("PATH", os.defpath), "HOME": str(home),
            "TMPDIR": str(work), "CI": "true", "VITE_API_URL": "/api",
            "npm_config_cache": str(work / "npm-cache"),
            "npm_config_registry": "https://registry.npmjs.org/"}


def write_archive(files, revision, output):
    """Stable metadata and ordering; refuse overwrite of an existing artifact."""
    manifest = {"source_revision": revision, "entrypoint": "app.staging:create_app",
                "api_base": "/api", "files": {
                    name: hashlib.sha256(content).hexdigest() for name, content in sorted(files.items())}}
    files = dict(files, **{"build-manifest.json": (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()})
    with output.open("xb") as raw:
        with gzip.GzipFile(fileobj=raw, mode="wb", filename="", mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode="w") as archive:
                for name, content in sorted(files.items()):
                    info = tarfile.TarInfo(name)
                    info.size, info.mode, info.mtime = len(content), 0o644, 0
                    archive.addfile(info, io.BytesIO(content))


def package(repo, revision, output):
    if output.exists():
        raise ValueError("Output already exists")
    with tempfile.TemporaryDirectory(prefix="ielts-staging-build-") as directory:
        work = Path(directory)
        source = work / "source"
        export_sources(repo, revision, source)
        # Snapshot non-frontend inputs directly after the Git export. Dependency
        # installation and compiler output must not be able to add or replace
        # arbitrary backend/docs entries in the artifact.
        files = {"STAGING-README.md": INSTRUCTIONS.encode()}
        for root in (source / "backend", source / "docs"):
            for path in root.rglob("*"):
                if path.is_file():
                    files[path.relative_to(source).as_posix()] = path.read_bytes()
        env = build_environment(work)
        npm = shutil.which("npm")
        if npm is None:
            raise ValueError("npm is required")
        frontend = source / "frontend"
        # Registry access may require the environment's existing transport proxy
        # and CA. Pass only these to install, never to the frontend compiler.
        install_env = dict(env)
        for key in ("HTTPS_PROXY", "HTTP_PROXY", "NO_PROXY", "https_proxy", "http_proxy", "no_proxy",
                    "NODE_EXTRA_CA_CERTS", "SSL_CERT_FILE", "NODE_USE_ENV_PROXY",
                    "npm_config_proxy", "npm_config_https_proxy", "npm_config_noproxy",
                    "NPM_CONFIG_PROXY", "NPM_CONFIG_HTTPS_PROXY", "NPM_CONFIG_NOPROXY"):
            if key in os.environ:
                install_env[key] = os.environ[key]
        subprocess.run([npm, "ci", "--ignore-scripts", "--no-audit", "--no-fund"],
                       cwd=frontend, env=install_env, check=True, timeout=300)
        subprocess.run([npm, "run", "build"], cwd=frontend, env=env, check=True, timeout=180)
        dist = frontend / "dist"
        if not (dist / "index.html").is_file():
            raise ValueError("Frontend build produced no index")
        for path in dist.rglob("*"):
            if path.is_symlink():
                raise ValueError("Frontend output must not contain links")
            if path.is_file():
                files["frontend/" + str(path.relative_to(dist))] = path.read_bytes()
        write_archive(files, revision, output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision", required=True, help="Exact full commit SHA, not branch name")
    parser.add_argument("--output", required=True, type=Path, help="New local .tar.gz path")
    args = parser.parse_args()
    package(Path(__file__).resolve().parents[1], args.revision, args.output.resolve())


if __name__ == "__main__":
    main()

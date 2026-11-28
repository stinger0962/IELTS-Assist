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
                  "frontend/tsconfig.app.json", "frontend/tsconfig.node.json", "frontend/public/vite.svg"}
BILLING_PREFIX = "/__ielts-billing-test/"
BILLING_RUNBOOK = "docs/qa/same-origin-billing-rehearsal.md"
BILLING_CHECK = "ops/check-billing-rehearsal.py"
BILLING_INSTRUCTIONS = """# IELTS sandbox rehearsal bundle (not deployed)

For the existing https://annababy.cc/__ielts-billing-test/ path only.
The included same-origin billing runbook is the operational source of truth.
This bundle neither configures ingress nor creates accounts, credentials,
webhook destinations, or databases. It does not contain real data or Stripe secrets.

Check the supplied archive digest and build-manifest.json before extracting
into a clean, dedicated directory. Install the listed backend dependencies in
a fresh environment. After checking the actual vhost, isolated PostgreSQL,
and the approved access gate, use the guarded launcher only:

    python -m app.same_origin_sandbox

Set PYTHONPATH to the extracted backend directory and IELTS_BILLING_TEST_DIST
to the extracted frontend directory. Start with both billing flags off
until the runbook preflight checks pass. Never run app.main:app or overwrite the
ordinary frontend's assets. Keep the test namespace gated; only the exact
signed sandbox webhook POST is exempt from the operator gate.

The smoke test is a learner opening the pass offer on the existing website,
using Stripe test mode, returning to the same path, and seeing the pass
activate only after verified settlement. No actual payment is permitted.
"""
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
            or path in {"docs/qa/dashboard-only-sandbox-staging.md", BILLING_RUNBOOK, BILLING_CHECK}
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


def write_archive(files, revision, output, *, same_origin=False):
    """Stable metadata and ordering; refuse overwrite of an existing artifact."""
    manifest = {"source_revision": revision,
                "entrypoint": "app.same_origin_sandbox" if same_origin else "app.staging:create_app",
                "api_base": BILLING_PREFIX + "api" if same_origin else "/api", "files": {
                    name: hashlib.sha256(content).hexdigest() for name, content in sorted(files.items())}}
    files = dict(files, **{"build-manifest.json": (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()})
    with output.open("xb") as raw:
        with gzip.GzipFile(fileobj=raw, mode="wb", filename="", mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode="w") as archive:
                for name, content in sorted(files.items()):
                    info = tarfile.TarInfo(name)
                    info.size, info.mode, info.mtime = len(content), 0o644, 0
                    archive.addfile(info, io.BytesIO(content))


def package(repo, revision, output, *, same_origin=False):
    if output.exists():
        raise ValueError("Output already exists")
    with tempfile.TemporaryDirectory(prefix="ielts-staging-build-") as directory:
        work = Path(directory)
        source = work / "source"
        export_sources(repo, revision, source)
        # Snapshot non-frontend inputs directly after the Git export. Dependency
        # installation and compiler output must not be able to add or replace
        # arbitrary backend/docs entries in the artifact.
        if same_origin and (not (source / "backend/app/same_origin_sandbox.py").is_file()
                            or not (source / BILLING_RUNBOOK).is_file()):
            raise ValueError("Revision lacks the guarded billing launcher or runbook")
        files = ({"BILLING-TEST-README.md": BILLING_INSTRUCTIONS.encode()} if same_origin
                 else {"STAGING-README.md": INSTRUCTIONS.encode()})
        if same_origin and (source / BILLING_CHECK).is_file():
            files[BILLING_CHECK] = (source / BILLING_CHECK).read_bytes()
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
        build = [npm, "run", "build"] + (["--", "--mode", "billing-test"] if same_origin else [])
        subprocess.run(build, cwd=frontend, env=env, check=True, timeout=180)
        dist = frontend / "dist"
        index = dist / "index.html"
        if not index.is_file():
            raise ValueError("Frontend build produced no index")
        if same_origin:
            _check_billing_index(index.read_text(), dist)
        for path in dist.rglob("*"):
            if path.is_symlink():
                raise ValueError("Frontend output must not contain links")
            if path.is_file():
                files["frontend/" + str(path.relative_to(dist))] = path.read_bytes()
        write_archive(files, revision, output, same_origin=same_origin)


def _check_billing_index(html, dist):
    assets = re.findall(r'\b(?:src|href)="([^"]+)"', html)
    local = [asset for asset in assets if asset.startswith("/")]
    if (not any(a.startswith(BILLING_PREFIX + "assets/") and a.endswith(".js") for a in local)
            or any(not a.startswith(BILLING_PREFIX) for a in local)):
        raise ValueError("Frontend index is not a billing-test build")
    for asset in local:
        path = asset.removeprefix(BILLING_PREFIX)
        if (not re.fullmatch(r"(?:assets/[A-Za-z0-9_.-]+|vite\.svg)", path)
                or not (dist / path).is_file()):
            raise ValueError("Billing-test index references a missing or invalid asset")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision", required=True, help="Exact full commit SHA, not branch name")
    parser.add_argument("--output", required=True, type=Path, help="New local .tar.gz path")
    parser.add_argument("--same-origin-billing-test", action="store_true",
                        help="Build only the guarded same-domain billing-test artifact")
    args = parser.parse_args()
    package(Path(__file__).resolve().parents[1], args.revision, args.output.resolve(),
            same_origin=args.same_origin_billing_test)


if __name__ == "__main__":
    main()

"""Local source packaging checks; no package downloads or app/provider startup."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tarfile

import pytest

spec = importlib.util.spec_from_file_location(
    "staging_package", Path(__file__).resolve().parents[2] / "ops/package-staging.py")
packaging = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packaging)


@pytest.mark.parametrize("path", ["backend/.env", "frontend/.env.production", "backend/app/.env.py",
    "backend/ielts_assist.db", "backend/gcp-key.json", "backend/app/key.json",
    "/frontend/src/x.ts", "backend/audio/file.wav", "frontend/node_modules/pkg/index.ts", "../frontend/src/x.ts",
    "frontend/demo-preview/index.html", "tools/mock-preview/run.ts",
    "frontend/src/__tests__/test.ts", "frontend/src/__tests__/fixtures/fullMock.json"])
def test_disallowed_inputs(path):
    assert not packaging.selected(path)


def test_clean_build_environment_discards_caller_secrets(tmp_path, monkeypatch):
    monkeypatch.setenv("VITE_API_URL", "https://production.invalid/api")
    monkeypatch.setenv("VITE_SECRET", "not-shipped")
    monkeypatch.setenv("STRIPE_TEST_SECRET_KEY", "not-shipped")
    monkeypatch.setenv("NODE_OPTIONS", "--require=unapproved.js")
    monkeypatch.setenv("npm_config_userconfig", "/unapproved/npmrc")
    result = packaging.build_environment(tmp_path)
    assert result["VITE_API_URL"] == "/api"
    assert "VITE_SECRET" not in result
    assert "STRIPE_TEST_SECRET_KEY" not in result
    assert "NODE_OPTIONS" not in result
    assert "npm_config_userconfig" not in result
    assert result["HOME"] == str(tmp_path / "build-home")


def test_archive_manifest_hashes_and_deterministic_metadata(tmp_path):
    files = {"backend/app/staging.py": b"# guard\n", "frontend/index.html": b"fixture"}
    first, second = tmp_path / "first.gz", tmp_path / "second.gz"
    packaging.write_archive(files, "a" * 40, first)
    packaging.write_archive(files, "a" * 40, second)
    assert first.read_bytes() == second.read_bytes()
    with tarfile.open(first, "r:gz") as archive:
        assert sorted(archive.getnames()) == ["backend/app/staging.py", "build-manifest.json", "frontend/index.html"]
        manifest = json.load(archive.extractfile("build-manifest.json"))
        assert manifest["entrypoint"] == "app.staging:create_app"
        assert manifest["source_revision"] == "a" * 40
        assert manifest["api_base"] == "/api"
        assert manifest["files"] == {k: hashlib.sha256(v).hexdigest() for k, v in files.items()}
        assert all(member.isfile() and member.mode == 0o644 and member.mtime == 0 for member in archive)
    with pytest.raises(FileExistsError):
        packaging.write_archive(files, "a" * 40, first)


def test_export_uses_only_exact_tracked_revision_and_ignores_local_data(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    def write(path, value):
        target = repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(value)
    write("backend/app/staging.py", "# committed guard\n")
    write("backend/.env", "SECRET=fixture-never-export\n")
    write("frontend/.env.production", "VITE_SECRET=fixture-never-export\n")
    write("frontend/src/App.tsx", "// committed UI\n")
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repo), "-c", "user.name=Fixture", "-c", "user.email=fixture@invalid.test",
                    "commit", "-qm", "fixture"], check=True)
    revision = packaging.git(repo, "rev-parse", "HEAD").decode().strip()
    write("backend/app/staging.py", "# uncommitted change\n")
    write("backend/app/local_secret.py", "# untracked fixture\n")
    target = tmp_path / "snapshot"
    packaging.export_sources(repo, revision, target)
    assert (target / "backend/app/staging.py").read_text() == "# committed guard\n"
    assert sorted(str(p.relative_to(target)) for p in target.rglob("*") if p.is_file()) == [
        "backend/app/staging.py", "frontend/src/App.tsx"]
    with pytest.raises(ValueError, match="full 40"):
        packaging.export_sources(repo, "HEAD", tmp_path / "nope")

    (repo / "frontend/src/link.ts").symlink_to("../../outside.ts")
    subprocess.run(["git", "-C", str(repo), "add", "frontend/src/link.ts"], check=True)
    subprocess.run(["git", "-C", str(repo), "-c", "user.name=Fixture", "-c", "user.email=fixture@invalid.test",
                    "commit", "-qm", "fixture link"], check=True)
    linked_revision = packaging.git(repo, "rev-parse", "HEAD").decode().strip()
    with pytest.raises(ValueError, match="regular tracked"):
        packaging.export_sources(repo, linked_revision, tmp_path / "reject-link")


def test_package_build_never_embeds_ambient_markers(tmp_path, monkeypatch):
    marker = "PRIVATE_ENV_MARKER_NOT_FOR_ASSETS"
    monkeypatch.setenv("VITE_SECRET", marker)
    monkeypatch.setenv("HTTPS_PROXY", "https://transport.invalid")
    monkeypatch.setenv("NODE_EXTRA_CA_CERTS", "/existing/transport-ca.pem")
    def export(repo, revision, destination):
        for name, content in {"backend/app/staging.py": "# guard", "backend/requirements.txt": "",
                              "docs/qa/dashboard-only-sandbox-staging.md": "# runbook",
                              "frontend/package.json": "{}"}.items():
            path = destination / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
    monkeypatch.setattr(packaging, "export_sources", export)
    monkeypatch.setattr(packaging.shutil, "which", lambda name: "/fixture/npm")
    calls = []
    def run(args, *, cwd, env, check, timeout):
        calls.append(args)
        assert "VITE_SECRET" not in env
        if args[1] == "ci":
            assert env["HTTPS_PROXY"] == "https://transport.invalid"
            assert env["NODE_EXTRA_CA_CERTS"] == "/existing/transport-ca.pem"
            assert "--ignore-scripts" in args
        else:
            assert "HTTPS_PROXY" not in env and "NODE_EXTRA_CA_CERTS" not in env
            dist = cwd / "dist"
            dist.mkdir()
            (dist / "index.html").write_text("<script>const api=" + repr(env["VITE_API_URL"]) + "</script>")
    monkeypatch.setattr(packaging.subprocess, "run", run)
    output = tmp_path / "bundle.tar.gz"
    packaging.package(tmp_path, "a" * 40, output)
    assert len(calls) == 2
    with tarfile.open(output) as archive:
        index = archive.extractfile("frontend/index.html").read()
        assert b"/api" in index and marker.encode() not in index
        for member in archive:
            assert marker.encode() not in archive.extractfile(member).read()


def test_build_cannot_add_or_replace_exported_backend_files(tmp_path, monkeypatch):
    def fake_export(repo, revision, source):
        (source / "backend/app").mkdir(parents=True)
        (source / "backend/app/staging.py").write_bytes(b"# tracked guard")
        (source / "frontend").mkdir()

    def fake_npm(args, *, cwd, env, check, timeout):
        if args[1] != "run":
            return
        (cwd.parent / "backend/app/staging.py").write_bytes(b"# altered after export")
        (cwd.parent / "backend/.env").write_bytes(b"unexpected")
        (cwd / "dist").mkdir()
        (cwd / "dist/index.html").write_bytes(b"fixture")

    monkeypatch.setattr(packaging, "export_sources", fake_export)
    monkeypatch.setattr(packaging.shutil, "which", lambda _: "npm")
    monkeypatch.setattr(packaging.subprocess, "run", fake_npm)
    target = tmp_path / "bundle.tar.gz"
    packaging.package(tmp_path, "a" * 40, target)
    with tarfile.open(target, "r:gz") as archive:
        assert archive.extractfile("backend/app/staging.py").read() == b"# tracked guard"
        assert "backend/.env" not in archive.getnames()


def test_same_origin_bundle_selects_fixed_build_mode_and_launcher(tmp_path, monkeypatch):
    def export(repo, revision, source):
        for name, body in {
            "backend/app/same_origin_sandbox.py": "# guarded launcher",
            packaging.BILLING_RUNBOOK: "# rehearsal runbook",
            packaging.BILLING_CHECK: "# read-only probe",
            "frontend/package.json": "{}",
        }.items():
            path = source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body)

    def npm(args, *, cwd, env, check, timeout):
        if args[1] != "run":
            return
        assert args[1:] == ["run", "build", "--", "--mode", "billing-test"]
        dist = cwd / "dist"
        (dist / "assets").mkdir(parents=True)
        (dist / "assets/app.js").write_text("fixture")
        (dist / "vite.svg").write_text("<svg/>")
        (dist / "index.html").write_text(
            '<script src="/__ielts-billing-test/assets/app.js"></script>'
            '<link href="/__ielts-billing-test/vite.svg">')

    monkeypatch.setattr(packaging, "export_sources", export)
    monkeypatch.setattr(packaging.subprocess, "run", npm)
    monkeypatch.setattr(packaging.shutil, "which", lambda _: "npm")
    out = tmp_path / "billing.tgz"
    packaging.package(tmp_path, "b" * 40, out, same_origin=True)
    with tarfile.open(out, "r:gz") as archive:
        manifest = json.load(archive.extractfile("build-manifest.json"))
        assert manifest["entrypoint"] == "app.same_origin_sandbox"
        assert manifest["api_base"] == "/__ielts-billing-test/api"
        assert manifest["source_revision"] == "b" * 40
        assert "BILLING-TEST-README.md" in archive.getnames()
        assert archive.extractfile(packaging.BILLING_CHECK).read() == b"# read-only probe"
        assert "STAGING-README.md" not in archive.getnames()
        for name, digest in manifest["files"].items():
            assert hashlib.sha256(archive.extractfile(name).read()).hexdigest() == digest


@pytest.mark.parametrize("html", [
    '<script src="/assets/app.js"></script>',
    '<script src="/__ielts-billing-test/assets/missing.js"></script>',
    '<script src="/__ielts-billing-test/assets/app.js"></script><link href="/vite.svg">',
])
def test_rehearsal_artifact_rejects_root_or_missing_assets(tmp_path, html):
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets/app.js").touch()
    with pytest.raises(ValueError, match="billing-test build|missing or invalid asset"):
        packaging._check_billing_index(html, tmp_path)

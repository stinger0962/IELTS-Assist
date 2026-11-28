#!/usr/bin/env python3
"""Read-only routing checks for the fixed annababy.cc billing rehearsal.

Run on the rehearsal host, with the verified bundle's build-manifest.json.
Does not authenticate, contact Stripe, change settings, or validate checkout.
"""
import argparse
from hashlib import sha256
from http.client import HTTPConnection, HTTPException
import json
from pathlib import Path
import re
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener

HOST = "annababy.cc"
PREFIX = "/__ielts-billing-test/"
HEALTH = PREFIX + "api/health"
LIMIT = 8 * 1024 * 1024
MIME = {".html": {"text/html"}, ".js": {"text/javascript", "application/javascript"},
        ".css": {"text/css"}, ".svg": {"image/svg+xml"}}


class CheckError(Exception):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def read_response(path, response):
    headers = {k.lower(): v for k, v in response.getheaders()}
    body = response.read(LIMIT + 1) if response.status == 200 else b""
    if len(body) > LIMIT:
        raise CheckError(f"{path}: response too large")
    return response.status, headers, body


def get(public, path, host=HOST):
    headers = {"Host": host, "Accept-Encoding": "identity"}
    try:
        if public:
            # Normal platform TLS trust and proxy configuration, never redirect or authenticate.
            opener = build_opener(NoRedirect())
            try:
                response = opener.open(Request("https://" + HOST + path, headers=headers), timeout=10)
            except HTTPError as error:
                response = error
            with response:
                return read_response(path, response)
        conn = HTTPConnection("127.0.0.1", 8011, timeout=5)
        try:
            conn.request("GET", path, headers=headers)
            with conn.getresponse() as response:
                return read_response(path, response)
        finally:
            conn.close()
    except (OSError, HTTPException):
        raise CheckError(f"{path}: connection failed") from None


def content_type(headers):
    return headers.get("content-type", "").split(";", 1)[0].strip().lower()


def validate_health(label, response):
    code, headers, body = response
    if code != 200 or content_type(headers) != "application/json":
        raise CheckError(f"{label}: expected HTTP 200 JSON, got HTTP {code}")
    try:
        payload = json.loads(body)
        if (isinstance(payload, dict) and payload.get("status") == "healthy"
                and payload.get("database") == "ok"):
            return
    except (ValueError, UnicodeError):
        pass
    raise CheckError(f"{label}: healthy database not confirmed")


def checks_from_manifest(manifest):
    if (not isinstance(manifest, dict) or manifest.get("api_base") != PREFIX + "api"
            or manifest.get("entrypoint") != "app.same_origin_sandbox"
            or not re.fullmatch(r"[0-9a-f]{40}", str(manifest.get("source_revision")))
            or not isinstance(manifest.get("files"), dict)):
        raise CheckError("Use the verified same-origin build manifest")
    files = manifest["files"]
    assets = {name.removeprefix("frontend/"): digest for name, digest in files.items()
              if re.fullmatch(r"frontend/assets/[A-Za-z0-9_-][A-Za-z0-9_.-]*\.(?:js|css)", name)}
    for name in ("index.html", "vite.svg"):
        assets[name] = files.get("frontend/" + name)
    if (not all(any(name.endswith(ext) for name in assets) for ext in (".js", ".css"))
            or not all(isinstance(d, str) and re.fullmatch(r"[0-9a-f]{64}", d) for d in assets.values())):
        raise CheckError("Manifest lacks required frontend digests")
    return assets


def guard(label, headers):
    controls = {part.strip().lower() for part in headers.get("cache-control", "").split(",")}
    if not {"private", "no-store"} <= controls or "set-cookie" in headers:
        raise CheckError(f"{label}: missing private/no-store or returned a cookie")


def check_loopback(manifest, fetch=get):
    files = checks_from_manifest(manifest)
    health = fetch(False, HEALTH)
    validate_health("Loopback billing health", health)
    guard(HEALTH, health[1])
    for name, digest in files.items():
        paths = (PREFIX, PREFIX + "practice", PREFIX + "checkout/return",
                 PREFIX + "checkout/cancel") if name == "index.html" else (PREFIX + name,)
        for path in paths:
            code, headers, body = fetch(False, path)
            guard(path, headers)
            if (code != 200 or content_type(headers) not in MIME[Path(name).suffix]
                    or sha256(body).hexdigest() != digest):
                raise CheckError(f"{path}: not the expected namespaced build")
    if fetch(False, "/")[0] != 404 or fetch(False, HEALTH, "localhost")[0] != 404:
        raise CheckError("Loopback root or wrong Host was not rejected")


def check_public(manifest, fetch=get):
    files = checks_from_manifest(manifest)
    home = fetch(True, "/")
    if home[0] != 200 or content_type(home[1]) != "text/html":
        raise CheckError(f"Ordinary home: expected HTTP 200 HTML, got HTTP {home[0]}")
    validate_health("Ordinary API health", fetch(True, "/api/health"))
    paths = [PREFIX, HEALTH, PREFIX + "practice", PREFIX + "checkout/return", PREFIX + "checkout/cancel",
             *(PREFIX + name for name in files if name != "index.html")]
    for path in paths:
        code, headers, body = fetch(True, path)
        if code == 200:
            if body == home[2] and content_type(headers) == "text/html":
                raise CheckError(f"{path}: ordinary homepage fallback; rehearsal not reachable")
            raise CheckError(f"{path}: unexpectedly public HTTP 200; inspect the gate")
        if code not in {401, 403, 404}:
            raise CheckError(f"{path}: unexpected HTTP {code}; denial not confirmed")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path, help="build-manifest.json from the verified same-origin bundle")
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--public-only", action="store_true", help="Run from a client the edge should deny")
    modes.add_argument("--loopback-only", action="store_true", help="Run on the rehearsal host")
    args = parser.parse_args()
    try:
        manifest = json.loads(args.manifest.read_bytes())
        (check_public if args.public_only else check_loopback)(manifest)
    except CheckError as exc:
        parser.exit(1, f"Check failed: {exc}\n")
    except (OSError, ValueError):
        parser.exit(1, "Check failed: unreadable build manifest\n")
    if args.public_only:
        print("Anonymous denial and normal site health checked only; rehearsal not verified.")
    else:
        print("Loopback build checked only. Verify public denial, allowed TLS and checkout separately.")


if __name__ == "__main__":
    main()

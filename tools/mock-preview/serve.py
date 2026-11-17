"""Synthetic, loopback-only demo. No application startup, accounts or providers."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from app.services.full_mock_preview import active_mock_preview
from app.services.full_mock_renderer_bridge import RENDERER_VERSION
from app.services.full_mock_raw_score import score_full_mock

FIXTURES = json.loads((ROOT / "frontend/src/__tests__/fixtures/fullMockRenderer.json").read_text())
DIST = ROOT / "frontend/demo-preview/dist"


def preview(skill):
    return active_mock_preview(FIXTURES[skill]["exercise"], skill=skill, renderer_version=RENDERER_VERSION)


def score(skill, submission):
    return score_full_mock(FIXTURES[skill]["exercise"], submission, skill=skill)


class Handler(BaseHTTPRequestHandler):
    def allowed(self):
        expected = f"127.0.0.1:{self.server.server_port}"
        return self.headers.get("Host") == expected and self.headers.get("Origin") in (None, "http://" + expected)

    def reply(self, status, body, content_type="application/json"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if not self.allowed():
            return self.reply(403, b'{}')
        if self.path in ("/preview/reading", "/preview/listening"):
            return self.reply(200, json.dumps(preview(self.path.rsplit("/", 1)[1])).encode())
        # Serve only built artifacts, not source fixtures containing answers.
        relative = "index.html" if self.path == "/" else self.path.lstrip("/")
        target = (DIST / relative).resolve()
        if not target.is_relative_to(DIST.resolve()) or not target.is_file():
            return self.reply(404, b'{}')
        return self.reply(200, target.read_bytes(), mimetypes.guess_type(target.name)[0] or "application/octet-stream")

    def do_POST(self):
        if not self.allowed():
            return self.reply(403, b'{}')
        if self.path not in ("/score/reading", "/score/listening"):
            return self.reply(404, b'{}')
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 16384 or self.headers.get("Content-Type") != "application/json":
                raise ValueError()
            submission = json.loads(self.rfile.read(length))
            result = score(self.path.rsplit("/", 1)[1], submission)
        except (ValueError, TypeError):
            return self.reply(400, b'{"error":"Invalid raw submission"}')
        return self.reply(200, json.dumps(result).encode())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    if not (DIST / "index.html").is_file():
        parser.error("Build frontend/demo-preview first; see tools/mock-preview/README.md.")
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Synthetic preview: http://127.0.0.1:{server.server_port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

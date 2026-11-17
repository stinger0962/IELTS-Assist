"""Run with Python's unittest, no application or provider dependencies."""
from http.client import HTTPConnection
import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from serve import Handler, preview, score


class DemoTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def request(self, method, path, body=None, headers=None):
        conn = HTTPConnection("127.0.0.1", self.server.server_port)
        conn.request(method, path, body, headers or {})
        result = conn.getresponse()
        status, data = result.status, result.read()
        conn.close()
        return status, data

    def test_real_preview_to_score(self):
        for skill in ("reading", "listening"):
            status, body = self.request("GET", "/preview/" + skill)
            self.assertEqual(status, 200)
            dto = json.loads(body)
            self.assertEqual(dto, preview(skill))
            self.assertNotIn('"answer"', body.decode())
            self.assertNotIn('"transcript"', body.decode())
            key = dto["sections"][0]["questions"][0]["key"]
            envelope = {"schema_version": "full_mock_raw_v2", "answers": {key: "box"}}
            status, result = self.request("POST", "/score/" + skill, json.dumps(envelope),
                                          {"Content-Type": "application/json"})
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(result), score(skill, envelope))
            self.assertEqual(json.loads(result)["correct"], 1)
            self.assertEqual(json.loads(result)["total"], 40)

    def test_reject_bad_hosts_origins_keys_and_source_files(self):
        self.assertEqual(self.request("GET", "/", headers={"Host": "evil.example"})[0], 403)
        self.assertEqual(self.request("GET", "/", headers={"Origin": "https://evil.example"})[0], 403)
        for path in ("/../../serve.py", "/src/__tests__/fixtures/fullMockRenderer.json", "/audio/synthetic.wav"):
            self.assertEqual(self.request("GET", path)[0], 404)
        body = json.dumps({"schema_version": "full_mock_raw_v2", "answers": {"q_0_0": "box"}})
        self.assertEqual(self.request("POST", "/score/reading", body, {"Content-Type": "application/json"})[0], 400)
        self.assertEqual(self.request("POST", "/score/reading", "{}")[0], 400)

    def test_blank_is_zero(self):
        for skill in ("reading", "listening"):
            self.assertEqual(score(skill, {"schema_version": "full_mock_raw_v2", "answers": {}})["correct"], 0)


if __name__ == "__main__":
    unittest.main()

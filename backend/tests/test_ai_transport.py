import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from time import sleep

from app.services import ai


def test_slow_plan_reply_outlives_normal_ai_timeout(monkeypatch):
    content = json.dumps({"morning": [], "evening": [], "summary": "Test plan"})
    body = json.dumps({"choices": [{"message": {"content": content}, "finish_reason": "stop"}]}).encode()

    class SlowModel(BaseHTTPRequestHandler):
        def do_POST(self):
            self.rfile.read(int(self.headers["Content-Length"]))
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            # Pause after the headers too: generation must not have a body-read deadline.
            sleep(1.25)
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), SlowModel)
    thread = Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
    thread.start()
    monkeypatch.setattr(ai, "PROVIDER", "local")
    monkeypatch.setattr(ai, "LOCAL_URL", f"http://127.0.0.1:{server.server_port}/api/v1/chat")
    monkeypatch.setattr(ai, "LOCAL_TIMEOUT", 0.5)
    try:
        result = ai.complete_structured("Build a plan", schema={"type": "object"}, system="Test")
        assert json.loads(result) == json.loads(content)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

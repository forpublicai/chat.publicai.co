from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import time

MODELS = ("spain-repro", "spain-paired-control", "spain-structured-control")


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.rstrip("/") == "/v1/models":
            self.send_json(
                {
                    "object": "list",
                    "data": [
                        {"id": model, "object": "model", "owned_by": "local-test"}
                        for model in MODELS
                    ],
                }
            )
        else:
            self.send_error(404)

    def send_json(self, payload):
        encoded = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_POST(self):
        if self.path.rstrip("/") != "/v1/chat/completions":
            self.send_error(404)
            return
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        model = body.get("model")
        if not body.get("stream"):
            self.send_json(
                {
                    "id": "local-task",
                    "object": "chat.completion",
                    "model": model,
                    "choices": [
                        {
                            "index": 0,
                            "message": {
                                "role": "assistant",
                                "content": "Synthetic test",
                            },
                            "finish_reason": "stop",
                        }
                    ],
                }
            )
            return
        if model == MODELS[1]:
            deltas = [
                {"content": s}
                for s in ("<thi", "nk>Audit preface.", "</thi", "nk>", "42")
            ]
        elif model == MODELS[2]:
            deltas = [{"reasoning_content": "Audit preface."}, {"content": "42"}]
        else:
            deltas = [{"content": s} for s in ("Audit preface.", "</thi", "nk>", "42")]
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        for delta in [{"role": "assistant"}, *deltas, {}]:
            choice = {
                "index": 0,
                "delta": delta,
                "finish_reason": None if delta else "stop",
            }
            event = {
                "id": "local-fixture",
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": model,
                "choices": [choice],
            }
            self.wfile.write(f"data: {json.dumps(event)}\n\n".encode())
            self.wfile.flush()
        self.wfile.write(b"data: [DONE]\n\n")


ThreadingHTTPServer(("127.0.0.1", 18742), Handler).serve_forever()

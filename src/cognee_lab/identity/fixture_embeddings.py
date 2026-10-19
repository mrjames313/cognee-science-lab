"""Local deterministic embedding SERVICE for fixtures, not a storage adapter.

The real configured vector interface calls this OpenAI-compatible endpoint.
This exercises storage/index retrieval, not embedding-model quality.
"""

import hashlib
import json
import math
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def embed(text, dimensions=64):
    vector = [0.0] * dimensions
    for token in re.findall(r"\w+", str(text).casefold()):
        index = (
            int.from_bytes(hashlib.sha256(token.encode()).digest()[:4], "big")
            % dimensions
        )
        vector[index] += 1.0
    norm = math.sqrt(sum(v * v for v in vector)) or 1.0
    return [v / norm for v in vector]


class FixtureEmbeddings:
    def __enter__(self):
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_POST(self):
                if self.path != "/v1/embeddings":
                    self.send_error(404)
                    return
                request = json.loads(
                    self.rfile.read(int(self.headers["Content-Length"]))
                )
                inputs = request["input"]
                if isinstance(inputs, str):
                    inputs = [inputs]
                result = dict(
                    object="list",
                    model=request.get("model", "fixture"),
                    data=[
                        dict(object="embedding", index=i, embedding=embed(t))
                        for i, t in enumerate(inputs)
                    ],
                    usage=dict(prompt_tokens=0, total_tokens=0),
                )
                payload = json.dumps(result).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return f"http://127.0.0.1:{self.server.server_port}/v1"

    def __exit__(self, *_):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

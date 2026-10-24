"""Serve the Crypty static site and its same-origin chat API."""

import argparse
import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from chatbot import answer_question


WEBSITE_ROOT = Path(__file__).resolve().parents[1]
MAX_REQUEST_BYTES = 64 * 1024


class CryptyHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEBSITE_ROOT), **kwargs)

    def do_POST(self):
        if self.path != "/api/chat":
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > MAX_REQUEST_BYTES:
                self._json(413 if length > MAX_REQUEST_BYTES else 400,
                           {"error": "Request must be between 1 byte and 64 KB."})
                return
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            question = payload.get("question", "")
            history = payload.get("history", [])
            if not isinstance(question, str) or not isinstance(history, list):
                self._json(400, {"error": "Question and history have an invalid format."})
                return
            if len(question) > 4000:
                self._json(400, {"error": "Please keep your question under 4,000 characters."})
                return
            reply = answer_question(question, history)
            self._json(200, {"reply": reply})
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._json(400, {"error": "Request body must be valid JSON."})
        except (RuntimeError, ValueError) as error:
            self._json(502, {"error": str(error)})
        except Exception:
            self._json(500, {"error": "The chat service hit an unexpected error."})

    def _json(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def main():
    parser = argparse.ArgumentParser(description="Run Crypty's website and chat bot")
    parser.add_argument("--host", default="127.0.0.1", help="Host interface (default: localhost)")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), CryptyHandler)
    print(f"Crypty website: http://{args.host}:{args.port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

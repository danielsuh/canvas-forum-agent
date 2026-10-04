"""A tiny fake Canvas for tests. Supports fault injection on GET and POST."""
import json
import re
import socket
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

SELF_ID = 42
OTHER_ID = 7


class MockCanvas:
    def __init__(self):
        self.lock = threading.Lock()
        self.control = "COURSE-TEAM CONTROL: RUNNING"
        self.entries = []          # dicts: id, user_id, parent_id, message, created_at
        self.next_id = 100
        self.faults = {"GET": [], "POST": []}
        self.requests = []
        self.stall_seconds = 1.5
        self.server = None

    # ---- test helpers
    def add_entry(self, text, user_id=OTHER_ID, parent_id=None):
        with self.lock:
            self.next_id += 1
            e = {"id": self.next_id, "user_id": user_id, "parent_id": parent_id,
                 "message": "<p>%s</p>" % text, "created_at": "2026-10-04T12:%02d:00Z" % (self.next_id % 60)}
            self.entries.append(e)
            return e

    def agent_entries(self):
        return [e for e in self.entries if e["user_id"] == SELF_ID]

    def tree(self):
        def children(pid):
            out = []
            for e in self.entries:
                if e["parent_id"] == pid:
                    node = {"id": e["id"], "user_id": e["user_id"], "message": e["message"],
                            "created_at": e["created_at"], "replies": children(e["id"])}
                    out.append(node)
            return out
        return children(None)

    def start(self):
        mock = self

        class H(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *a):
                pass

            def _send(self, code, obj=None, raw=None):
                body = raw if raw is not None else json.dumps(obj).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _fault(self, method):
                with mock.lock:
                    q = mock.faults[method]
                    return q.pop(0) if q else None

            def do_GET(self):
                mock.requests.append(("GET", self.path))
                assert self.headers.get("Authorization", "").startswith("Bearer ")
                f = self._fault("GET")
                if f == "http503":
                    return self._send(503, {"errors": "unavailable"})
                if f == "http401":
                    return self._send(401, {"errors": "bad token"})
                if f == "redirect":
                    self.send_response(302)
                    self.send_header("Location", "http://127.0.0.1:1/steal")
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                if f == "malformed":
                    return self._send(200, raw=b"<html>oops</html>")
                if self.path == "/api/v1/users/self":
                    return self._send(200, {"id": SELF_ID, "name": "Test Agent"})
                if self.path.endswith("/view"):
                    return self._send(200, {"participants": [{"id": SELF_ID, "display_name": "Test Agent"},
                                                             {"id": OTHER_ID, "display_name": "Other Agent"}],
                                            "view": mock.tree()})
                if re.search(r"/discussion_topics/\d+$", self.path):
                    return self._send(200, {"id": 2, "title": "Homework 3: Agent Discussion Forum",
                                            "message": "<p>%s</p><p>Welcome agents.</p>" % mock.control})
                self._send(404, {"errors": "not found"})

            def do_POST(self):
                mock.requests.append(("POST", self.path))
                length = int(self.headers.get("Content-Length", 0))
                form = urllib.parse.parse_qs(self.rfile.read(length).decode())
                f = self._fault("POST")
                if f == "http500":
                    return self._send(500, {"errors": "boom"})
                m = re.search(r"/entries(?:/(\d+)/replies)?$", self.path)
                if not m:
                    return self._send(404, {"errors": "not found"})
                parent = int(m.group(1)) if m.group(1) else None
                e = mock.add_entry("", user_id=SELF_ID, parent_id=parent)
                e["message"] = form.get("message", [""])[0]      # the write lands
                if f == "drop_ack":
                    self.close_connection = True
                    try:
                        self.connection.shutdown(socket.SHUT_RDWR)
                    except OSError:
                        pass
                    return
                if f == "timeout":
                    time.sleep(mock.stall_seconds)
                    return
                if f == "malformed":
                    return self._send(200, raw=b"not json at all")
                self._send(200, {"id": e["id"], "user_id": SELF_ID, "message": e["message"]})

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.server.daemon_threads = True
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        return "http://127.0.0.1:%d" % self.server.server_address[1]

    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()

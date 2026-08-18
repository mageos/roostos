#!/bin/bash
set -e

echo "=== Starting Upstream WAN Internet Simulator (172.30.1.100) ==="

# Python mock web/echo server for testing external internet connectivity
cat << 'EOF' > /tmp/wan_mock_server.py
import http.server
import socketserver
import json

PORT = 80

class WANHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Server", "WAN-Internet-Simulator")
        self.end_headers()
        response = {
            "status": "online",
            "client_ip": self.client_address[0],
            "client_port": self.client_address[1],
            "path": self.path,
            "host_header": self.headers.get("Host", ""),
            "message": "Connected to Upstream Internet WAN"
        }
        self.wfile.write(json.dumps(response, indent=2).encode("utf-8"))

    def log_message(self, format, *args):
        print(f"[WAN-HTTP] {self.address_string()} - {format % args}")

with socketserver.TCPServer(("", PORT), WANHandler) as httpd:
    print(f"WAN Mock HTTP Server listening on port {PORT}...")
    httpd.serve_forever()
EOF

python3 /tmp/wan_mock_server.py &
HTTP_PID=$!

cleanup() {
    echo "Stopping WAN Mock Server..."
    kill -TERM "$HTTP_PID" 2>/dev/null || true
    exit 0
}

trap cleanup SIGINT SIGTERM

wait "$HTTP_PID"

#!/usr/bin/env python3
"""RoostOS UI Redesign Prototype Local Web Server.

Serves the interactive prototype application and site map explorer.
"""

import http.server
import os
import socketserver
import sys
from typing import NoReturn


class PrototypeHttpRequestHandler(http.server.SimpleHTTPRequestHandler):
    """Custom HTTP handler with proper MIME types and CORS support."""

    def end_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        super().end_headers()

    def guess_type(self, path: str) -> str:
        if path.endswith(".js"):
            return "application/javascript"
        if path.endswith(".css"):
            return "text/css"
        if path.endswith(".html"):
            return "text/html"
        if path.endswith(".json"):
            return "application/json"
        return super().guess_type(path)


def run_server(port: int = 3300) -> NoReturn:
    """Run prototype HTTP server on the specified port."""
    current_dir: str = os.path.dirname(os.path.abspath(__file__))
    os.chdir(current_dir)

    handler = PrototypeHttpRequestHandler
    # Allow port reuse to prevent 'Address already in use' errors on quick restarts
    socketserver.TCPServer.allow_reuse_address = True

    try:
        with socketserver.TCPServer(("", port), handler) as httpd:
            print("=" * 65)
            print(f"🦅 RoostOS UI Redesign - Interactive Exploration Prototype")
            print("=" * 65)
            print(f"👉 Local Access URL: http://localhost:{port}")
            print(f"📁 Serving directory: {current_dir}")
            print(f"✨ Features:")
            print(f"   • Concept 1: Dual-Persona (Household Hub vs SysAdmin Console)")
            print(f"   • Concept 2: Unified Topology (Progressive Disclosure)")
            print(f"   • Device Simulator: Mobile (iPhone), Tablet, and Desktop")
            print(f"   • Interactive Fake Data: Inline add/edit rows per AGENTS.md")
            print("=" * 65)
            print("Press Ctrl+C to terminate.")
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nPrototype server stopped.")
        sys.exit(0)


if __name__ == "__main__":
    port_num: int = 3300
    if len(sys.argv) > 1:
        try:
            port_num = int(sys.argv[1])
        except ValueError:
            print(f"Invalid port: {sys.argv[1]}, using default 3300")

    run_server(port_num)

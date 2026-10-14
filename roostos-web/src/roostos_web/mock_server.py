"""Dedicated launcher for the RoostOS Mock API & UI Test Server.

Run with:
    python -m roostos_web.mock_server [--port 8000] [--reload]
"""

import os
import sys
import argparse
import uvicorn

from roostos_web.di import create_mock_web_injector, set_injector
from roostos_web.main import create_app


def run_mock_server() -> None:
    parser = argparse.ArgumentParser(description="RoostOS Standalone Mock API & UI Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host interface to bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind (default: 8000)")
    parser.add_argument("--reload", action="store_true", default=False, help="Enable auto-reloading on file changes")
    args = parser.parse_args()

    # Enforce mock environment variables
    os.environ["ROOSTOS_MOCK"] = "1"
    os.environ["ROOSTOS_MOCK_AUTH"] = "1"
    os.environ["ROOSTOS_DEV_MOCK"] = "1"

    # Initialize DI Container with In-Memory Mock Services
    mock_injector = create_mock_web_injector()
    set_injector(mock_injector)

    app = create_app(mode="full", no_ui=False)

    print("=" * 64)
    print("  🚀 RoostOS UI Test Server (Standalone Mock Environment)")
    print(f"  🌐 Frontend UI:  http://{args.host}:{args.port}/")
    print(f"  📚 OpenAPI Docs: http://{args.host}:{args.port}/docs")
    print("  🔑 Auth:         Mock Auto-Login (Admin session active)")
    print("  💾 Data Store:   In-Memory Seed Config (No /etc/roostos needed)")
    print("  📡 Daemon IPC:   MockRoostClient (No D-Bus needed)")
    print("=" * 64)

    if args.reload:
        uvicorn.run("roostos_web.main:app", host=args.host, port=args.port, reload=True)
    else:
        uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    run_mock_server()

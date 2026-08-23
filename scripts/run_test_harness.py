#!/usr/bin/env python3
import argparse
import os
import shutil
import signal
import subprocess
import sys
import time
from typing import Any, List, Optional

# Auto-reexec with local .venv python if current interpreter lacks dependencies
WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
VENV_PYTHON = os.path.join(WORKSPACE_ROOT, ".venv", "bin", "python")
if os.path.isfile(VENV_PYTHON) and sys.executable != VENV_PYTHON:
    try:
        import pydantic  # noqa: F401
    except ImportError:
        os.execv(VENV_PYTHON, [VENV_PYTHON] + sys.argv)

sys.path.insert(0, WORKSPACE_ROOT)

from tests.harness.scenarios import AVAILABLE_SCENARIOS, ScenarioManager


def run_cmd(cmd: List[str], check: bool = True, capture: bool = False) -> subprocess.CompletedProcess:
    """Helper to run a system command."""
    return subprocess.run(cmd, check=check, capture_output=capture, text=True)


class TestHarnessOrchestrator:
    """Orchestrates Docker Compose multi-node test harness execution."""

    def __init__(self, compose_file: str, workspace_root: str) -> None:
        self.compose_file = compose_file
        self.workspace_root = workspace_root
        self.staged_config_dir = os.path.join(workspace_root, "test-harness", "staged-config")
        self.scenario_manager = ScenarioManager(base_dir=workspace_root)

    def _compose_cmd(self, extra_args: List[str]) -> List[str]:
        return ["docker", "compose", "-f", self.compose_file] + extra_args

    def stage_scenario(self, scenario_name: str) -> None:
        """Stages scenario YAML configurations for container volume mounting."""
        print(f"[TEST-HARNESS] Staging deployment scenario: '{scenario_name}'...")
        if os.path.exists(self.staged_config_dir):
            shutil.rmtree(self.staged_config_dir)
        os.makedirs(self.staged_config_dir, exist_ok=True)
        self.scenario_manager.stage_scenario_config(scenario_name, self.staged_config_dir)
        print(f"[TEST-HARNESS] Staged configs copied to {self.staged_config_dir}")

    def build_images(self) -> None:
        """Builds all docker images defined in the compose file."""
        deb_script = os.path.join(self.workspace_root, "scripts", "build-all-debs.sh")
        if os.path.isfile(deb_script):
            print("[TEST-HARNESS] Building latest RoostOS Debian packages (.deb)...")
            run_cmd(["bash", deb_script])
        print("[TEST-HARNESS] Building test harness container images with Debian packages...")
        run_cmd(self._compose_cmd(["build"]))

    def start_network(self) -> None:
        """Spins up all background services in detached mode."""
        print("[TEST-HARNESS] Starting container nodes (WAN, Router, LAN, Guest)...")
        run_cmd(self._compose_cmd(["up", "-d", "upstream-wan", "roostos-router", "client-lan", "client-guest"]))
        print("[TEST-HARNESS] Waiting 3 seconds for router daemon and network settling...")
        time.sleep(3)

    def stop_network(self) -> None:
        """Tears down all containers and networks."""
        print("[TEST-HARNESS] Tearing down test harness containers and networks...")
        run_cmd(self._compose_cmd(["down", "--remove-orphans", "-v"]), check=False)

    def run_tests(self, test_filter: Optional[str] = None, pytest_args: Optional[List[str]] = None) -> int:
        """Runs pytest automation suite inside the test-runner container."""
        print("[TEST-HARNESS] Executing Pytest automation suite inside 'test-runner' container...")
        cmd = ["run", "--rm", "test-runner", "pytest", "tests/automation/", "-v"]
        if test_filter:
            cmd.extend(["-k", test_filter])
        if pytest_args:
            cmd.extend(pytest_args)
        
        proc = subprocess.run(self._compose_cmd(cmd))
        return proc.returncode

    def run_interactive(self) -> None:
        """Runs the cluster in interactive mode with Web UI accessible on localhost:8080."""
        print("=" * 70)
        print("  ROOSTOS MULTI-NODE TEST HARNESS - INTERACTIVE MODE")
        print("=" * 70)
        print("  Router Web UI:   http://localhost:8080")
        print("  Default Login:   admin / password")
        print("  WAN Simulator:   172.30.1.100")
        print("  LAN Client:      172.30.2.50  (client-lan)")
        print("  Guest Client:    172.30.3.50  (client-guest)")
        print("-" * 70)
        print("  Press Ctrl+C at any time to shut down the test network.")
        print("=" * 70)

        def sig_handler(signum: int, frame: Optional[Any]) -> None:
            print("\n[TEST-HARNESS] Received shutdown signal. Cleaning up...")
            self.stop_network()
            sys.exit(0)

        signal.signal(signal.SIGINT, sig_handler)
        signal.signal(signal.SIGTERM, sig_handler)

        while True:
            time.sleep(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="RoostOS Multi-Node Test Harness CLI")
    parser.add_argument(
        "--scenario",
        default="default",
        choices=list(AVAILABLE_SCENARIOS.keys()),
        help="Deployment scenario to test (default: 'default')",
    )
    parser.add_argument(
        "--interactive",
        "-i",
        action="store_true",
        help="Spin up nodes and leave running for manual Web UI testing on http://localhost:8080",
    )
    parser.add_argument(
        "--build",
        action="store_true",
        help="Build/rebuild container images before running",
    )
    parser.add_argument(
        "--down",
        action="store_true",
        help="Teardown running test harness containers and exit",
    )
    parser.add_argument(
        "--test",
        "-k",
        type=str,
        default=None,
        help="Filter pytest automation tests by expression (e.g. -k firewall)",
    )
    parser.add_argument(
        "--keep-alive",
        action="store_true",
        help="Do not teardown containers after test run (useful for debugging)",
    )

    args, unknown_pytest_args = parser.parse_known_args()
    compose_path = os.path.join(WORKSPACE_ROOT, "test-harness", "docker-compose.yml")
    orchestrator = TestHarnessOrchestrator(compose_file=compose_path, workspace_root=WORKSPACE_ROOT)

    if args.down:
        orchestrator.stop_network()
        return

    try:
        orchestrator.stage_scenario(args.scenario)
        if args.build:
            orchestrator.build_images()
        orchestrator.start_network()

        if args.interactive:
            orchestrator.run_interactive()
        else:
            exit_code = orchestrator.run_tests(test_filter=args.test, pytest_args=unknown_pytest_args)
            if not args.keep_alive:
                orchestrator.stop_network()
            else:
                print("[TEST-HARNESS] Keeping containers running as requested. Web UI: http://localhost:8080")
            sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n[TEST-HARNESS] Aborted by user.")
        orchestrator.stop_network()
    except Exception as e:
        print(f"\n[TEST-HARNESS] Error: {e}", file=sys.stderr)
        orchestrator.stop_network()
        sys.exit(1)


if __name__ == "__main__":
    main()

import os
import sys
import asyncio
import datetime
import subprocess
from typing import Callable, List, Dict, Any, Set, Optional

from roostos_engine.config import RoostConfig, DeviceConfig
from roostos_engine.state_db import StateDB
from roostos_engine.firewall_manager import FirewallManager
from roostos_engine.scheduler import is_schedule_active, resolve_schedule_targets


class AllowanceTracker:
    """Manages bedtime schedules, daily screen time allowance accumulation, bypasses, and delta firewall sets."""

    def __init__(
        self,
        get_config: Callable[[], RoostConfig],
        get_firewall_manager: Callable[[], FirewallManager],
        state_db: StateDB,
        mock: bool = False,
        on_bypass_expired: Optional[Callable[[str], None]] = None,
    ):
        self.get_config = get_config
        self.get_firewall_manager = get_firewall_manager
        self.state_db = state_db
        self.mock = mock
        self.on_bypass_expired = on_bypass_expired

        self.currently_blocked: Set[str] = set()
        self.allowance_usage: Dict[str, int] = {}  # mac -> seconds used today
        self.temporary_bypasses: List[Dict[str, Any]] = []
        self.nft_call_history: List[List[str]] = []
        self._last_allowance_date = datetime.datetime.now().strftime("%Y-%m-%d")
        self.enforcer_task: Optional[asyncio.Task] = None

    def start_loop(self) -> None:
        """Starts the background scheduler loop task."""
        try:
            coro = self._scheduler_loop()
            self.enforcer_task = asyncio.create_task(coro)
            self.run_scheduler_check()
        except Exception as e:
            coro.close()
            self.enforcer_task = None
            print(f"Warning: Failed to start scheduler enforcer: {e}", file=sys.stderr)

    def stop_loop(self) -> None:
        """Stops the background scheduler enforcer task."""
        if self.enforcer_task:
            self.enforcer_task.cancel()
            self.enforcer_task = None

    async def _scheduler_loop(self) -> None:
        """Periodic enforcer loop running bedtime checkouts and allowance increments."""
        while True:
            try:
                self.run_scheduler_check()
            except Exception as e:
                print(f"Error in background scheduler enforcer loop: {e}", file=sys.stderr)
            await asyncio.sleep(60)

    def execute_system_cmd(self, args: List[str]) -> bool:
        """Executes active firewall or network routing command. Tracks history for tests."""
        self.nft_call_history.append(args)
        print(f"Executing system command: {' '.join(args)}")
        if self.mock or os.getuid() != 0:
            return True
        try:
            subprocess.run(args, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception as e:
            print(f"Error executing command: {e}", file=sys.stderr)
            return False

    def setup_policy_routing(self) -> None:
        """Configures routing tables and rules for policy routing (VPNs)."""
        fm = self.get_firewall_manager()
        cmds = fm.compile_routing_setup_cmds()
        for cmd in cmds:
            self.execute_system_cmd(cmd)

    def grant_time_extension(self, mac: str, duration_seconds: int) -> bool:
        """Grants a temporary time bypass to a client MAC."""
        try:
            norm_mac = DeviceConfig.normalize_mac(mac)
            self.temporary_bypasses = [b for b in self.temporary_bypasses if b["mac"] != norm_mac]
            
            expiry = datetime.datetime.now() + datetime.timedelta(seconds=duration_seconds)
            self.temporary_bypasses.append({
                "mac": norm_mac,
                "expiry": expiry
            })
            print(f"Time extension of {duration_seconds}s granted to MAC: {norm_mac} (expires at {expiry})")
            self.run_scheduler_check()
            return True
        except Exception as e:
            print(f"Error granting extension: {e}", file=sys.stderr)
            return False

    def remove_time_extension(self, mac: str) -> bool:
        """Revokes an active temporary time bypass."""
        try:
            norm_mac = DeviceConfig.normalize_mac(mac)
            self.temporary_bypasses = [b for b in self.temporary_bypasses if b["mac"] != norm_mac]
            if self.on_bypass_expired:
                self.on_bypass_expired(norm_mac)
            self.run_scheduler_check()
            return True
        except Exception as e:
            print(f"Error removing extension: {e}", file=sys.stderr)
            return False

    def run_scheduler_check(self) -> None:
        """Evaluates active bedtimes, daily limits, and temporary bypasses. Emits delta nft updates."""
        config = self.get_config()
        fm = self.get_firewall_manager()
        self.setup_policy_routing()
        now = datetime.datetime.now()
        
        # 1. Evaluate Bypasses
        active_bypasses = set()
        valid_bypasses = []
        for b in self.temporary_bypasses:
            if b["expiry"] > now:
                valid_bypasses.append(b)
                active_bypasses.add(b["mac"])
            else:
                if self.on_bypass_expired:
                    self.on_bypass_expired(b["mac"])
                print(f"Temporary whitelisted bypass expired for MAC: {b['mac']}")
        self.temporary_bypasses = valid_bypasses

        # 2. Check schedules
        blocked_by_schedules: Set[str] = set()
        active_schedules_with_limits = []

        if hasattr(config, "schedules") and config.schedules:
            for sched in config.schedules:
                if is_schedule_active(sched, now):
                    targets = resolve_schedule_targets(sched, config)
                    blocked_by_schedules.update(targets)
                
                if sched.daily_limit is not None:
                    active_schedules_with_limits.append(sched)

        # 3. Check Daily Allowances
        today_str = now.strftime("%Y-%m-%d")
        if self._last_allowance_date != today_str:
            self._last_allowance_date = today_str
            self.allowance_usage.clear()
            print(f"Daily allowance counters reset for new date {today_str}.")

        active_leases = self.state_db.get_active_leases()
        active_macs = {l["mac"] for l in active_leases}

        for sched in active_schedules_with_limits:
            targets = resolve_schedule_targets(sched, config)
            for mac in targets:
                if mac in active_macs:
                    # Accumulate 60 seconds of usage
                    self.allowance_usage[mac] = self.allowance_usage.get(mac, 0) + 60
                
                limit_seconds = sched.daily_limit * 60
                if self.allowance_usage.get(mac, 0) >= limit_seconds:
                    blocked_by_schedules.add(mac)

        # 4. Filter out whitelisted bypasses
        final_blocked = blocked_by_schedules - active_bypasses

        # 5. Delta nft updates
        to_block = final_blocked - self.currently_blocked
        to_unblock = self.currently_blocked - final_blocked

        for mac in to_block:
            self.execute_system_cmd(fm.get_block_mac_cmd(mac))
            self.currently_blocked.add(mac)

        for mac in to_unblock:
            self.execute_system_cmd(fm.get_unblock_mac_cmd(mac))
            self.currently_blocked.remove(mac)

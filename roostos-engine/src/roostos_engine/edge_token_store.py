"""Persistent token and shared secret management for Edge Gateway enrollment."""

import json
import os
import time
from typing import Dict, List, Optional

DEFAULT_FALLBACK_SECRET = "roostos-edge-default-secret-min-32-bytes!!"
_GLOBAL_ACTIVE_TOKENS: Dict[str, float] = {}


def resolve_secret_key(config_dir: str, explicit_key: Optional[str] = None) -> str:
    """Resolves JWT secret key with priority: explicit -> env -> file -> fallback."""
    if explicit_key:
        return explicit_key
    env_secret = os.environ.get("ROOSTOS_JWT_SECRET")
    if env_secret:
        return env_secret

    candidates = [
        os.environ.get("ROOSTOS_JWT_SECRET_FILE"),
        os.path.join(config_dir, "edge_jwt.secret"),
        "/var/lib/roostos/edge_jwt.secret",
        "/etc/roostos/edge_jwt.secret",
    ]
    for sp in candidates:
        if sp and os.path.exists(sp):
            try:
                with open(sp, "r") as f:
                    content = f.read().strip()
                    if content:
                        return content
            except Exception:
                pass

    return DEFAULT_FALLBACK_SECRET


def resolve_state_file(config_dir: str, explicit_file: Optional[str] = None) -> str:
    """Finds best writable persistent path for bootstrap token registry."""
    if explicit_file:
        return explicit_file
    if os.environ.get("ROOSTOS_EDGE_TOKENS_FILE"):
        return os.environ["ROOSTOS_EDGE_TOKENS_FILE"]

    state_dir = os.environ.get("ROOSTOS_STATE_DIR")
    if state_dir:
        return os.path.join(state_dir, "edge_tokens.json")

    candidates = ["/var/lib/roostos", config_dir, "/tmp/roostos"]
    for d in candidates:
        try:
            if os.path.exists(d) and (os.access(d, os.W_OK) or os.getuid() == 0):
                return os.path.join(d, "edge_tokens.json")
            if not os.path.exists(d):
                os.makedirs(d, exist_ok=True)
                return os.path.join(d, "edge_tokens.json")
        except Exception:
            continue

    return "/tmp/roostos/edge_tokens.json"


class EdgeTokenStore:
    """Persistent storage and lifecycle tracking for Edge Gateway bootstrap tokens."""

    def __init__(
        self,
        config_dir: str = "/etc/roostos",
        secret_key: Optional[str] = None,
        state_file: Optional[str] = None,
    ):
        self.config_dir = config_dir
        self.secret_key = resolve_secret_key(config_dir, secret_key)
        self.state_file = resolve_state_file(config_dir, state_file)

    def load_tokens(self) -> Dict[str, float]:
        """Loads unexpired bootstrap tokens from disk and in-memory caches."""
        now = time.time()
        tokens: Dict[str, float] = {}

        dirs_to_check: List[str] = [
            os.path.dirname(self.state_file),
            "/var/lib/roostos",
            self.config_dir,
            "/tmp/roostos",
        ]
        seen_dirs = set()
        for d in dirs_to_check:
            if not d or d in seen_dirs or not os.path.exists(d):
                continue
            seen_dirs.add(d)

            t_file = os.path.join(d, "edge_tokens.json")
            if os.path.exists(t_file):
                try:
                    with open(t_file, "r") as f:
                        data = json.load(f)
                        if isinstance(data, dict):
                            for k, v in data.items():
                                exp = v.get("expires_at", v) if isinstance(v, dict) else v
                                if isinstance(exp, (int, float)) and exp > now:
                                    tokens[k] = float(exp)
                except Exception:
                    pass

            b_file = os.path.join(d, "edge_bootstrap.json")
            if os.path.exists(b_file):
                try:
                    with open(b_file, "r") as f:
                        bdata = json.load(f)
                        jti = bdata.get("jti")
                        exp = bdata.get("expires_at", 0)
                        if jti and isinstance(exp, (int, float)) and exp > now:
                            tokens[jti] = float(exp)
                except Exception:
                    pass

        for k, exp in _GLOBAL_ACTIVE_TOKENS.items():
            if exp > now:
                tokens[k] = exp

        return tokens

    def save_tokens(self, tokens: Dict[str, float]) -> None:
        """Atomically saves active bootstrap tokens to persistent disk store."""
        try:
            os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
            tmp = f"{self.state_file}.tmp.{os.getpid()}"
            with open(tmp, "w") as f:
                json.dump(tokens, f)
            os.replace(tmp, self.state_file)
        except Exception:
            pass

    def record_token(self, jti: str, expires_at: float) -> None:
        """Records a new bootstrap token in memory and on disk."""
        _GLOBAL_ACTIVE_TOKENS[jti] = expires_at
        active = self.load_tokens()
        active[jti] = expires_at
        self.save_tokens(active)

    def consume_token(self, jti: str) -> None:
        """Removes consumed/expired token from memory and persistent files."""
        _GLOBAL_ACTIVE_TOKENS.pop(jti, None)
        active = self.load_tokens()
        active.pop(jti, None)
        self.save_tokens(active)

        for d in [os.path.dirname(self.state_file), "/var/lib/roostos", "/tmp/roostos"]:
            b_file = os.path.join(d, "edge_bootstrap.json")
            if os.path.exists(b_file):
                try:
                    with open(b_file, "r") as f:
                        bdata = json.load(f)
                    if bdata.get("jti") == jti:
                        os.remove(b_file)
                except Exception:
                    pass

import os
import sqlite3
from typing import List, Dict, Any, Optional

class StateDB:
    """Manages the transient SQLite state database cache for active leases and UPnP requests."""
    
    def __init__(self, db_path: str = "/var/lib/roostos/state.db"):
        self.db_path = db_path
        # Ensure parent directories exist
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        self.init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self) -> None:
        """Initializes tables if they do not exist."""
        with self._get_connection() as conn:
            # 1. Create active_leases table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS active_leases (
                    mac TEXT PRIMARY KEY,
                    ip TEXT NOT NULL,
                    hostname TEXT,
                    quarantined INTEGER DEFAULT 1,
                    last_seen DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 2. Create pending_upnp_requests table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS pending_upnp_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    mac TEXT NOT NULL,
                    internal_ip TEXT NOT NULL,
                    external_port INTEGER NOT NULL,
                    internal_port INTEGER NOT NULL,
                    protocol TEXT NOT NULL,
                    description TEXT,
                    requested_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    # ==========================================
    # DHCP Lease Operations
    # ==========================================

    def register_lease(self, mac: str, ip: str, hostname: Optional[str], quarantined: bool = True) -> bool:
        """Upserts a DHCP lease record in the SQLite cache."""
        try:
            with self._get_connection() as conn:
                conn.execute("""
                    INSERT INTO active_leases (mac, ip, hostname, quarantined, last_seen)
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(mac) DO UPDATE SET
                        ip = excluded.ip,
                        hostname = excluded.hostname,
                        quarantined = excluded.quarantined,
                        last_seen = CURRENT_TIMESTAMP
                """, (mac.lower(), ip, hostname, 1 if quarantined else 0))
                conn.commit()
            return True
        except Exception as e:
            print(f"Error caching lease in SQLite: {e}")
            return False

    def release_lease(self, mac: str) -> bool:
        """Deletes a DHCP lease record when released or expired."""
        try:
            with self._get_connection() as conn:
                conn.execute("DELETE FROM active_leases WHERE mac = ?", (mac.lower(),))
                conn.commit()
            return True
        except Exception as e:
            print(f"Error releasing lease from SQLite: {e}")
            return False

    def get_active_leases(self) -> List[Dict[str, Any]]:
        """Returns all currently active lease records."""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("SELECT mac, ip, hostname, quarantined, last_seen FROM active_leases")
                return [
                    {
                        "mac": row["mac"],
                        "ip": row["ip"],
                        "hostname": row["hostname"],
                        "quarantined": bool(row["quarantined"]),
                        "last_seen": row["last_seen"]
                    }
                    for row in cursor.fetchall()
                ]
        except Exception as e:
            print(f"Error fetching active leases from SQLite: {e}")
            return []

    # ==========================================
    # UPnP Gateway Operations
    # ==========================================

    def add_pending_upnp(self, mac: str, internal_ip: str, ext_port: int, int_port: int, protocol: str, description: Optional[str]) -> int:
        """Adds a pending UPnP request to the staging queue."""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("""
                    INSERT INTO pending_upnp_requests (mac, internal_ip, external_port, internal_port, protocol, description)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (mac.lower(), internal_ip, ext_port, int_port, protocol.lower(), description))
                conn.commit()
                return cursor.lastrowid or 0
        except Exception as e:
            print(f"Error queuing UPnP request in SQLite: {e}")
            return 0

    def get_pending_upnp(self) -> List[Dict[str, Any]]:
        """Returns all currently queued UPnP requests."""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("SELECT mac, internal_ip, external_port, internal_port, protocol, description FROM pending_upnp_requests")
                return [
                    {
                        "mac": row["mac"],
                        "internal_ip": row["internal_ip"],
                        "port": row["external_port"],
                        "internal_port": row["internal_port"],
                        "protocol": row["protocol"],
                        "description": row["description"]
                    }
                    for row in cursor.fetchall()
                ]
        except Exception as e:
            print(f"Error fetching pending UPnP requests: {e}")
            return []

    def remove_pending_upnp(self, mac: str, port: int, protocol: str) -> bool:
        """Deletes a staged UPnP request from the queue once processed."""
        try:
            with self._get_connection() as conn:
                conn.execute("""
                    DELETE FROM pending_upnp_requests 
                    WHERE mac = ? AND external_port = ? AND protocol = ?
                """, (mac.lower(), port, protocol.lower()))
                conn.commit()
            return True
        except Exception as e:
            print(f"Error deleting UPnP request from SQLite: {e}")
            return False

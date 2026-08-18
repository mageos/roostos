import asyncio
import sys
import os
import json
import logging
import click
import socket
from dbus_next.aio import MessageBus
from dbus_next import BusType
import paho.mqtt.client as mqtt

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("roostos-timeguardd")

STATE_FILE = "/var/lib/roostos-timeguardd/state.json"
CONFIG_FILE = "/etc/roostos-timeguardd/config.json"

def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to read {path}: {e}")
    return default

def save_json(path, data):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to write {path}: {e}")

class TimeGuardDaemon:
    def __init__(self):
        self.config = load_json(CONFIG_FILE, {
            "mqtt_host": "roostos.local",
            "mqtt_port": 1883,
            "mqtt_user": "",
            "mqtt_pass": "",
            "users": {
                "demo-user": {
                    "daily_limit_seconds": 3600,  # 1 hour
                }
            }
        })
        self.state = load_json(STATE_FILE, {
            "users": {
                "demo-user": {
                    "remaining_seconds": 3600,
                    "last_reset_day": ""
                }
            }
        })
        self.hostname = socket.gethostname()
        self.running = True
        self.mqtt_connected = False
        self.setup_mqtt()

    def setup_mqtt(self):
        self.mqtt_client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
        
        ca_cert = self.config.get("ca_cert") or "/etc/roostos-timeguardd/certs/ca.crt"
        certfile = self.config.get("client_cert") or "/etc/roostos-timeguardd/certs/client.crt"
        keyfile = self.config.get("client_key") or "/etc/roostos-timeguardd/certs/client.key"
        
        if os.path.exists(ca_cert) and os.path.exists(certfile) and os.path.exists(keyfile):
            try:
                self.mqtt_client.tls_set(ca_certs=ca_cert, certfile=certfile, keyfile=keyfile)
                logger.info("Configured mTLS for MQTT using client certificate.")
            except Exception as e:
                logger.warning(f"Failed to configure MQTT mTLS: {e}")
        elif self.config.get("mqtt_user") and self.config.get("mqtt_pass"):
            self.mqtt_client.username_pw_set(self.config["mqtt_user"], self.config["mqtt_pass"])
        
        self.mqtt_client.on_connect = self.on_mqtt_connect
        self.mqtt_client.on_disconnect = self.on_mqtt_disconnect
        self.mqtt_client.on_message = self.on_mqtt_message

    def on_mqtt_connect(self, client, userdata, flags, rc, properties=None):
        logger.info("Connected to MQTT Broker")
        self.mqtt_connected = True
        # Subscribe to user limit updates
        for username in self.config.get("users", {}):
            topic = f"roostos/timeguard/limits/{username}"
            client.subscribe(topic)
            logger.info(f"Subscribed to topic: {topic}")

    def on_mqtt_disconnect(self, client, userdata, disconnect_flags, rc, properties=None):
        logger.warning("Disconnected from MQTT Broker. Falling back to local offline mode.")
        self.mqtt_connected = False

    def on_mqtt_message(self, client, userdata, msg):
        try:
            topic_parts = msg.topic.split('/')
            username = topic_parts[-1]
            payload = json.loads(msg.payload.decode('utf-8'))
            if "remaining_seconds" in payload:
                rem = payload["remaining_seconds"]
                if username in self.state["users"]:
                    logger.info(f"Received sync for {username}: remaining_seconds={rem}")
                    self.state["users"][username]["remaining_seconds"] = rem
                    save_json(STATE_FILE, self.state)
        except Exception as e:
            logger.error(f"Failed to process MQTT message: {e}")

    async def get_active_users(self):
        """Query systemd-logind to find currently active local human users."""
        active_users = set()
        try:
            bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
            introspection = await bus.introspect("org.freedesktop.login1", "/org/freedesktop/login1")
            obj = bus.get_proxy_object("org.freedesktop.login1", "/org/freedesktop/login1", introspection)
            manager = obj.get_interface("org.freedesktop.login1.Manager")
            
            sessions = await manager.call_list_sessions()
            for session_id, uid, username, seat, active in sessions:
                if active:
                    if uid >= 1000:
                        active_users.add(username)
            await bus.disconnect()
        except Exception as e:
            logger.error(f"Error querying systemd-logind: {e}")
        return active_users

    async def lock_user_sessions(self, username):
        """Lock all active sessions for a user using loginctl."""
        logger.warning(f"Locking sessions for user: {username} (time limit reached)")
        try:
            proc = await asyncio.create_subprocess_exec(
                "loginctl", "lock-sessions",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await proc.communicate()
        except Exception as e:
            logger.error(f"Failed to lock sessions: {e}")

    async def run(self):
        logger.info("TimeGuard Daemon started")
        # Start MQTT loop in a background thread
        host = self.config.get("mqtt_host", "roostos.local")
        port = self.config.get("mqtt_port", 1883)
        try:
            self.mqtt_client.connect_async(host, port, 60)
            self.mqtt_client.loop_start()
        except Exception as e:
            logger.error(f"Initial MQTT connection failed: {e}. Starting in offline mode.")

        while self.running:
            try:
                active_users = await self.get_active_users()
                import datetime
                today_str = datetime.date.today().isoformat()

                for username, user_config in self.config.get("users", {}).items():
                    if username not in self.state["users"]:
                        self.state["users"][username] = {
                            "remaining_seconds": user_config.get("daily_limit_seconds", 3600),
                            "last_reset_day": today_str
                        }

                    ustate = self.state["users"][username]

                    # Reset daily limit if a new day starts
                    if ustate.get("last_reset_day") != today_str:
                        logger.info(f"New day detected. Resetting time limit for {username}")
                        ustate["remaining_seconds"] = user_config.get("daily_limit_seconds", 3600)
                        ustate["last_reset_day"] = today_str

                    if username in active_users:
                        # Decrement remaining time locally
                        if ustate["remaining_seconds"] > 0:
                            ustate["remaining_seconds"] = max(0, ustate["remaining_seconds"] - 30)
                            logger.info(f"User {username} is active. Remaining time: {ustate['remaining_seconds']}s")
                        
                        # Publish heartbeat if connected
                        if self.mqtt_connected:
                            try:
                                payload = {
                                    "hostname": self.hostname,
                                    "active_seconds": 30,
                                    "remaining_seconds": ustate["remaining_seconds"]
                                }
                                self.mqtt_client.publish(
                                    f"roostos/timeguard/heartbeat/{username}",
                                    json.dumps(payload),
                                    qos=1
                                )
                            except Exception as e:
                                logger.error(f"Failed to publish heartbeat: {e}")

                        if ustate["remaining_seconds"] <= 0:
                            await self.lock_user_sessions(username)

                save_json(STATE_FILE, self.state)
            except Exception as e:
                logger.error(f"Error in main daemon loop: {e}")
            await asyncio.sleep(30)

        self.mqtt_client.loop_stop()
        self.mqtt_client.disconnect()

@click.group()
def main():
    pass

@main.command()
def start():
    """Start the background monitoring daemon."""
    daemon = TimeGuardDaemon()
    try:
        asyncio.run(daemon.run())
    except KeyboardInterrupt:
        logger.info("Daemon stopped by user")

@main.command()
@click.argument("username")
def pam_check(username):
    """Called by pam_exec to verify if a user has remaining screen time."""
    config = load_json(CONFIG_FILE, {})
    state = load_json(STATE_FILE, {})
    
    if username not in config.get("users", {}):
        sys.exit(0)
        
    ustate = state.get("users", {}).get(username, {})
    remaining = ustate.get("remaining_seconds", 3600)
    
    if remaining <= 0:
        print(f"Screen time limit reached for today. Access Denied.", file=sys.stderr)
        sys.exit(1)
        
    sys.exit(0)

if __name__ == "__main__":
    main()

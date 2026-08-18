import os
import sys
import shutil
from roostos_engine.subsystems.base import Subsystem

class PluginsSyncSubsystem(Subsystem):
    name = "plugins"
    dependencies = ["network"]
    run_on_init = False  # Only runs on reload_config

    def update(self) -> None:
        # For local plugin development: sync local ui.js assets directly if they exist
        local_plugins_dir = "/home/matt/source/github/mageos/roostos/plugins"
        if os.path.isdir(local_plugins_dir):
            for plugin in self.config.plugins:
                local_ui_file = os.path.join(local_plugins_dir, plugin.id, "ui.js")
                if os.path.isfile(local_ui_file):
                    assets_dir = os.environ.get("ROOSTOS_WEB_ASSETS", "/usr/share/roostos/web")
                    dest_dir = os.path.join(assets_dir, "plugins", plugin.id)
                    dest_file = os.path.join(dest_dir, "ui.js")
                    try:
                        os.makedirs(dest_dir, exist_ok=True)
                        shutil.copy2(local_ui_file, dest_file)
                        print(f"Developer sync: Copied local plugin UI for {plugin.id} to {dest_file}")
                    except Exception as e:
                        print(f"Failed to sync local UI file for {plugin.id}: {e}", file=sys.stderr)

        # Synchronize Docker containers for enabled plugins
        try:
            import docker
            client = docker.from_env()
        except Exception as e:
            print(f"Warning: Failed to initialize Docker client: {e}", file=sys.stderr)
            return

        # 1. Get currently running roostos containers
        try:
            existing_containers = client.containers.list(all=True, filters={"label": "org.roostos.managed=true"})
        except Exception as e:
            print(f"Warning: Failed to list Docker containers: {e}", file=sys.stderr)
            return

        # Compile list of active/desired plugins
        active_plugins = {p.id: p for p in self.config.plugins if p.enabled}
        
        # Stop and remove containers for disabled plugins
        for container in existing_containers:
            plugin_id = container.labels.get("org.roostos.plugin_id")
            if plugin_id not in active_plugins:
                print(f"Stopping and removing container: {container.name}")
                try:
                    container.stop(timeout=5)
                    container.remove(force=True)
                except Exception as e:
                    print(f"Failed to remove container {container.name}: {e}", file=sys.stderr)

        # Start desired plugin containers
        for plugin_id, plugin in active_plugins.items():
            for c_cfg in plugin.containers:
                container_name = f"roostos-plugin-{plugin_id}-{c_cfg.name}"
                
                # Check if it already exists and is running
                running_container = next((c for c in existing_containers if c.name == container_name), None)
                if running_container:
                    if running_container.status != "running":
                        try:
                            running_container.start()
                        except Exception as e:
                            print(f"Failed to start container {container_name}: {e}", file=sys.stderr)
                    continue

                # Prepare port bindings
                ports_dict = {}
                for p in c_cfg.ports:
                    ports_dict[f"{p.container_port}/{p.protocol}"] = p.host_port

                # Prepare volumes
                volumes_dict = {}
                for v in c_cfg.volumes:
                    volumes_dict[v.host_path] = {"bind": v.container_path, "mode": v.mode}

                # Automatically mount D-Bus socket for the container to interact with the host system/session bus
                dbus_addr = os.environ.get("DBUS_SESSION_BUS_ADDRESS")
                container_env = c_cfg.environment.copy()
                if dbus_addr:
                    container_env["DBUS_SESSION_BUS_ADDRESS"] = dbus_addr
                    if "path=" in dbus_addr:
                        parts = dbus_addr.split("path=")
                        socket_path = parts[1].split(",")[0]
                        if os.path.exists(socket_path):
                            volumes_dict[socket_path] = {"bind": socket_path, "mode": "rw"}
                else:
                    system_socket = "/var/run/dbus/system_bus_socket"
                    if os.path.exists(system_socket):
                        volumes_dict[system_socket] = {"bind": system_socket, "mode": "rw"}

                # Automatically issue and mount mTLS client certificate for plugin container
                if hasattr(self.daemon, "cert_manager"):
                    try:
                        requested_scopes = getattr(plugin, "requested_scopes", [])
                        self.daemon.cert_manager.issue_plugin_cert(plugin_id, requested_scopes)
                        plugin_cert_dir = os.path.join(self.daemon.cert_manager.plugins_cert_dir, plugin_id)
                        if os.path.exists(plugin_cert_dir):
                            volumes_dict[plugin_cert_dir] = {"bind": "/etc/roostos/certs", "mode": "ro"}
                    except Exception as e:
                        print(f"Warning: Failed to issue cert for plugin {plugin_id}: {e}", file=sys.stderr)

                 # Start the container
                image_name = c_cfg.image
                registry = getattr(self.config.system, "docker_registry", None)
                if registry:
                    if "/" in image_name:
                        first_part = image_name.split("/")[0]
                        if "." in first_part or ":" in first_part or first_part == "localhost":
                            image_name = registry.rstrip("/") + "/" + "/".join(image_name.split("/")[1:])
                        else:
                            image_name = f"{registry.rstrip('/')}/{image_name}"
                    else:
                        image_name = f"{registry.rstrip('/')}/{image_name}"

                print(f"Starting plugin container: {container_name} ({image_name})")
                try:
                    client.containers.run(
                        image_name,
                        name=container_name,
                        detach=True,
                        ports=ports_dict if plugin.network_mode != "host" else None,
                        volumes=volumes_dict,
                        environment=container_env,
                        network_mode=plugin.network_mode,
                        labels={
                            "org.roostos.managed": "true",
                            "org.roostos.plugin_id": plugin_id
                        },
                        restart_policy={"Name": "unless-stopped"}
                    )
                except Exception as e:
                    print(f"Failed to run container {container_name}: {e}", file=sys.stderr)

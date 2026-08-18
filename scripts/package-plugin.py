#!/usr/bin/env python3
import os
import sys
import zipfile
import argparse

def package_plugin(plugin_name, plugins_dir, dist_dir):
    plugin_path = os.path.join(plugins_dir, plugin_name)
    if not os.path.isdir(plugin_path):
        print(f"Error: Plugin directory '{plugin_path}' does not exist.")
        return False

    manifest_name = None
    for name in ("roostos-pod.yaml", "roostos-pod.yml", "manifest.yaml", "manifest.yml"):
        if os.path.exists(os.path.join(plugin_path, name)):
            manifest_name = name
            break

    if not manifest_name:
        print(f"Error: No roostos-pod.yaml manifest found in '{plugin_path}'")
        return False

    zip_filename = os.path.join(dist_dir, f"{plugin_name}.zip")
    print(f"Packaging plugin '{plugin_name}' -> {zip_filename}...")

    with zipfile.ZipFile(zip_filename, "w", zipfile.ZIP_DEFLATED) as zipf:
        # Add manifest
        manifest_path = os.path.join(plugin_path, manifest_name)
        zipf.write(manifest_path, manifest_name)
        print(f"  Added: {manifest_name}")

        # Add UI script if it exists
        ui_path = os.path.join(plugin_path, "ui.js")
        if os.path.exists(ui_path):
            zipf.write(ui_path, "ui.js")
            print("  Added: ui.js")
            
    print(f"Success! Packaged '{plugin_name}' successfully.")
    return True

def main():
    parser = argparse.ArgumentParser(description="Package RoostOS plugins into deployable ZIP archives.")
    parser.add_argument("plugin", nargs="?", help="Specific plugin directory name to package (e.g. wireguard)")
    args = parser.parse_args()

    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    plugins_dir = os.path.join(project_root, "plugins")
    dist_dir = os.path.join(project_root, "dist")

    os.makedirs(dist_dir, exist_ok=True)

    if args.plugin:
        success = package_plugin(args.plugin, plugins_dir, dist_dir)
        sys.exit(0 if success else 1)
    else:
        if not os.path.exists(plugins_dir):
            print(f"Error: Plugins directory not found at {plugins_dir}")
            sys.exit(1)
        
        plugins = [d for d in os.listdir(plugins_dir) if os.path.isdir(os.path.join(plugins_dir, d))]
        if not plugins:
            print("No plugins found to package.")
            sys.exit(0)

        success_count = 0
        for p in plugins:
            if package_plugin(p, plugins_dir, dist_dir):
                success_count += 1

        print(f"\nCompleted! Packaged {success_count} / {len(plugins)} plugins.")

if __name__ == "__main__":
    main()

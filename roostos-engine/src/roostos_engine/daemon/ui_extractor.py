import os
import sys
import io
import tarfile
from typing import Optional


def extract_plugin_ui(
    image_name: str,
    ui_entrypoint: str,
    plugin_id: str,
    docker_registry: Optional[str] = None
) -> bool:
    """Pulls the specified image, extracts the ui_entrypoint file, and saves it to the host static folder."""
    try:
        import docker
        client = docker.from_env()
    except Exception as e:
        raise Exception(f"Docker client error: {e}")

    if docker_registry:
        if "/" in image_name:
            first_part = image_name.split("/")[0]
            if "." in first_part or ":" in first_part or first_part == "localhost":
                image_name = docker_registry.rstrip("/") + "/" + "/".join(image_name.split("/")[1:])
            else:
                image_name = f"{docker_registry.rstrip('/')}/{image_name}"
        else:
            image_name = f"{docker_registry.rstrip('/')}/{image_name}"

    try:
        print(f"Pulling image for UI extraction: {image_name}")
        client.images.pull(image_name)
    except Exception as e:
        raise Exception(f"Image pull failed: {e}")

    temp_container = None
    try:
        temp_container = client.containers.create(image_name)
        stream, _ = temp_container.get_archive(ui_entrypoint)
        file_data = b"".join(stream)
        
        tar = tarfile.open(fileobj=io.BytesIO(file_data))
        member = tar.next()
        if not member:
            raise Exception("Empty UI tar stream from container")
        
        extracted_file = tar.extractfile(member)
        if not extracted_file:
            raise Exception("Failed to extract UI content from tar member")
        ui_content = extracted_file.read()
        
        assets_dir = os.environ.get("ROOSTOS_WEB_ASSETS", "/usr/share/roostos/web")
        dest_dir = os.path.join(assets_dir, "plugins", plugin_id)
        os.makedirs(dest_dir, exist_ok=True)
        
        dest_file = os.path.join(dest_dir, "ui.js")
        with open(dest_file, "wb") as f:
            f.write(ui_content)
            
        print(f"Successfully extracted plugin UI script for {plugin_id} to {dest_file}")
        return True
    except Exception as e:
        print(f"Error during UI extraction: {e}", file=sys.stderr)
        raise Exception(f"Extraction failed: {e}")
    finally:
        if temp_container:
            try:
                temp_container.remove(force=True)
            except Exception:
                pass

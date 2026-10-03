"""FastAPI router for Docker daemon image inspection and archive uploads."""

import os
import tempfile
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File

from roostos_web.auth import get_current_admin, get_current_user, UserSession

images_router = APIRouter(tags=["catalog-images"])


@images_router.post("/images/load")
async def load_local_docker_image(
    file: UploadFile = File(...),
    current_user: UserSession = Depends(get_current_admin),
) -> Dict[str, Any]:
    """Loads a container image from an uploaded .tar archive directly into the local Docker daemon."""
    try:
        import docker
        client = docker.from_env()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Docker service unavailable: {e}")

    contents = await file.read()
    with tempfile.NamedTemporaryFile(suffix=".tar", delete=False) as tmp:
        tmp.write(contents)
        tmp_path = tmp.name

    try:
        with open(tmp_path, "rb") as f:
            images = client.images.load(f.read())
        loaded_tags = [tag for img in images for tag in img.tags]
        return {
            "success": True,
            "message": f"Loaded {len(images)} image(s) into local cache.",
            "loaded_tags": loaded_tags or ["(untagged)"],
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to load image archive: {e}")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


@images_router.get("/images")
async def list_local_docker_images(
    current_user: UserSession = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    """Lists Docker container images available in the local daemon cache."""
    try:
        import docker
        client = docker.from_env()
        images = client.images.list()
        return [
            {
                "id": img.short_id,
                "tags": img.tags,
                "size_mb": round(img.attrs.get("Size", 0) / (1024 * 1024), 1),
                "created": img.attrs.get("Created", ""),
            }
            for img in images
        ]
    except Exception:
        return []

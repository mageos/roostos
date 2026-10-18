"""Unit test to verify UI static assets and ES module graph integrity."""

from pathlib import Path
import re
from fastapi.testclient import TestClient

from roostos_web.main import app


def test_ui_index_html_served():
    client = TestClient(app)
    resp = client.get("/")
    assert resp.status_code == 200
    assert "RoostOS" in resp.text
    assert 'href="css/shell.css"' in resp.text
    assert 'href="css/concept1.css"' in resp.text
    assert 'src="js/app.js"' in resp.text


def test_es_module_import_integrity():
    """Verifies that all relative imports in roostos-ui/js/ resolve to existing files."""
    ui_dir = Path(__file__).parent.parent.parent.parent / "roostos-ui"
    js_dir = ui_dir / "js"
    assert js_dir.is_dir()

    import_pattern = re.compile(r"""(?:import|export)\s+(?:.*?from\s+)?['"](\.[^'"]+)['"]""")

    missing_imports = []
    for js_file in js_dir.rglob("*.js"):
        content = js_file.read_text(encoding="utf-8")
        for match in import_pattern.finditer(content):
            rel_path = match.group(1)
            target = (js_file.parent / rel_path).resolve()
            if not target.exists() and not (target.with_suffix(".js")).exists():
                missing_imports.append((str(js_file.relative_to(ui_dir)), rel_path))

    assert not missing_imports, f"Found unresolved imports: {missing_imports}"


def test_static_asset_routes():
    """Verifies critical static CSS and JS routes return 200 OK."""
    client = TestClient(app)
    critical_paths = [
        "/css/base.css",
        "/css/components.css",
        "/css/shell.css",
        "/css/concept1.css",
        "/js/app.js",
        "/js/state.js",
        "/js/state-actions.js",
        "/js/state-sync.js",
        "/js/api.js",
        "/js/data.js",
        "/js/concept1/c1-household-home.js",
        "/js/concept1/c1-household-devices.js",
        "/js/concept1/c1-admin-dhcp.js",
        "/js/concept1/c1-admin-apps.js",
        "/js/concept1/c1-admin-app-sources.js",
        "/js/concept1/c1-admin-edge-peers.js",
    ]
    for p in critical_paths:
        res = client.get(p)
        assert res.status_code == 200, f"Path {p} failed with {res.status_code}"

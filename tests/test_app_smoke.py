from app.main import app


def test_app_registers_core_routes():
    paths = {route.path for route in app.routes}
    assert "/health" in paths
    assert "/login" in paths
    assert "/kid" in paths
    assert "/admin" in paths
    assert "/admin/users" in paths
    assert "/admin/import" in paths
    assert "/admin/import/template.csv" in paths


def test_static_and_template_mounts_exist():
    names = {route.name for route in app.routes}
    assert "static" in names

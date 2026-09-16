from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def test_static_png_fallback_and_invalid_spec(tmp_path):
    with TestClient(create_app(Settings(dataset_dir=tmp_path))) as client:
        response = client.post("/api/v1/charts/png", json={"option": {
            "title": {"text": "Sales"}, "xAxis": {"data": ["A", "B"]},
            "series": [{"type": "bar", "data": [10, 20]}],
        }})
        assert response.status_code == 200, response.text[:200]
        assert response.content.startswith(b"\x89PNG\r\n\x1a\n")
        assert response.headers["content-type"] == "image/png"
        assert client.post("/api/v1/charts/png", json={"option": {"series": []}}).status_code == 422

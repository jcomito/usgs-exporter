import pytest
from unittest.mock import patch
from app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


@patch("app.fetch_usgs")
def test_metrics_endpoint(mock_fetch_usgs, client):
    # Mock the fetch_usgs function to avoid making real API calls
    mock_fetch_usgs.return_value = None

    response = client.get("/metrics")
    assert response.status_code == 200
    assert response.mimetype == "text/plain"


@patch("app.fetch_usgs")
def test_home_endpoint(mock_fetch_usgs, client):
    response = client.get("/")
    assert response.status_code == 200
    assert "USGS Exporter is running for site" in response.data.decode("utf-8")

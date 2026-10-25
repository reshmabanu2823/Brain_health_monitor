"""Automated tests for CORTIA Insights Explainable AI Centre."""
import json
import pytest
from fastapi.testclient import TestClient
from server import app
from app.logger import log_result


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_insights_overview(client):
    res = client.get("/api/insights/overview")
    assert res.status_code == 200
    data = res.json()
    assert "workspace" in data
    assert "mri_status" in data
    assert "eeg_status" in data
    assert data["eeg_status"]["model_installed"] is False
    assert "Maker UNO" in data["eeg_status"]["hardware_scope"]
    assert "disclaimer" in data


def test_insights_performance_records(client):
    res = client.get("/api/insights/performance")
    assert res.status_code == 200
    data = res.json()
    assert "mri" in data
    assert "eeg" in data

    # Verify MRI evaluation contains real metrics if candidate is loaded
    mri = data["mri"]
    if mri.get("available"):
        assert mri["sample_count"] == 234
        assert 0.90 <= mri["accuracy"] <= 1.0
        assert "glioma_tumor" in mri["per_class"]
        assert len(mri["confusion_matrix"]) == 4

    # Verify EEG evaluation is explicitly unavailable without fabrication
    eeg = data["eeg"]
    assert eeg["available"] is False
    assert "No trained EEG classification model" in eeg["reason"]
    assert len(eeg["feasibility_boundaries"]) >= 3


def test_insights_mri_latest_and_by_id(client):
    # Seed a verified scan
    scan_id = log_result(
        image_path="test_insights_scan.png",
        label="Glioma",
        confidence=94.5,
        probabilities={"Glioma": 94.5, "Meningioma": 2.5, "No Tumor": 1.0, "Pituitary": 2.0},
        tumor_area_pct=8.45,
        peak_saliency=0.9124,
    )

    # Test latest scan
    res = client.get("/api/insights/mri/latest")
    assert res.status_code == 200
    latest = res.json()
    assert latest["scan_id"] == scan_id
    assert latest["predicted_label"] == "Glioma"
    assert latest["confidence"] == 94.5
    assert latest["is_tumor"] is True
    assert latest["metrics"]["tumor_area_pct"] == 8.45
    assert latest["metrics"]["peak_saliency"] == 0.9124
    assert latest["explanation_available"] is True

    # Test specific scan by ID
    res_id = client.get(f"/api/insights/mri/{scan_id}")
    assert res_id.status_code == 200
    scan_by_id = res_id.json()
    assert scan_by_id["scan_id"] == scan_id


def test_insights_mri_missing_id_returns_404(client):
    res = client.get("/api/insights/mri/999999999")
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


def test_insights_history_filtering(client):
    res_all = client.get("/api/insights/history?limit=20&type=all")
    assert res_all.status_code == 200
    all_items = res_all.json()
    assert isinstance(all_items, list)

    res_mri = client.get("/api/insights/history?limit=20&type=mri")
    assert res_mri.status_code == 200
    mri_items = res_mri.json()
    assert all(i["type"] == "mri" for i in mri_items)


def test_insights_eeg_missing_id_returns_404(client):
    res = client.get("/api/insights/eeg/non_existent_session_id")
    assert res.status_code == 404

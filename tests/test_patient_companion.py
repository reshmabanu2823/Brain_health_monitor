"""Automated tests for Patient & Everyday Companion features."""
import pytest
from app.patient_companion import get_patient_mri_companion, get_mind_calmness_metrics
from fastapi.testclient import TestClient
from server import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_plain_english_tumor_explanations():
    for label in ["Glioma", "Meningioma", "Pituitary", "No Tumor"]:
        data = get_patient_mri_companion(label=label, confidence=92.5, tumor_area_pct=6.5)
        assert data["finding_title"] is not None
        assert len(data["summary"]) > 50
        assert len(data["doctor_questions"]) >= 4
        assert "important_reminder" in data
        assert "physician" in data["important_reminder"].lower() or "doctor" in data["important_reminder"].lower()

        # Check that questions are relevant
        for q in data["doctor_questions"]:
            assert len(q) > 15


def test_mind_calmness_high_alpha():
    # Simulate high alpha (calm state)
    features = {"relative_alpha_power": {"mean": 38.0}}
    res = get_mind_calmness_metrics(features, quality_state="Acceptable")
    assert res["calmness_score"] >= 70
    assert "Calm" in res["calmness_level"]
    assert res["color"] == "#188038"


def test_mind_calmness_low_alpha():
    # Simulate low alpha (active thinking/stress)
    features = {"relative_alpha_power": {"mean": 12.0}}
    res = get_mind_calmness_metrics(features, quality_state="Acceptable")
    assert res["calmness_score"] < 45
    assert "Active" in res["calmness_level"]


def test_mind_calmness_insufficient_quality():
    # Simulate bad electrode connection
    features = {"relative_alpha_power": {"mean": 30.0}}
    res = get_mind_calmness_metrics(features, quality_state="Insufficient quality")
    assert res["calmness_score"] == 0
    assert "adjustment" in res["sensor_fit"].lower() or "loose" in res["sensor_fit"].lower()


def test_insights_mri_has_patient_companion(client):
    res = client.get("/api/insights/mri/latest")
    if res.status_code == 200:
        data = res.json()
        assert "patient_companion" in data
        companion = data["patient_companion"]
        assert "finding_title" in companion
        assert len(companion["doctor_questions"]) >= 4

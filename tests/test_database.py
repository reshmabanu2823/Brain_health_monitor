import pytest
from fastapi.testclient import TestClient
import database
from main import app as main_app


@pytest.fixture
def db_isolated(tmp_path, monkeypatch):
    test_db = tmp_path / "test_cortia_ai.db"
    monkeypatch.setattr(database, "DB_PATH", test_db)
    monkeypatch.setenv("BHM_CORTIA_DB", str(test_db))
    database.init_db()
    return test_db


def test_database_crud(db_isolated):
    # MRI scans CRUD
    scan_id = database.insert_mri_scan(
        file_identifier="scan_sample.dcm",
        classification="Glioma",
        confidence=0.965,
        diagnostic_flag="POS",
        saliency_peak=0.89,
        saliency_area=14.5,
        saliency_center_x=110.0,
        saliency_center_y=95.0,
    )
    assert scan_id is not None
    scans = database.get_mri_scans(limit=10)
    assert len(scans) == 1
    assert scans[0]["id"] == scan_id
    assert scans[0]["classification"] == "Glioma"
    assert scans[0]["diagnostic_flag"] == "POS"

    single = database.get_mri_scan(scan_id)
    assert single is not None
    assert single["file_identifier"] == "scan_sample.dcm"

    # EEG session CRUD
    sess_id = database.start_eeg_session(source="SIMULATED", notes="Baseline run")
    assert sess_id is not None
    sess_list = database.get_eeg_sessions(limit=10)
    assert len(sess_list) == 1
    assert sess_list[0]["status"] == "recording"

    database.end_eeg_session(
        session_id=sess_id,
        duration_seconds=30.0,
        total_samples=7500,
        signal_quality="Acceptable",
        features_json='{"alpha_power": 12.3}',
    )
    sess_done = database.get_eeg_session(sess_id)
    assert sess_done["status"] == "completed"
    assert sess_done["total_samples"] == 7500

    # AI Conversations & Messages CRUD
    conv_id = database.create_conversation(title="Test Consultation", provider="local")
    assert conv_id is not None
    convs = database.get_conversations(limit=10)
    assert any(c["id"] == conv_id for c in convs)

    database.update_conversation_title(conv_id, "Updated Consultation Title")
    convs_updated = database.get_conversations(limit=10)
    assert any(c["title"] == "Updated Consultation Title" for c in convs_updated)

    msg1 = database.insert_message(conv_id, "user", "What is glioma?", ["Citation 1"])
    msg2 = database.insert_message(conv_id, "assistant", "Glioma is a primary brain tumor.", ["Citation 2"])
    assert msg1 is not None
    assert msg2 is not None

    msgs = database.get_messages(conv_id)
    assert len(msgs) == 2
    assert msgs[0]["content"] == "What is glioma?"
    assert msgs[1]["citations"] == ["Citation 2"]

    database.delete_message(msg1)
    msgs_after = database.get_messages(conv_id)
    assert len(msgs_after) == 1

    database.delete_conversation(conv_id)
    convs_after = database.get_conversations(limit=10)
    assert not any(c["id"] == conv_id for c in convs_after)


def test_main_app_endpoints(db_isolated):
    client = TestClient(main_app)

    # 1. MRI analyze endpoint
    files = {"file": ("test_mri.png", b"fake-png-content", "image/png")}
    res = client.post("/api/analyze", files=files)
    assert res.status_code == 200
    data = res.json()
    assert "scan_id" in data
    assert data["classification"] == "Glioma"

    # 2. Scans endpoint
    scans_res = client.get("/api/scans")
    assert scans_res.status_code == 200
    scans = scans_res.json()
    assert len(scans) >= 1
    assert scans[0]["file_identifier"] == "test_mri.png"

    # 3. EEG session endpoints
    start_res = client.post("/api/eeg/session/start", params={"source": "SIMULATED", "notes": "Test Start"})
    assert start_res.status_code == 200
    session_id = start_res.json()["session_id"]

    end_res = client.post(f"/api/eeg/session/{session_id}/end", json={
        "duration_seconds": 12.5,
        "total_samples": 3125,
        "signal_quality": "Acceptable",
        "features": {"alpha": 5.4}
    })
    assert end_res.status_code == 200
    assert end_res.json()["status"] == "completed"

    list_eeg = client.get("/api/eeg/sessions")
    assert list_eeg.status_code == 200
    assert any(s["id"] == session_id for s in list_eeg.json())

    # 4. AI endpoints
    conv_res = client.post("/api/ai/conversations", params={"provider": "local"})
    assert conv_res.status_code == 200
    c_id = conv_res.json()["conversation_id"]

    add_msg_res = client.post(f"/api/ai/conversations/{c_id}/messages", json={
        "role": "user",
        "content": "Explain Grad-CAM",
        "citations": ["Paper 2017"]
    })
    assert add_msg_res.status_code == 200
    assert "message_id" in add_msg_res.json()

    msgs_res = client.get(f"/api/ai/conversations/{c_id}/messages")
    assert msgs_res.status_code == 200
    assert len(msgs_res.json()) == 1

    del_res = client.delete(f"/api/ai/conversations/{c_id}")
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "deleted"

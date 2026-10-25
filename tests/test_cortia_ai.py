"""Automated tests for CORTIA AI Conversational Assistant."""
import pytest
from fastapi.testclient import TestClient
from server import app
from app.ai.knowledge import KnowledgeRetriever
from app.ai.storage import ConversationStore
from app.logger import log_result


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_ai_capabilities_endpoint(client):
    res = client.get("/api/ai/capabilities")
    assert res.status_code == 200
    data = res.json()
    assert data["assistant_name"] == "CORTIA AI"
    assert "active_provider" in data
    assert len(data["grounded_tools"]) >= 6
    assert len(data["starter_prompts"]) >= 5
    assert "disclaimer" in data


def test_knowledge_retriever_verified_citations():
    retriever = KnowledgeRetriever()
    # Query for Grad-CAM
    results = retriever.retrieve("How does Grad-CAM explain the network?", top_k=1)
    assert len(results) == 1
    doc, cit, score = results[0]
    assert "Grad-CAM" in cit.title
    assert cit.doi == "10.1109/ICCV.2017.74"
    assert cit.publication_year == 2017
    assert cit.verified is True

    # Query for EEG frequency bands
    results_eeg = retriever.retrieve("relative alpha power oscillations in relaxation", top_k=1)
    assert len(results_eeg) == 1
    doc_eeg, cit_eeg, _ = results_eeg[0]
    assert "alpha" in doc_eeg["content"].lower()
    assert cit_eeg.verified is True


def test_ai_chat_raw_vs_filtered(client):
    res = client.post("/api/ai/chat", json={
        "message": "Explain the difference between raw and filtered EEG signals."
    })
    assert res.status_code == 200
    data = res.json()
    assert "conversation_id" in data
    msg = data["message"]
    assert msg["role"] == "assistant"
    # Grounded response content assertions
    assert "raw" in msg["content"].lower()
    assert "filtered" in msg["content"].lower()
    assert "1.0 – 40.0 hz" in msg["content"].lower() or "bandpass" in msg["content"].lower()
    assert len(msg["citations"]) >= 1
    assert any("Sanei" in c["title"] or "EEG" in c["title"] for c in msg["citations"])


def test_ai_chat_gradcam_mechanics(client):
    res = client.post("/api/ai/chat", json={
        "message": "Explain how Grad-CAM works and its diagnostic limitations."
    })
    assert res.status_code == 200
    data = res.json()
    content = data["message"]["content"]
    assert "grad-cam" in content.lower()
    assert "gradient" in content.lower()
    assert "not" in content.lower() and ("segmentation" in content.lower() or "margins" in content.lower())
    assert len(data["message"]["citations"]) >= 1


def test_ai_chat_models_available_honesty(client):
    res = client.post("/api/ai/chat", json={
        "message": "Which AI models are currently available in the registry?"
    })
    assert res.status_code == 200
    content = res.json()["message"]["content"]
    assert "mobilenet" in content.lower() or "mri" in content.lower()
    # Explicit honesty that EEG model is not installed and sleep/anxiety are infeasible
    assert "no trained" in content.lower() or "withheld" in content.lower()
    assert "infeasible" in content.lower() or "single-channel" in content.lower()


def test_ai_chat_with_mri_context(client):
    scan_id = log_result(
        image_path="test_ai_mri.png",
        label="Pituitary",
        confidence=98.2,
        probabilities={"Pituitary": 98.2, "Glioma": 0.5, "Meningioma": 0.8, "No Tumor": 0.5},
        tumor_area_pct=4.12,
        peak_saliency=0.887,
    )

    res = client.post("/api/ai/chat", json={
        "message": "Explain the findings of this scan.",
        "analysis_type": "mri",
        "analysis_id": str(scan_id)
    })
    assert res.status_code == 200
    data = res.json()
    msg = data["message"]
    assert "pituitary" in msg["content"].lower() or str(scan_id) in msg["content"]
    # Check analysis reference chip
    assert msg["analysis_references"] is not None
    assert len(msg["analysis_references"]) >= 1
    assert msg["analysis_references"][0]["id"] == str(scan_id)
    assert f"/insights?type=mri&id={scan_id}" in msg["analysis_references"][0]["deep_link"]


def test_ai_chat_simulated_eeg_warning(client, tmp_path):
    # Connect demo simulated source and start recording to get a real session id
    client.post("/api/device/connect", json={"source": "simulated"})
    rec_res = client.post("/api/eeg/recordings", json={"notes": "AI test"})
    assert rec_res.status_code == 200
    rid = rec_res.json()["id"]
    client.post("/api/eeg/recordings/stop")
    client.post("/api/device/disconnect")

    # Ask AI about this simulated session
    res = client.post("/api/ai/chat", json={
        "message": "Summarize this recording.",
        "analysis_type": "eeg",
        "analysis_id": rid
    })
    assert res.status_code == 200
    data = res.json()
    msg = data["message"]
    # Verify simulated data identification
    assert msg["simulated_warning"] is not None
    assert "simulated" in msg["simulated_warning"].lower()


def test_conversation_persistence_lifecycle(client):
    # 1. Create message
    res = client.post("/api/ai/chat", json={"message": "First inquiry on EEG alpha band."})
    assert res.status_code == 200
    data = res.json()
    conv_id = data["conversation_id"]

    # 2. Add second message to same conversation
    res2 = client.post("/api/ai/chat", json={
        "conversation_id": conv_id,
        "message": "What is the peak frequency in alpha?"
    })
    assert res2.status_code == 200
    assert res2.json()["conversation_id"] == conv_id

    # 3. Retrieve conversation history
    hist_res = client.get(f"/api/ai/conversations/{conv_id}")
    assert hist_res.status_code == 200
    hist = hist_res.json()
    assert hist["id"] == conv_id
    assert len(hist["messages"]) >= 4  # 2 user + 2 assistant messages

    # 4. List conversations
    list_res = client.get("/api/ai/conversations")
    assert list_res.status_code == 200
    conv_list = list_res.json()
    assert any(c["id"] == conv_id for c in conv_list)

    # 5. Delete conversation
    del_res = client.delete(f"/api/ai/conversations/{conv_id}")
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "deleted"

    # 6. Verify 404 after deletion
    get_after_del = client.get(f"/api/ai/conversations/{conv_id}")
    assert get_after_del.status_code == 404

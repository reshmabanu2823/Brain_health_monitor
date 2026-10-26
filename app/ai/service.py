"""Orchestrator for CORTIA AI Assistant."""
import json
import logging
import os
from typing import Any, Dict, List, Optional
from .knowledge import KnowledgeRetriever
from .provider import get_llm_provider
from .schemas import AnalysisReference, ChatMessage, ChatRequest, ChatResponse, Citation
from .storage import ConversationStore
import database as cortia_db
from .tools import (
    get_eeg_hardware_status,
    get_eeg_session_summary,
    get_latest_eeg_summary,
    get_latest_mri_scan,
    get_model_registry,
    get_mri_scan_by_id,
    get_system_health,
    get_verified_model_evaluations,
)

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are CORTIA AI, an expert neuro-oncology, neurology, and clinical AI medical consultant.
Your role is to help patients, clinicians, and researchers understand brain imaging analyses, tumor pathology, physiological EEG biopotentials, treatment pathways, and medical implications.

CLINICAL & PATIENT CONSULTATION CAPABILITIES:
1. COMPREHENSIVE MEDICAL ANSWERS: Provide detailed, medically grounded explanations for all patient symptoms, tumor types (Glioma, Meningioma, Pituitary, or normal variants), neuroanatomy, diagnostic workflows, standard treatments (surgical resection, radiotherapy, Stupp protocol chemotherapy, dexamethasone, anticonvulsants), and EEG physiological rhythms.
2. PATIENT DATA GROUNDING: Whenever patient data is available in the verified context (MRI tumor classification, confidence %, Grad-CAM focal saliency area, EEG band powers, recent scans), directly reference the patient's specific numbers and findings to contextualize your explanation.
3. CLEAR & COMPASSIONATE COMMUNICATION: Explain complex medical terminology in accessible, compassionate language. Help the patient understand what their diagnostic numbers mean in plain English.
4. SUGGEST CONSTRUCTIVE NEXT STEPS: Provide concrete questions for the patient to discuss with their treating neurosurgeon, oncologist, or neurologist.
5. RESEARCH & HARDWARE DISCLOSURE: The application uses single-channel biopotential telemetry (1.0 - 40.0 Hz bandpass); psychiatric screening or clinical sleep staging is infeasible on single-channel setups. Distinguish physical serial from simulated EEG recordings. Grad-CAM represents convolutional feature attention density, not histological tumor margins.
"""


class CortiaAIService:
    def __init__(self, db_path: str, model_dir: str, eeg_service=None, app_state=None):
        self.store = ConversationStore(db_path)
        self.model_dir = model_dir
        self.eeg_service = eeg_service
        self.app_state = app_state
        self.retriever = KnowledgeRetriever()
        self.provider = get_llm_provider()

    def reload_provider(self):
        self.provider = get_llm_provider()
        return self.provider

    def process_chat(self, req: ChatRequest) -> ChatResponse:
        conv_id = req.conversation_id or self.store.create_conversation(title=req.message[:50])

        # Save user message
        self.store.add_message(conversation_id=conv_id, role="user", content=req.message)
        try:
            conn = cortia_db.get_connection()
            row = conn.execute("SELECT id FROM ai_conversations WHERE id = ?", (conv_id,)).fetchone()
            if not row:
                conn.execute(
                    "INSERT INTO ai_conversations (id, created_at, updated_at, title, provider) VALUES (?,?,?,?,?)",
                    (conv_id, cortia_db.now_utc(), cortia_db.now_utc(), req.message[:50], "local")
                )
                conn.commit()
            conn.close()
            cortia_db.insert_message(conv_id, "user", req.message)
        except Exception as db_exc:
            log.warning(f"Failed to sync user message to cortia_db: {db_exc}")

        # 1. Retrieve verified scientific citations
        citations: List[Citation] = []
        retrieved_docs = self.retriever.retrieve(req.message, top_k=2)
        citation_context = ""
        for doc, cit, _ in retrieved_docs:
            citations.append(cit)
            citation_context += f"\n- Source: {cit.title} ({cit.publication_year or 'N/A'})\n  Content: {doc['content']}\n  Limitation: {doc.get('limitations', 'None noted')}\n"

        # 2. Gather verified project state tools
        app_context_parts = []
        references: List[AnalysisReference] = []
        simulated_warning = None
        tool_invocations = []

        query = req.message.lower()

        # Handle explicit analysis context or latest MRI scan (always attached for medical context)
        mri_scan = None
        if req.analysis_type == "mri" and req.analysis_id:
            try:
                mri_scan = get_mri_scan_by_id(int(req.analysis_id))
                tool_invocations.append(f"get_mri_scan_by_id({req.analysis_id})")
            except Exception:
                pass
        else:
            try:
                mri_scan = get_latest_mri_scan()
                if mri_scan:
                    tool_invocations.append("get_latest_mri_scan()")
            except Exception:
                pass

        if mri_scan:
            app_context_parts.append(
                f"[MRI SCAN RECORD #{mri_scan['scan_id']}]:\n"
                f"- Filename: {mri_scan['filename']}\n"
                f"- Classification Result: {mri_scan['result']} (Confidence: {mri_scan['confidence']:.1f}%)\n"
                f"- Class Probabilities: {mri_scan['probabilities']}\n"
                f"- Saliency Area: {mri_scan.get('tumor_area_pct', 0.0):.1f}%, Peak Saliency: {mri_scan.get('peak_saliency', 0.0):.4f}\n"
                f"- Timestamp: {mri_scan['timestamp']}\n"
            )
            references.append(AnalysisReference(
                type="mri",
                id=str(mri_scan["scan_id"]),
                title=f"MRI Scan #{mri_scan['scan_id']} ({mri_scan['result']})",
                deep_link=f"/insights?type=mri&id={mri_scan['scan_id']}",
            ))

        # Handle explicit analysis context or latest EEG telemetry
        eeg_summary = None
        if req.analysis_type == "eeg" and req.analysis_id:
            eeg_summary = get_eeg_session_summary(self.eeg_service, req.analysis_id)
            tool_invocations.append(f"get_eeg_session_summary({req.analysis_id})")
        else:
            try:
                eeg_summary = get_latest_eeg_summary(self.eeg_service)
                if eeg_summary:
                    tool_invocations.append("get_latest_eeg_summary()")
            except Exception:
                pass

        if eeg_summary:
            src = eeg_summary.get("source", "unknown")
            if src == "simulated":
                simulated_warning = "This EEG session contains SIMULATED biopotentials generated for calibration testing, not live physiological recordings."

            app_context_parts.append(
                f"[EEG RECORDING #{eeg_summary['session_id'][:8]}...]:\n"
                f"- Source: {src.upper()}\n"
                f"- Duration: {eeg_summary.get('duration_seconds', 0.0):.1f}s (Sample count: {eeg_summary.get('sample_count', 0)})\n"
                f"- Overall Quality State: {eeg_summary.get('quality_summary', {}).get('quality_state', 'Unknown')}\n"
                f"- Observed Quality Issues: {eeg_summary.get('quality_summary', {}).get('observed_issues', [])}\n"
                f"- Preprocessing: Low {eeg_summary.get('preprocessing_config', {}).get('low_hz', 1.0)} Hz, "
                f"High {eeg_summary.get('preprocessing_config', {}).get('high_hz', 40.0)} Hz, "
                f"Notch {eeg_summary.get('preprocessing_config', {}).get('notch_hz', 50.0)} Hz\n"
                f"- Extracted Feature Summary (Averages): {json.dumps(eeg_summary.get('feature_summary', {}), indent=2)}\n"
                f"- Installed EEG Model Output: {eeg_summary.get('model_output', {}).get('reason', 'None')}\n"
            )
            references.append(AnalysisReference(
                type="eeg",
                id=eeg_summary["session_id"],
                title=f"EEG Session {eeg_summary['session_id'][:8]} ({src.capitalize()})",
                deep_link=f"/insights?type=eeg&id={eeg_summary['session_id']}",
            ))

        # Handle model registry queries
        if any(w in query for w in ["model", "registry", "available models", "sleep", "depression", "anxiety"]):
            reg = get_model_registry(self.eeg_service)
            tool_invocations.append("get_model_registry()")
            app_context_parts.append(f"[MODEL REGISTRY STATUS]:\n{json.dumps(reg, indent=2)}\n")

        # Handle hardware connection queries
        if any(w in query for w in ["hardware", "connect", "serial", "port", "device", "maker uno", "bioamp"]):
            hw = get_eeg_hardware_status(self.eeg_service)
            tool_invocations.append("get_eeg_hardware_status()")
            app_context_parts.append(f"[EEG HARDWARE STATUS]:\n{json.dumps(hw, indent=2)}\n")

        # Combine verified context
        combined_context = ""
        if citation_context:
            combined_context += f"SCIENTIFIC LITERATURE CITATIONS:\n{citation_context}\n"
        if app_context_parts:
            combined_context += "\nACTUAL APPLICATION STATE:\n" + "\n".join(app_context_parts)

        # 3. Retrieve conversation history for context
        conv_record = self.store.get_conversation(conv_id)
        msg_history = []
        if conv_record and conv_record.get("messages"):
            for m in conv_record["messages"][-6:]:  # Last 6 messages
                msg_history.append({"role": m["role"], "content": m["content"]})
        else:
            msg_history.append({"role": "user", "content": req.message})

        # 4. Generate answer through LLM or Grounded Engine
        result = self.provider.generate(
            system_instruction=SYSTEM_PROMPT,
            messages=msg_history,
            context=combined_context,
        )

        answer_text = result.get("text", "Unable to formulate a grounded response at this time.")
        provider_name = result.get("provider", "Grounded Engine")

        # 5. Save assistant message
        msg_id = self.store.add_message(
            conversation_id=conv_id,
            role="assistant",
            content=answer_text,
            citations=citations,
            references=references,
            simulated_warning=simulated_warning,
        )
        try:
            cit_titles = [c.title for c in citations] if citations else []
            cortia_db.insert_message(conv_id, "assistant", answer_text, cit_titles)
        except Exception as db_exc:
            log.warning(f"Failed to sync assistant message to cortia_db: {db_exc}")

        # 6. Build suggested follow-ups
        followups = []
        if "eeg" in query or req.analysis_type == "eeg":
            followups = [
                "Explain the difference between raw and filtered EEG signals.",
                "Why was this recording marked as insufficient quality?",
                "Explain the limitations of single-channel BioAmp hardware."
            ]
        elif "mri" in query or "tumor" in query or req.analysis_type == "mri":
            followups = [
                "Explain how Grad-CAM works.",
                "What is the difference between saliency coverage and segmentation?",
                "Which AI models are currently available in the registry?"
            ]
        else:
            followups = [
                "Summarize my latest EEG recording.",
                "Summarize the results of my latest MRI analysis.",
                "Explain the relative alpha power in this session."
            ]

        response_msg = ChatMessage(
            id=msg_id,
            role="assistant",
            content=answer_text,
            citations=citations,
            analysis_references=references,
            tool_invocations=tool_invocations,
            simulated_warning=simulated_warning,
        )

        return ChatResponse(
            conversation_id=conv_id,
            message=response_msg,
            provider_mode=provider_name,
            suggested_followups=followups,
        )

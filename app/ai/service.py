"""Orchestrator for CORTIA AI Assistant (incorporating Medicluster CliniQ engine)."""
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional
from .knowledge import KnowledgeRetriever
from .provider import get_llm_provider
from .schemas import AnalysisReference, ChatMessage, ChatRequest, ChatResponse, Citation
from .storage import ConversationStore
import database as cortia_db
from .rag_assistant import check_drug_interactions, DRUG_INTERACTIONS
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

LANGUAGE_NAMES = {
    "en": "English",
    "hi": "Hindi",
    "kn": "Kannada",
    "te": "Telugu",
    "ta": "Tamil",
}

SYSTEM_PROMPT = """You are CliniQ, an empathetic, supportive medical doctor having a natural clinical consultation dialogue with a patient or clinician within the CORTIA research platform.

CLINICAL CONSULTATION PRINCIPLES (PORTED FROM MEDICLUSTER):
1. Keep your responses concise, direct, and structured (around 2 to 4 clean paragraphs or bulleted sections).
2. Structure your reply using these standard clinical sections when discussing findings, diagnosis, or symptoms:
   ### Clinical Impression
   Direct, plain-language explanation of findings or potential condition.
   
   ### Key Findings & Differential
   Clear, grounded bullet points addressing the user's specific scan, biopotential data, or symptoms.
   
   ### Recommended Specialist & Action Plan
   Specific specialist referral (e.g. Neuro-Oncology, Neurosurgery, Neurology) and 2-3 immediate practical next steps.
   
   ### Red-Flag Signs & Follow-Up
   Urgent warning signs warranting immediate ER evaluation, and a friendly, relevant clinical follow-up question.

3. PATIENT DATA GROUNDING: Ground your answers in the verified MRI classification, confidence %, Grad-CAM focal saliency, and EEG frequency telemetry whenever available.
4. MEDICAL EXCLUSIVITY: You are dedicated exclusively to medical, neurological, clinical, and healthcare topics. Decline non-medical queries politely.
5. DRUG INTERACTIONS: Always emphasize potential drug interactions, bleeding risks, or hepatic/renal precautions if medications are queried.
"""

# Common medications for regex extraction from prompt
KNOWN_MEDS = [
    "warfarin", "aspirin", "ibuprofen", "metformin", "lisinopril", "metoprolol",
    "verapamil", "furosemide", "digoxin", "atorvastatin", "azithromycin", "ceftriaxone",
    "calcium", "heparin", "clopidogrel", "fluoxetine", "tramadol", "ciprofloxacin",
    "theophylline", "dexamethasone", "levetiracetam", "keppra", "phenytoin", "carbamazepine",
    "valproate", "temozolomide"
]


class CortiaAIService:
    def __init__(
        self,
        db_path: str = "logs/cortia_ai.db",
        model_dir: str = "model",
        eeg_service: Any = None,
        app_state: Any = None,
    ):
        self.store = ConversationStore(db_path)
        self.retriever = KnowledgeRetriever()
        self.provider = get_llm_provider()
        self.model_dir = model_dir
        self.eeg_service = eeg_service
        self.app_state = app_state

    def _extract_medications(self, text: str, user_meds: Optional[List[str]] = None) -> List[str]:
        found = set(user_meds or [])
        text_lower = text.lower()
        for med in KNOWN_MEDS:
            if re.search(r'\b' + re.escape(med) + r'\b', text_lower):
                found.add(med)
        return list(found)

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
                    (conv_id, cortia_db.now_utc(), cortia_db.now_utc(), req.message[:50], "cliniq_rag")
                )
                conn.commit()
            conn.close()
            cortia_db.insert_message(conv_id, "user", req.message)
        except Exception as db_exc:
            log.warning(f"Failed to sync user message to cortia_db: {db_exc}")

        # 1. Check for drug interactions (from Medicluster RAG Assistant)
        meds_to_check = self._extract_medications(req.message, req.medications)
        drug_alert_info = None
        drug_alert_text = ""
        if len(meds_to_check) >= 2:
            drug_alert_info = check_drug_interactions(meds_to_check)
            if drug_alert_info.get("interactions"):
                drug_alert_text = f"\n\n### Clinical Drug Interaction Alert\n{drug_alert_info['summary']}\n"
                for item in drug_alert_info["interactions"]:
                    drug_alert_text += f"- **{'/'.join(item['drugs']).title()}** ({item['severity'].upper()}): {item['effect']}\n"

        # 2. Retrieve verified scientific citations
        citations: List[Citation] = []
        retrieved_docs = self.retriever.retrieve(req.message, top_k=2)
        citation_context = ""
        for doc, cit, _ in retrieved_docs:
            citations.append(cit)
            citation_context += f"\n- Source: {cit.title} ({cit.publication_year or 'N/A'})\n  Content: {doc['content']}\n"

        # 3. Gather verified telemetry context (MRI scan & EEG)
        app_context_parts = []
        references: List[AnalysisReference] = []
        simulated_warning = None
        tool_invocations = []

        query = req.message.lower()

        # Handle MRI context
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
                f"[ACTIVE MRI SCAN RECORD #{mri_scan['scan_id']}]:\n"
                f"- Scan Image: {mri_scan['filename']}\n"
                f"- Primary Classification: {mri_scan['result']} (Confidence: {mri_scan['confidence']:.1f}%)\n"
                f"- Probability Breakdown: {mri_scan['probabilities']}\n"
                f"- Focal Tumor Saliency Area: {mri_scan.get('tumor_area_pct', 0.0):.1f}%\n"
                f"- Peak Attention Score: {mri_scan.get('peak_saliency', 0.0):.4f}\n"
            )
            references.append(AnalysisReference(
                type="mri",
                id=str(mri_scan["scan_id"]),
                title=f"MRI Scan #{mri_scan['scan_id']} ({mri_scan['result']})",
                deep_link=f"/insights?type=mri&id={mri_scan['scan_id']}",
            ))

        # Handle EEG context
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
                f"[ACTIVE EEG BIOPOTENTIAL SESSION #{eeg_summary['session_id'][:8]}]:\n"
                f"- Telemetry Source: {src.upper()}\n"
                f"- Duration: {eeg_summary.get('duration_seconds', 0.0):.1f}s\n"
                f"- Quality Assessment: {eeg_summary.get('quality_summary', {}).get('quality_state', 'Unknown')}\n"
            )
            references.append(AnalysisReference(
                type="eeg",
                id=eeg_summary["session_id"],
                title=f"EEG Session {eeg_summary['session_id'][:8]} ({src.capitalize()})",
                deep_link=f"/insights?type=eeg&id={eeg_summary['session_id']}",
            ))

        # Multimodal image attachment context
        if req.image_base64:
            tool_invocations.append("multimodal_image_attached()")
            app_context_parts.append("[USER ATTACHED MEDICAL SCAN/PHOTO]: Multimodal visual scan provided for clinical inspection.")

        # Multi-language instruction
        lang = req.language or "en"
        lang_name = LANGUAGE_NAMES.get(lang, "English")
        lang_instruction = ""
        if lang != "en":
            lang_instruction = f"\n\nIMPORTANT: You must respond entirely in {lang_name}. All headings, explanations, and advice must be in {lang_name} script."

        # Compile context
        combined_context = (
            f"=== VERIFIED REAL PATIENT TELEMETRY CONTEXT ===\n{''.join(app_context_parts)}\n"
            f"=== SCIENTIFIC LITERATURE & GUIDELINES ===\n{citation_context}\n"
            f"{lang_instruction}"
        )

        # 4. Build message history
        prev_messages = self.store.get_messages(conv_id, limit=8)
        msg_history = []
        if prev_messages:
            for m in prev_messages:
                msg_history.append({"role": m["role"], "content": m["content"]})
        else:
            msg_history.append({"role": "user", "content": req.message})

        # Ensure the last message in msg_history is always the current user message
        if not msg_history or msg_history[-1].get("role") != "user" or msg_history[-1].get("content") != req.message:
            msg_history.append({"role": "user", "content": req.message})

        # 5. Generate response
        result = self.provider.generate(
            system_instruction=SYSTEM_PROMPT,
            messages=msg_history,
            context=combined_context,
        )

        raw_answer = result.get("text", "")
        provider_name = result.get("provider", "CliniQ Medical Engine")

        # Fallback to intelligent rule-grounded response if provider returned empty
        if not raw_answer or len(raw_answer.strip()) < 10:
            if mri_scan and any(w in query for w in ["scan", "mri", "tumor", "report", "finding", "result"]):
                raw_answer = (
                    f"### Clinical Impression\n"
                    f"The loaded scan demonstrates features consistent with **{mri_scan['result']}** with an automated model confidence of **{mri_scan['confidence']:.1f}%**.\n\n"
                    f"### Key Findings & Differential\n"
                    f"- **Focal Saliency**: Penultimate layer Grad-CAM attribution localized a primary focal attention mass covering approximately {mri_scan.get('tumor_area_pct', 0.0):.1f}% of intracranial area.\n"
                    f"- **Diagnostic Distribution**: {mri_scan['probabilities']}.\n\n"
                    f"### Recommended Specialist & Action Plan\n"
                    f"- **Referral**: Immediate evaluation by a **Neuro-Oncologist** and **Neurosurgical Team**.\n"
                    f"- **Next Steps**: Multi-parametric contrast MRI with spectroscopy (1H-MRS) and formal radiologist overread.\n\n"
                    f"### Red-Flag Signs & Follow-Up\n"
                    f"Seek immediate emergency medical attention for sudden severe headache, projectile vomiting, new-onset seizures, or acute focal motor deficits.\n\n"
                    f"*Has the patient experienced any nocturnal headaches or visual disturbances?*"
                )
            elif drug_alert_info and drug_alert_info.get("interactions"):
                raw_answer = (
                    f"### Clinical Drug Interaction Assessment\n"
                    f"A clinically significant drug-drug interaction was identified among the queried medications.\n"
                    f"{drug_alert_text}\n"
                    f"### Recommended Action Plan\n"
                    f"- **Consultation**: Review with the prescribing physician or clinical pharmacist prior to co-administration.\n"
                    f"- **Monitoring**: Schedule regular therapeutic lab monitoring (e.g. INR or renal function profile).\n\n"
                    f"### Red-Flag Signs\n"
                    f"Report any unexplained bruising, hematuria, black tarry stools, or persistent dizziness immediately."
                )
            else:
                raw_answer = (
                    f"### Clinical Impression\n"
                    f"Thank you for your clinical inquiry regarding: *\"{req.message}\"*.\n\n"
                    f"### Clinical Guidance\n"
                    f"- For neuro-imaging inquiries, review the active axial scan metrics in the **MRI Analysis** and **3D Brain Imaging** workspaces.\n"
                    f"- For physiological biopotentials, review spectral power distribution (Delta, Theta, Alpha, Beta) in **EEG Monitoring**.\n\n"
                    f"### Recommended Specialist\n"
                    f"Consult a board-certified Neurologist or Clinical Neurophysiologist for patient-specific diagnostic confirmation.\n\n"
                    f"*Would you like me to analyze a specific MRI scan or check medication interactions?*"
                )

        # Prepend drug interaction alert if present and not already in answer
        if drug_alert_text and "Clinical Drug" not in raw_answer:
            answer_text = drug_alert_text + "\n\n" + raw_answer
        else:
            answer_text = raw_answer

        # Determine recommended specialist
        specialist = "Neuro-Oncology"
        if "eeg" in query or "seizure" in query:
            specialist = "Neurology / Epileptology"
        elif "drug" in query or "warfarin" in query or "metformin" in query:
            specialist = "Clinical Pharmacology"
        elif "pituitary" in query or (mri_scan and "Pituitary" in mri_scan.get("result", "")):
            specialist = "Neuro-Endocrinology / Skull Base Surgery"

        # 6. Save assistant message
        self.store.add_message(
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
        except Exception:
            pass

        suggested = [
            "Explain Grad-CAM focal visual attribution",
            "Check drug interactions for Dexamethasone & Warfarin",
            "Explore active lesion in 3D Brain Imaging",
            "What surgical resection criteria apply to this finding?"
        ]

        return ChatResponse(
            conversation_id=conv_id,
            message=ChatMessage(
                role="assistant",
                content=answer_text,
                citations=citations,
                analysis_references=references,
                tool_invocations=tool_invocations,
                simulated_warning=simulated_warning,
                drug_interactions=drug_alert_info,
                specialist=specialist
            ),
            provider_mode=provider_name,
            suggested_followups=suggested,
            drug_interactions=drug_alert_info,
            specialist=specialist
        )

    def get_capabilities(self) -> Dict[str, Any]:
        return {
            "assistant_name": "CORTIA CliniQ",
            "version": "2.5",
            "provider_configured": getattr(self.provider, "is_configured", False),
            "active_provider": getattr(self.provider, "name", "CliniQ Grounded Engine"),
            "grounded_tools": [
                "mri_axial_diagnostic_inference",
                "grad_cam_saliency_attribution",
                "eeg_spectral_decomposition",
                "eeg_quality_assurance_filter",
                "drug_drug_interaction_knowledge_base",
                "multimodal_medical_image_inspection",
                "ras_3d_brain_mesh_reconstruction"
            ],
            "starter_prompts": [
                "Summarize active MRI scan findings and clinical differential",
                "Check drug interactions for Warfarin, Aspirin, and Dexamethasone",
                "Explain the focal attention zone identified by Grad-CAM",
                "Recommended specialist referral and clinical next steps"
            ],
            "supported_languages": [
                {"code": "en", "name": "English"},
                {"code": "hi", "name": "हिंदी (Hindi)"},
                {"code": "kn", "name": "ಕನ್ನಡ (Kannada)"},
                {"code": "te", "name": "తెలుగు (Telugu)"},
                {"code": "ta", "name": "தமிழ் (Tamil)"}
            ],
            "disclaimer": "CORTIA CliniQ is a research assistance tool and does not provide clinical diagnosis. Consult qualified physicians for medical decisions."
        }

# CORTIA AI & CORTIA Insights (Explainable AI Centre)

## System Overview

**CORTIA** (*Cerebral Observation & Research through Technological Intelligence and Analytics*) integrates two advanced research modules into the unified Google Material Design 3 workstation:

1. **CORTIA AI**: An intelligent, neuroscience-focused conversational assistant grounded in peer-reviewed scientific literature and real project telemetry.
2. **CORTIA Insights**: A scientific Explainable AI Centre providing visual inspection of Grad-CAM saliency density, single-channel EEG feature metrics, empirical confusion matrices, and audit logs.

---

## 1. Module 1: CORTIA AI

### 1.1 Architecture & Grounding Rules
- **Retrieval-Augmented Generation (RAG)**: The assistant uses a grounded knowledge retriever indexed with verified scientific publications (Selvaraju et al. 2017 ICCV, Sanei & Chambers 2007, Klimesch 1999, Hjorth 1970, Casson et al. 2010, Islam et al. 2016, Cheng et al. 2015).
- **Zero Fabrication Constraint**:
  - The assistant retrieves actual application state using read-only backend functions (`get_eeg_hardware_status`, `get_latest_eeg_summary`, `get_eeg_session_summary`, `get_model_registry`, `get_latest_mri_scan`, `get_mri_scan_by_id`, `get_verified_model_evaluations`, `get_system_health`).
  - If a model is not installed (e.g. EEG classifiers), the assistant explicitly reports that no model is available rather than fabricating scores.
  - Infeasible neuropsychiatric tasks (sleep staging, anxiety screening, depression screening via Frontal Alpha Asymmetry) are explicitly documented as infeasible on 1-channel BioAmp hardware.
  - If an EEG session was generated via simulation, an explicit warning chip is attached to all summaries and exported answers.
  - Grad-CAM is strictly defined as gradient-weighted saliency visual attention, not clinical lesion segmentation or margin boundaries.
- **Modular LLM Provider Interface**:
  - `BaseLLMProvider` abstraction supporting:
    - **Google Gemini** (`GEMINI_API_KEY` or `CORTIA_AI_API_KEY`, model: `gemini-1.5-flash`)
    - **OpenAI** (`OPENAI_API_KEY`, model: `gpt-4o-mini`)
    - **GroundedSynthesisEngine**: Local, deterministic research engine operating with zero cloud API keys, synthesizing verified literature citations and actual database records.
- **Conversation Persistence**:
  - Stored in SQLite (`logs/cortia_ai.db`).
  - Supports conversation listing, message history retrieval, citations preservation, and deletion.

### 1.2 Endpoints
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/ai/chat` | Send research inquiry, returns grounded response with citations and deep links |
| `GET` | `/api/ai/capabilities` | Inspect active provider, starter prompts, and tool access |
| `GET` | `/api/ai/conversations` | List saved conversations |
| `GET` | `/api/ai/conversations/{id}` | Retrieve messages in conversation |
| `DELETE` | `/api/ai/conversations/{id}` | Delete conversation |
| `POST` | `/api/ai/clear` | Clear all conversation history |

---

## 2. Module 2: CORTIA Insights (Explainable AI Centre)

### 2.1 Workspace Structure
- **Overview**: System status summary, active model metrics, and data integrity safeguards.
- **MRI Explainability**:
  - Original MRI slice vs. Grad-CAM saliency overlay viewer.
  - View modes: Side-by-Side, Overlay (with interactive 0–100% opacity slider), Original Only, Grad-CAM Only.
  - Quantitative metrics: Saliency Coverage (% brain area with activation > 0.52) and Peak Saliency intensity.
  - One-click "Ask CORTIA AI About This MRI Scan" action.
- **EEG Feature Explorer**:
  - Live or historical session inspection from SQLite `eeg.db`.
  - Signal-quality assessment: 3-state badge (`Acceptable`, `Needs review`, `Insufficient quality`) with machine-readable reasons (missing samples, sensor saturation, flatline, excessive variance).
  - Extracted spectral & time-domain features table: Relative Alpha (8–13 Hz), Theta (4–8 Hz), Beta (13–30 Hz), Delta (1–4 Hz), partial Gamma (30–40 Hz), Peak Frequency, RMS Amplitude, Signal Power, Spectral Entropy, and Hjorth parameters.
  - Filter parameters: 4th-order Butterworth bandpass (1.0–40.0 Hz), 50.0 Hz notch, 4.0s windows, 1.0s guards.
  - Explicit notification that no trained EEG classifier is installed.
- **Model Performance Centre**:
  - Empirical evaluation metrics loaded from disk (`model_candidate_kaggle_boost15_234/evaluation.json`):
    - Test accuracy: **95.3%** on 234 test scans.
    - Macro F1-score: **0.928**.
    - Full 4x4 Confusion Matrix for Glioma, Meningioma, No Tumor, and Pituitary Tumor.
    - Export parity: 100% prediction agreement between TFLite quantized runtime and Keras FP32 baseline.
- **Analysis History**:
  - Unified table combining MRI scan inferences and EEG telemetry sessions.
  - Direct actions to inspect in viewer or ask CORTIA AI.

### 2.2 Endpoints
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/insights/overview` | Executive workspace summary and recent activity |
| `GET` | `/api/insights/mri/latest` | Retrieve latest MRI scan record and saliency metrics |
| `GET` | `/api/insights/mri/{scan_id}` | Retrieve specific MRI scan explanation record |
| `GET` | `/api/insights/eeg/latest` | Retrieve latest EEG session summary |
| `GET` | `/api/insights/eeg/{session_id}` | Retrieve specific EEG session summary |
| `GET` | `/api/insights/performance` | Load verified test evaluation records and confusion matrix |
| `GET` | `/api/insights/history` | List unified analysis history with filtering (`all`, `mri`, `eeg`) |
| `GET` | `/api/insights/compare/eeg` | Longitudinal side-by-side comparison between two sessions |

---

## 3. Navigation & Floating Assistant

- **Navigation Rail**: Synchronized across `/` (MRI), `/eeg` (EEG), `/insights` (Insights), `/ai` (AI), and `/cortia` (Portal).
- **Floating Assistant**: Available via bottom-right trigger across the application, with a sliding flyout drawer for instant queries and context-aware pre-fill.
- **Cross-Module Handoff**: Analysis cards on `/` and `/insights` contain "Ask CORTIA AI" buttons that deep-link with pre-validated server-side context (`/ai?analysis_type=mri&analysis_id=...`).

---

## 4. Verification & Testing

- Automated tests: `tests/test_cortia_ai.py` and `tests/test_cortia_insights.py` (14 passed).
- Complete test suite: `python -m pytest` (97 passed, 2 skipped GUI tests, 0 regressions).
- JavaScript syntax: `node --check` verified for all scripts (0 errors).

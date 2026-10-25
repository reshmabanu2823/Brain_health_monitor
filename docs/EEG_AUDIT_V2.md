# EEG Signal Intelligence: Comprehensive System Audit & Evolution Plan (v2.0)

**Document Version:** 2.0  
**Project:** Brain Health Monitor (BHM) — EEG Module Evolution  
**Date:** 2026-10-25  
**Target Environment:** Maker UNO (ATmega328P) + BioAmp EXG Pill (1-channel analog biopotential) + FastAPI / SQLite / Modern Web UI  

---

## STEP 1: AUDIT OF EXISTING EEG ARCHITECTURE

### a) Current EEG Functionality
The existing EEG module in the repository consists of a fully isolated sub-system decoupled from MRI operations:
- **Acquisition (`app/eeg/service.py`):** Managed by `EEGService` on an autonomous background worker thread (`bhm-eeg`). Handles both live USB serial communication (`_serial()`) and synthetic demonstration streaming (`_demo()`).
- **Buffering (`app/eeg/service.py`):** Uses a fixed-capacity FIFO `collections.deque(maxlen=input_samples)` holding exactly 1,500 samples (6.0 seconds at 250 Hz, divided into a 4-second central window and two 1-second filter edge guards).
- **Preprocessing (`app/eeg/signal.py`):** Detrends linear drift (`scipy.signal.detrend`), applies a 50 Hz IIR notch filter (`scipy.signal.iirnotch`), and runs a 4th-order zero-phase Butterworth bandpass filter (`scipy.signal.butter` + `sosfiltfilt`).
- **Quality Checks (`app/eeg/signal.py`):** Basic binary rejection (`valid: True/False`). Flags windows with non-finite samples, non-increasing timestamps, sampling rate deviations exceeding 2%, timing jitter exceeding 15%, ADC counts out of range [0, 1023], clipping (>1% of samples at 0 or 1023), flatline signal (standard deviation < 0.5 or >95% identical consecutive samples), or transient steps (>150 ADC count delta between adjacent samples).
- **Features (`app/eeg/signal.py`):** Extracts 9 scalar values (`delta`, `theta`, `alpha`, `beta`, `gamma_partial` relative powers; variance; Hjorth mobility; Hjorth complexity; spectral entropy).
- **Storage (`app/eeg/storage.py`):** Thread-safe SQLite repository (`logs/eeg.db`) with tables `eeg_sessions` and `eeg_samples`. Persists raw ADC counts, sequence numbers, device timestamps, and receipt timestamps. Generates CSV streaming exports.
- **API (`app/eeg/api.py`):** FastAPI router mounted at `/api/device/*` and `/api/eeg/*`. Exposes port discovery, connection controls (with same-origin enforcement), live telemetry snapshot (`/api/eeg/live`), model metadata (`/api/eeg/model/info`), and session recording/export endpoints.
- **Frontend (`static/eeg.html`, `static/js/eeg.js`, `static/css/eeg.css`):** Material Design 3 / Google Health clinical interface. Displays telemetry badges, live waveform canvas, relative band power progress meters, Welch PSD frequency canvas, classifier status, and local session recording history.

### b) Hardware Integration & Firmware
- **Microcontroller:** Maker UNO (ATmega328P, 16 MHz, 10-bit ADC, supply-derived 5V analog reference, CH340 USB-UART interface).
- **Analog Front-End:** BioAmp EXG Pill (1 differential bipolar biopotential channel: VCC $\rightarrow$ 5V, GND $\rightarrow$ GND, OUT $\rightarrow$ Maker UNO A0). Analog gain $\approx 1100\times$, passive hardware bandpass.
- **Firmware (`firmware/maker_uno_eeg/maker_uno_eeg.ino`):**
  - Custom ASCII streaming sketch (not compatible with proprietary Chords binary protocol).
  - Fixed sample rate: **250 Hz** (`PERIOD_US = 4000 µs`).
  - Framing: `#BHM,1,raw_adc_counts,10bit` initial handshake header followed by `sequence,micros,adc\n` CSV data frames.
  - Missed deadline handling: Increments sequence counter over dropped deadlines without synthesizing fake interpolated samples.
  - Baud rate: **115,200 baud**.
- **Host Ingestion (`app/eeg/protocol.py`):**
  - `SerialParser`: Robust byte-by-byte framing with 80-character maximum line guard and comment filtering.
  - `SampleClock`: Unwraps 32-bit microsecond counter (`micros()`) into continuous seconds and flags sequence loss, MCU reboots, or non-forward time jumps.

### c) Existing Signal-Processing Parameters & Filter Settings
*All parameters are encapsulated in `SignalConfig` (`app/eeg/signal.py`):*
- **Sampling Rate ($f_s$):** 250 Hz (configurable range 100–250 Hz).
- **Analysis Window:** 4.0 seconds (1,000 samples).
- **Edge Guards:** 1.0 second on each side (250 samples $\times$ 2), yielding an input buffer of 6.0 seconds (1,500 samples). Guard bands are discarded post-filtering to eliminate `sosfiltfilt` transient ringing.
- **Mains Notch Filter:** 50.0 Hz IIR notch filter, Quality Factor $Q = 30$, implemented as Second-Order Sections (SOS).
- **Bandpass Filter:** 4th-order Butterworth bandpass, forward-backward zero-phase (`sosfiltfilt`), cutoffs: **1.0 Hz to 40.0 Hz**.
- **Exact Band Definitions (`BANDS` in `app/eeg/signal.py`):**
  - **Delta ($\delta$):** **1.0 – 4.0 Hz** (*Note: Low cutoff is strictly 1.0 Hz due to hardware highpass and DC baseline wander; not 0.5 Hz*).
  - **Theta ($\theta$):** **4.0 – 8.0 Hz**
  - **Alpha ($\alpha$):** **8.0 – 13.0 Hz**
  - **Beta ($\beta$):** **13.0 – 30.0 Hz**
  - **Gamma ($\gamma$):** **30.0 – 40.0 Hz** (*Note: Strictly partial gamma up to the 40.0 Hz Nyquist-safe bandpass cutoff; sensitive to facial/cranial muscle contamination*).
- **PSD Estimation:** Welch's periodogram with 2-second subsegments (500 samples), 50% overlap (250 samples), constant detrending, and spectral density scaling ($\text{counts}^2/\text{Hz}$).

### d) Existing Machine Learning Code & Datasets
- **Dataset Status:** **Zero local EEG datasets or recordings exist.** No subject recordings, no labels, and no pre-collected physiological traces are stored in the repository.
- **Model Status:** **No trained EEG classifier exists.** `app/eeg/model.py` checks for `model.joblib` and `metadata.json`; when absent, it explicitly returns `available: False` with `"No EEG model installed; labeled dataset required"`. No synthetic predictions or fabricated confidence numbers are ever output.
- **Training Pipeline (`app/eeg/training.py`, `train_eeg.py`, `docs/EEG_ML.md`):**
  - An experimental baseline training framework is implemented using `scikit-learn` (supports `DummyClassifier`, `LogisticRegression`, and `RandomForestClassifier`).
  - Enforces strict subject-disjoint train/validation/test partitioning.
  - Requires explicit JSON manifest containing task descriptions, investigator provenance, license, subject IDs, and genuine uncalibrated ADC-count CSV paths.
  - Rejects duplicate files, repeated subject splits, and windows with data-quality faults.

### e) Pipeline Gaps Against Target Research Architecture
Target Pipeline:
$$\text{Acquisition} \longrightarrow \text{Validation/Buffering} \longrightarrow \text{Preprocessing} \longrightarrow \text{Quality Assessment} \longrightarrow \text{Features} \longrightarrow \text{Task Model} \longrightarrow \text{Uncertainty} \longrightarrow \text{Explanation} \longrightarrow \text{Dashboard/Reports}$$

1. **Acquisition & Buffering:** Fully functional for 1-channel Maker UNO serial and simulation.
2. **Preprocessing:** Functional, but preprocessing parameters (filter order, cutoff frequencies, notch configuration) are not permanently serialized with individual session records.
3. **Quality Assessment:** Currently binary (`valid: true/false`). Lacks a 3-tier graded taxonomy (`Acceptable` / `Needs review` / `Insufficient quality`) and does not serialize machine-readable reason tokens across the entire recording session.
4. **Feature Extraction:** Computes 9 scalar features, but lacks peak frequency, RMS, raw signal power, mean, and does not return units or window duration metadata alongside feature vectors.
5. **Task-Specific Model:** Trainer exists, but no trained model is deployed due to lack of an experimental dataset.
6. **Output + Uncertainty:** Baseline model infrastructure supports class probabilities, but lacks calibrated epistemic/aleatoric uncertainty quantification.
7. **Explanation:** No explanation assistant or feature attribution (e.g. SHAP, band contribution narratives) is connected to EEG.
8. **Dashboard / History / Reports:** Live dashboard shows active window and a flat list of recorded sessions, but lacks synchronized raw-vs-processed waveforms, cross-session longitudinal feature comparison, session summaries with research notes, and a structured model registry.

### f) Gaps Against Detailed Specifications
- **Synchronized Raw vs Processed Waveforms:** Frontend only renders the raw incoming buffer; filtered zero-phase output is discarded after PSD extraction rather than surfaced to the UI.
- **Three-State Quality System:** Currently only reports boolean `valid` and human-readable string rejection reasons. Missing explicit states: `acceptable`, `needs_review`, `insufficient_quality` with programmatic failure codes (`saturation`, `flatline`, `excessive_amplitude`, `excessive_noise`, `insufficient_duration`, `discontinuous_samples`).
- **Comprehensive Feature Set with Units:** Features currently return raw numerical arrays without explicit measurement units (`counts`, `counts^2`, `Hz`, `dimensionless`) or window specification. Peak frequency, RMS, mean, and total signal power are missing.
- **Reproducible Preprocessing Records:** Session records only store high-level dictionary parameters rather than the exact mathematical filter specifications (Butterworth 4th-order SOS, notch Q-factor, guard sample counts, software commit/version).
- **Session Summary Object:** Currently, the system only returns session start/end and sample counts. Missing aggregated window quality percentages, mean feature vectors across windows, model inference summaries, and investigator notes.
- **Model Registry:** Missing an endpoint and dashboard panel detailing the status, input contracts, and clinical feasibility of planned research modules.

### g) Bandpass Frequency Constraints & Physiological Realism
- **Delta (1.0–4.0 Hz):** Standard clinical delta spans 0.5–4.0 Hz. However, single-channel hobby dry/gel electrodes paired with simple RC highpass front-ends exhibit intense galvanic skin potential drift and movement artifacts below 1.0 Hz. Setting the lower cutoff to 1.0 Hz prevents baseline saturation from falsely dominating spectral power.
- **Partial Gamma (30.0–40.0 Hz):** True cortical gamma extends to 100+ Hz. With a 250 Hz sample rate (Nyquist limit = 125 Hz) and a 40 Hz lowpass filter, frequencies above 40 Hz are attenuated. Furthermore, single-channel forehead/scalp recordings without spatial filtering are heavily contaminated by cranial/temporalis muscle (EMG) activity in the 30–100 Hz band. Documenting gamma as **"partial 30–40 Hz"** is essential for scientific integrity.

---

## STEP 2: PRIORITISED 10-PHASE EVOLUTION PLAN

The evolutionary roadmap below transforms the existing codebase into the **EEG Signal Intelligence** research workstation.

### Feasibility Boundary: BioAmp 1-Channel Hardware
> [!IMPORTANT]
> The Maker UNO + BioAmp EXG Pill setup provides **one bipolar channel** without calibrated microvolts or scalp montage (10-20 system).
> - **Feasible Research Tasks:** Frontal alpha asymmetry baselines (if referenced appropriately), eyes-open vs. eyes-closed spectral reactivity, focused cognitive engagement vs. relaxed baseline, gross blink/ocular artifact telemetry.
> - **Infeasible Clinical Modules:**
>   1. **Sleep Staging (Polysomnography):** Requires multi-channel EEG (C3/C4/O1/O2), EOG (eye movements), and chin EMG. Single-channel forehead biopotentials cannot reliably score NREM 1-3 or REM sleep.
>   2. **Depression Screening:** Frontal alpha asymmetry for affective disorders requires standardized bilateral homologous electrode pairs (F3/F4) with common average or linked-ear reference. Single-channel cannot compute hemispheric asymmetry.
>   3. **Anxiety Disorder Diagnosis:** Clinical anxiety manifests with complex distributed neurocircuit patterns not diagnosable from single-channel uncalibrated counts.
> - **Governance Rule:** These infeasible modules must appear in the Model Registry permanently flagged as **"Not Available / Not Feasible on Single-Channel Hardware"**, never as active or simulated diagnostic predictors.

---

### Detailed Phase Matrix

| Phase | Phase Name | Status & Existing Code | What is Missing / To Implement | Effort | Dependencies & Hardware / User Decisions |
|---|---|---|---|:---:|---|
| **1** | **Audit** | Complete (`docs/EEG_AUDIT_V2.md`, `docs/EEG_ML.md`, `docs/HARDWARE.md`) | Nothing; documented baseline established. | **S** | None. Complete. |
| **2** | **Verify Real Data Acquisition** | Firmware (`maker_uno_eeg.ino`), serial parser (`protocol.py`), connection service (`service.py`) | Physical hardware handshake verification, electrode contact impedance check, serial noise measurement on battery power. | **M** | **Requires User Hardware:** Maker UNO board, BioAmp Pill, USB cable, electrode leads, and skin prep. |
| **3** | **Validation, Preprocessing, Quality & Features** | `signal.py` has basic 9 features and binary quality checks; `storage.py` stores sessions | 3-state quality engine (`Acceptable`/`Needs review`/`Insufficient`), expanded feature set with units (peak freq, RMS, mean, signal power), synchronized raw vs. processed waveform generation, preprocessing provenance storage, session summaries. | **M** | **Software-only.** Implemented in Step 3. |
| **4** | **Pick ONE Research Task + Dataset** | `docs/EEG_ML.md` describes eyes-open vs. eyes-closed protocol | Select specific experimental task (e.g. Eyes-Open vs. Eyes-Closed Alpha Reactivity); formalize participant recording protocol, consent form, and metadata schema. | **S** | **Requires User Decision:** Select research task and commit to recording protocol. |
| **5** | **Train, Integrate & Evaluate Model** | `app/eeg/training.py` provides cross-validation and scikit-learn pipeline | Genuine subject-disjoint dataset collection, training execution, evaluation artifact generation (`model.joblib`, `metadata.json`, `confusion_matrix.svg`). | **L** | Dependent on Phase 4 dataset collection. |
| **6** | **Connect Model to Dashboard** | `app/eeg/model.py` and `/api/eeg/model/info` endpoint exist | Real-time inference display for validated task model, epistemic uncertainty badge, fallback rationale when quality is insufficient. | **S** | Dependent on Phase 5 trained model. |
| **7** | **History & Longitudinal Comparison** | Session list in `storage.py` and `/api/eeg/recordings` | Cross-session feature comparison table, trend analysis (e.g. Alpha Peak Shift across sessions), session notes editor. | **M** | Software-only. Builds on Phase 3 session summaries. |
| **8** | **Neurova Explanation Assistant** | None for EEG (MRI has Grad-CAM saliency explanations) | Rule-based and spectral feature attribution assistant explaining feature deviations, band shifts, and signal quality rationale. | **M** | Software-only. |
| **9** | **Failure-Mode Testing** | `tests/test_eeg_*.py` covers basic errors and unit tests | Rigorous simulation of hardware disconnection, high-amplitude blink artifacts, electrode detachment, 50 Hz mains hum injection, buffer saturation. | **M** | Software-only. Automated synthetic test fixtures. |
| **10** | **Documentation & Research Protocols** | `docs/DATA_ACQUISITION.md`, `docs/HARDWARE.md`, `docs/EEG_ML.md` | Finalized laboratory handbook, participant guide, electrode placement SOP, research paper methodology draft. | **S** | Software-only. |

---

## STEP 3: SPECIFICATION OF SOFTWARE-ONLY IMPLEMENTATION (PHASE 3 SUBSET)

The immediate software implementation delivers the foundational signal intelligence capabilities:

1. **Three-State Quality Assessment Engine (`app/eeg/signal.py`):**
   - States: `acceptable`, `needs_review`, `insufficient_quality`.
   - Machine-readable reason tokens: `insufficient_duration`, `missing_or_non_finite`, `non_increasing_timestamps`, `rate_deviation`, `excessive_jitter`, `saturation_clipping`, `flatline`, `excessive_amplitude`, `excessive_noise_step`.
   - In `insufficient_quality`, inference is strictly withheld (`valid = False`), protecting downstream classifiers from corrupt inputs.

2. **Expanded Feature Extraction with Strict Dimensionality & Metadata:**
   - Retains the 9 core features in `result['features']` to guarantee 100% backward compatibility with existing ML code and tests.
   - Adds rich `result['feature_metrics']` providing:
     - `delta_power_relative`, `theta_power_relative`, `alpha_power_relative`, `beta_power_relative`, `gamma_partial_power_relative` (`fraction 0-1`).
     - `delta_power_absolute`, `theta_power_absolute`, `alpha_power_absolute`, `beta_power_absolute`, `gamma_partial_power_absolute` (`counts^2`).
     - `peak_frequency_hz` (`Hz`).
     - `mean` (`counts`).
     - `variance` (`counts^2`).
     - `rms` (`counts`).
     - `signal_power` (`counts^2`).
     - `spectral_entropy` (`dimensionless 0-1`).
     - `hjorth_mobility`, `hjorth_complexity` (`dimensionless`).
   - Every metric specifies `value`, `unit`, `window_length_s`, and `band_definition`.

3. **Synchronized Raw vs. Processed Waveforms:**
   - Preprocessing returns both the raw ADC window and the zero-phase filtered signal (`sosfiltfilt`) trimmed of edge guards, enabling direct comparison on the dashboard.

4. **Reproducible Preprocessing Provenance (`app/eeg/signal.py`, `app/eeg/storage.py`):**
   - Every session logs filter architecture (`butterworth_sos_zero_phase`, order 4, cutoffs 1.0–40.0 Hz), notch filter configuration (50 Hz, Q=30), guard duration, sample rate, and software version.

5. **Session Summary & Notes Endpoint (`app/eeg/api.py`, `app/eeg/storage.py`):**
   - SQLite schema migration adding `notes` and `summary` columns to `eeg_sessions`.
   - `/api/eeg/recordings/{rid}/summary` endpoint aggregating duration, sample count, quality distribution, mean features across windows, and researcher notes.

6. **Model Registry Endpoint (`app/eeg/api.py`):**
   - `/api/eeg/models/registry` providing the 6 planned modules with explicit availability status, inputs, and clinical feasibility constraints.

7. **Google Material Design 3 Frontend Integration (`static/eeg.html`, `static/js/eeg.js`):**
   - Synchronized raw vs. filtered waveform canvas toggle.
   - Three-state quality badge and diagnostic reasons panel.
   - Rich feature table with units.
   - Research Model Registry panel.
   - Researcher notes field for session records.

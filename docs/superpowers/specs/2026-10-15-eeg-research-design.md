# Single-channel EEG research extension

User brief: incrementally extend existing MRI application with actual Maker UNO/BioAmp EXG Pill USB acquisition, defensible signal processing, explicit simulation, reproducible ML tooling, session storage and accessible UI. Preserve MRI routes; no diagnostic EEG claims or fabricated results. User explicitly authorizes implementation after audit.

## Existing system and choice
Keep FastAPI, SQLite and static HTML/JS. A separate service would duplicate configuration and UI communication; replacing MRI would discard useful inference/report functionality. Add app/eeg modules and a separate /eeg research workspace in the same server. Keep MRI at /.

## Hardware contract
One BioAmp EXG Pill, one differential measurement (electrode reference is not another channel), Maker UNO ATmega328P, USB laptop. Custom raw acquisition sketch: A0, 10-bit ADC counts, nominal 250 Hz, 115200 baud, sequence + device micros timestamps + value CSV. No calibrated microvolt claims. Timestamp rollover handled; sequence gaps/reset/reconnection invalidate current window. Rate measured from device timestamps, not USB arrival times. Host receipt UTC stored separately. Rate mismatch/jitter/missing data reject analysis. Firmware supports compile-time sample rate, bounded 100–250 Hz.

Official current kit page lists UNO R4 Minima, not Maker UNO. User's actual Maker UNO takes precedence; do not use R4 firmware, ADC resolution or connector claims. Sources and electrical precautions documented separately.

## Processing and concurrency
Background acquisition thread owns port, buffer and recording writes; lock protects snapshots. Bounded six-second analysis input, four-second central window, one-second edge guards; no pretend continuous clinical filtering. Configurable 1–40 Hz Butterworth bandpass, optional 50/60 Hz notch, valid Nyquist checks, detrending, finite/flat/clipping/transient checks, Welch PSD and band powers. Low-rate and irregular timing rejected. Bands 1–4, 4–8, 8–13, 13–30, 30–40 Hz; last is partial gamma only. Startup requires full context. Heuristic quality means usable for software analysis, not verified EEG or electrode contact.

Simulation starts only explicitly, deterministic sine mixture labeled simulated throughout API, UI and recordings. No classifier on simulation. Disconnect never switches source. Acquisition faults clear analysis; bounded reconnect attempts. Recording SQLite transactions; disconnected sessions finalized as interrupted, no merging across reconnections. Bounded history and streaming CSV exports. No patient identity fields.

## Experimental classifier
No EEG dataset exists locally; do not train or claim EEG accuracy. Provide manifest-driven offline trainer with explicit train/validation/test assignments, subject disjointness, source-content duplicate checks, task/provenance/license metadata. Reuse exact processing/features. Fit StandardScaler inside sklearn Pipeline on train only. Compare dummy baseline, logistic regression and small random forest on validation balanced accuracy. Evaluate selected model and baseline on held-out test once. Save confusion matrices, per-class metrics, balanced accuracy, valid ROC-AUC, plots, rejection audit and artifact hash/config/features/labels/versions. Runtime accepts only compatible local trusted artifacts, checks hash/config/feature order/units/rate. Prediction only for valid real windows; scores are uncalibrated class probabilities.

## UI and validation
New responsive EEG page: source controls, connection/recording/rate, raw counts waveform, PSD and band bars, unavailable-model explanation, session list/export. Empty/error/disconnected/simulated states explicit. Repair fake MRI telemetry and obsolete hardware assumptions. Tests cover filtering attenuation, invalid rates, gaps, NaN, flat/clipped signals, parser fragments, rollover, resets, disconnect/reconnect, session isolation/export, leakage and artifact mismatch. Browser smoke desktop/mobile and backend failures. Physical hardware absent: do not claim acquisition or firmware upload tested.

# EEG dataset and experimental model workflow

## Actual data status

No EEG recordings or labeled EEG dataset was found locally: **0 recordings, 0 subjects, no EEG labels/rates/durations/class distribution available to audit**. No EEG dataset was downloaded. No production EEG classifier is trained, and there are no measured EEG classification results. Synthetic signals are used only for software tests and clearly labeled demo acquisition. MRI image labels are not EEG training labels.

An experimental **eyes-open versus eyes-closed recording protocol** is a possible research task, not an implemented medical assessment. It needs documented placement, synchronized task annotations, multiple independent subjects, adequate durations, rejected-artifact accounting and new-session testing. Eyes/face artifacts can create misleading classification even with a high score. Task definition/validation and participant consent/data governance remain with project investigators.

One public option is [PhysioNet EEG Motor Movement/Imagery](https://physionet.org/content/eegmmidb/1.0.0/): EDF+ recordings, 64 channels, 160 Hz, including eyes-open/closed baselines; license listed as Open Data Commons Attribution v1.0. It was inspected through its documentation only, not downloaded. Its channel montage, device, units and task annotations differ from this kit. It requires an explicit offline channel/annotation adapter and independent domain-transfer evaluation. Do not rename physical EEG amplitudes to ADC counts or pretend this implementation has 64 channels. Current live-compatible trainer intentionally accepts only genuine 10-bit ADC-count recordings.

## Input manifest

Prepare one CSV per labeled continuous recording. Columns **exactly** `timestamp_s,value`, finite increasing timestamps in seconds and actual raw ADC counts. Minimum six seconds at default settings; prefer multiple long sessions per subject/task. Live exports include source and receipt metadata: preserve those originals, select only `source=serial`, map `device_seconds`→`timestamp_s` and `adc_counts`→`value` into a separate training copy. Do not include interrupted segments without checking continuity; trainer rejects gapped windows. Labels are supplied by experimental annotations, never predicted from band ratios. Do not train on demo files.

Example schema (paths and subject names below are illustrative; these files are not included):

```json
{
  "task": "Eyes-open versus eyes-closed under documented acquisition protocol",
  "provenance": "Investigator-collected Maker UNO/BioAmp recordings, protocol version and date",
  "license": "Actual documented consent and permitted use",
  "units": "adc_counts",
  "sample_rate": 250,
  "recordings": [
    {"path":"s01_open.csv", "subject":"s01", "label":"eyes_open", "split":"train"},
    {"path":"s01_closed.csv", "subject":"s01", "label":"eyes_closed", "split":"train"},
    {"path":"s02_open.csv", "subject":"s02", "label":"eyes_open", "split":"validation"},
    {"path":"s02_closed.csv", "subject":"s02", "label":"eyes_closed", "split":"validation"},
    {"path":"s03_open.csv", "subject":"s03", "label":"eyes_open", "split":"test"},
    {"path":"s03_closed.csv", "subject":"s03", "label":"eyes_closed", "split":"test"}
  ]
}
```

This tiny manifest illustrates fields, not a sufficient study. Use substantially more subjects and report subject-level uncertainty; one subject per split cannot support general claims. All recordings from a subject must stay in one split. Labels must appear in every split after quality rejection. Set optional `preprocessing` object fields exactly as `SignalConfig` when deviating from defaults; rate overrides cannot disagree with top-level rate. Units/converter range are fixed to this hardware's counts.

## Processing and leakage control

1. Require declared task/provenance/license, explicit subjects and split labels.
2. Reject duplicate source files, byte hashes and canonical numeric content; user must still verify subject IDs and detect reexported fragments/near duplicates.
3. Partition **before** windowing. Each six-second input is nonoverlapping, with center four seconds retained for features. Discard incomplete tails, report rejected full windows and class counts.
4. Reject nonfinite data instead of inventing missing values; reject timing gaps/jitter, clipping, flatlines and excessive steps. These are configurable engineering heuristics, not validated artifact detection.
5. Detrend, optional notch then Butterworth bandpass via second-order sections and forward/backward filtering. This is finite-window analysis with one-second guards, not causal instantaneous filtering. [SciPy sosfiltfilt](https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.sosfiltfilt.html) describes the filtering operation.
6. [Welch PSD](https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.welch.html) uses two-second subsegments, default 50% overlap, density scaling. Integrate frequency-bin power within declared bands. Edge bands reflect filter rolloff; 30–40 Hz is partial gamma. Spectral entropy normalizes discrete passband PSD; Hjorth derivatives use measured sample rate. Features are documented in saved ordering.
7. Fit StandardScaler on training features only inside logistic regression pipeline. Random forest and dummy prior use identical accepted windows. No per-window z-scoring silently destroys amplitude features.
8. Select using **validation balanced accuracy** across dummy prior, logistic regression and depth-limited random forest. Dummy may win; no forced advanced model.
9. Evaluate selected frozen model and dummy baseline on final test once. Do not tune after examining it. Saved test scores are window-level and within-subject correlated; subject bootstrap/CIs and prospective external validation are future work.

## Reproduction

```bash
.venv/bin/python train_eeg.py --manifest /path/to/manifest.json --output-dir eeg_model_candidate
```

Use a new output directory; trainer refuses overwriting. Inspect `evaluation.json`, rejected windows and validation scores before selecting deployment configuration. Outputs: `model.joblib`, `metadata.json` (model checksum, features, config, labels, versions, seed, provenance), `manifest.json` (file hashes), `evaluation.json`, `confusion_matrix.svg`.

Configure `BHM_EEG_MODEL_DIR=eeg_model_candidate` and restart backend. Loading requires exact sklearn/Python versions, feature order, units, dimension, label order and checksum. Inference additionally requires matching preprocessing configuration and a valid real-input window. Simulated data never reaches classifier. Probability scores are not calibrated diagnostic confidence. Joblib deserializes code: only load models you produced or trust locally; no model upload endpoint exists.

No additional large neural network is justified by unavailable data. Acquiring credible task labels and representative data matters before architecture complexity. MRI training and its GPU metrics remain separate.

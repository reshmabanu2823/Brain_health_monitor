# Signal methods and interpretation

CORTIA computes signal descriptors. It does not infer disorders, intelligence or psychological states. Engineering tests establish numerical behavior; they do not validate health interpretation or clinical performance.

## Acquisition and provenance

A selected Chords UNO-R4 channel supplies unsigned 14-bit ADC counts. Gain/reference calibration is not known, so raw units remain ADC counts, PSD uses ADC²/Hz, integrated power uses ADC², and FFT amplitude uses ADC counts. Relative power and ratios are dimensionless. No conversion to microvolts is asserted.

Raw CSV records local index, hardware counter, inferred device-relative time, receipt Unix time, raw count, missing count and discontinuity flag. Device time advances by `(1 + missing)/fs`; receipt timestamps are host batch arrival times, not exact ADC sampling timestamps. Packet counters wrap modulo 256, so loss counts are lower bounds when a long gap contains a full counter cycle. A receive timeout interrupts acquisition; no fabricated samples or gap interpolation enter analysis.

Sampling rate is the operator’s firmware setting (250 or 500 Hz). A five-second throughput check rejects mismatches exceeding 15%. This detects major configuration errors, not precision oscillator drift. No resampling is performed. Bandwidth 0.5–29.5 Hz is the configured analysis band; actual analog response and electrode placement require hardware verification.

## Windows, filtering and quality

Eight-second, nonoverlapping recording windows give 2,000 samples at 250 Hz or 4,000 at 500 Hz. Final partial windows remain raw only. Live monitoring and recordings have separate segmentation origins; recorded segment offsets, rather than live display alignment, determine stored session features.

Raw quality heuristics run before filtering:

- Flatline: raw SD below 0.5 ADC counts, or over 98% identical adjacent values.
- Clipping: over 1% of values at/below 1 or at/above 16,382.
- Abrupt step: maximum absolute first difference exceeds `max(2500, 20 × 1.4826 × MAD(first differences))` ADC counts.
- Missing sample, duplicate/corruption discontinuity: reject the affected window.
- Vanishing retained-band power: withhold unstable metrics.

These choices are **unvalidated artifact-screening heuristics**. They do not reliably identify every blink, muscle artifact, poor electrode contact or movement. Quality categories reflect engineering triggers, not confirmed physiological causes. No ICA or single-channel artifact reconstruction is claimed.

Usable windows are centered and filtered with a fourth-order Butterworth bandpass, represented as SOS and applied forward/backward using SciPy `sosfiltfilt`. Effective magnitude response is squared, edges are attenuated, and finite-window padding affects estimates near boundaries. Eight seconds limits low-frequency precision and is not a clinical recording duration recommendation. Power-line 50/60 Hz lies outside the retained band, so no separate notch is applied or claimed. The processing function supports an explicit notch inside the retained passband, although standard workstation acquisition does not enable it.

See [SciPy SOS filtering](https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.sosfiltfilt.html) and [Welch PSD](https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.welch.html).

## Spectral measurements

Welch PSD uses four-second periodic Hann segments with 50% overlap and constant detrending. Frequency bins are 0.25 Hz apart. PSD is a variance-density estimate, not a direct neural source measurement.

| Metric | Formula | Interpretation and limitations |
| --- | --- | --- |
| Delta power | `∫[0.5,4] PSD(f) df` | Slow-frequency signal power; sensitive to drift, motion and filtering near 0.5 Hz |
| Theta power | `∫[4,8] PSD(f) df` | Spectral power in this interval; task, state and artifacts matter |
| Alpha power | `∫[8,13] PSD(f) df` | Spectral power; eyes and electrode location strongly affect comparability |
| Beta power | `∫[13,29.5] PSD(f) df` | Truncated beta descriptor; muscle contamination possible; not full 13–30 Hz |
| Relative band power | `P_band / (P_delta + P_theta + P_alpha + P_beta)` | Compositional share; one band changing changes every share |
| Alpha/theta | `P_alpha / P_theta` | Exploratory spectral balance; not intelligence or relaxation score |
| Theta/beta | `P_theta / P_beta` | Exploratory balance; not a standalone attention or ADHD measure |
| Beta/alpha | `P_beta / P_alpha` | Exploratory balance; not anxiety or stress measurement |
| Peak frequency | `argmax PSD(f)` over retained bins | Largest bin, not necessarily a true oscillation or individual alpha frequency |
| FFT amplitude | `2 abs(rFFT(filtered × Hann)) / sum(Hann)` | Window-corrected amplitude descriptor; finite-window leakage remains |

Band power uses trapezoidal integration with interpolated interval endpoints. Shared endpoints do not double-count interval area. Ratios are null when their denominator is `<= max(1e-12, total_power × 1e-6)`. No gamma power is calculated.

All metrics require valid, sufficiently stationary recordings and consistent montage, task, eyes, filtering, hardware gain and bandwidth. None of these measurements distinguish neural activity from every possible artifact in one channel. Spectral features combine oscillatory and aperiodic activity; no periodic-source decomposition is implied.

Clinical caution for theta/beta interpretation is supported by the [American Academy of Neurology practice advisory](https://pmc.ncbi.nlm.nih.gov/articles/PMC5135022/). CORTIA applies no diagnostic rules from that device literature.

## Personalized baseline

Baseline eligibility: at least three distinct completed recordings; each has at least three usable windows. This is a software minimum, **not evidence that 24 seconds or three sessions establishes a clinically adequate baseline**. More recordings under controlled conditions are preferable for stable estimation. Different electrodes, gain, task, time of day and artifacts can change features.

For each feature, a session contributes its mean across usable windows for which the feature exists. Baseline statistics are calculated across session means, avoiding counting correlated windows as independent sessions:

- Mean: `μ = Σ x_i / n`.
- Median: middle ordered value (or average of middle pair).
- Sample SD: `s = sqrt(Σ(x_i−μ)²/(n−1))`.
- Deviation: `z = (current_session_mean−μ)/s`.

Baselines store cohort session IDs, context, acquisition config and statistics. Recalculation creates a new version. Task, eyes, montage and complete acquisition configuration must match; free-text notes do not determine comparability. Features absent from any selected session are excluded from baseline statistics.

SD `<=1e-12` yields null z-score. `|z|>=3` is an exploratory flag, not a p-value, validated threshold, clinical change or diagnosis. Small cohorts, feature distributions and multiple comparisons limit interpretation. A recording inside the baseline cohort is explicitly labeled in-sample and does not produce an independent change alert.

## Pattern detection

Separate event categories: acquisition gap, possible recording artifact, poor signal quality, and exploratory baseline deviation. Each stores trigger and explanation. No Isolation Forest is fitted to tiny baseline cohorts: statistical deviation is transparent, and unsupervised model validation would require an adequate independent dataset.

## MRI and explanations

MRI is a separate four-class 2D image classifier. It receives RGB 224×224 bilinear-resized images normalized by 255, preserving the original bundled TFLite preprocessing contract. No verified clinical performance, segmentation or out-of-distribution rejection is provided. DICOM support is limited to a single grayscale MR frame; imaging normalization is not a clinically validated MRI preprocessing protocol.

Grad-CAM requires the imported Keras model’s predicted class and probability vector to agree with TFLite (absolute tolerance 0.05) on the actual input, plus connected positive gradients. Attribution is withheld otherwise. Grad-CAM is class saliency, never lesion area or segmentation. The original TFLite export fails this agreement check on N1.JPG. The separately verified float32 export passes a stricter <=0.001 conversion check on nine images and produces actual Grad-CAM; see [export details](mri-export.md). Model-version score differences are not biological changes.

AI can only select predefined evidence statement IDs generated from persisted backend results. Extra text, unknown IDs, malformed JSON and duplicate IDs fail closed. Quality and limitations remain attached. Snapshot digests allow later tracing. This prevents invented model prose from appearing as measured evidence; it does not make any underlying heuristic clinically valid.

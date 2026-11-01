# Remaining validation plan

Authorization: original CORTIA brief, local-workstation design and user request to
complete remaining work. This extends verification, without generating production
EEG records, switching models, deploying remotely, or claiming clinical validity.

- [x] Add hand-calculated benchmark metric and dataset-integrity tests, observe
  missing harness failure, then implement test-only MRI benchmarking harness.
- [x] Evaluate selected float32 bundle on the existing 314-image evaluation manifest;
  verify file hashes and recorded split disjointness. Preserve per-image outputs,
  confusion matrix, per-class precision/recall/F1 and explicit training limitations.
- [x] Add real loopback HTTP contract tests for external-AI selection, consent,
  malformed/invented findings and upstream failures, with isolated temporary data.
- [x] Complete exporter no-usable-Grad-CAM rejection/cleanup coverage.
- [x] Stress-test acquisition and storage with accelerated 60-minute fixtures at
  250 and 500 Hz, exclusively inside temporary test directories. Verify every raw
  row and persisted segment. Report throughput/storage; never call this hardware validation.
- [x] Run full backend suite, review changes, and update validation/remaining reports.

Evidence: 52 backend tests pass; independent review finds no blocking defects.
314-image MRI benchmark: 75.48% accuracy, macro F1 0.70665, glioma recall 29.8%,
pituitary recall 55.6%; 100% class agreement with Keras, maximum absolute
probability difference 0.00002486234; 308 actual Grad-CAM, six correctly withheld.
2.7 million accelerated test samples / 900 windows pass every raw-row and stored
segment check. Reports and reproduction commands: `docs/completion-report.md`.

External gates: physical board and provider configuration requested asynchronously.
Independent clinical validation requires suitable data/protocol and cannot be
established by software tests or repeatedly reused repository images.

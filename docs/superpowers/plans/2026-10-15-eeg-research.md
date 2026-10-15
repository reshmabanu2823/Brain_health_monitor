# EEG research extension implementation plan

Goal: implement verified software paths for one-channel Maker UNO acquisition without disrupting MRI.
Spec: ../specs/2026-10-15-eeg-research-design.md
Execution: native in this session, as requested by user; no approval pause.

- [x] Audit repository and official hardware sources; record evidence and blockers.
- [x] Add failing tests for timestamped serial protocol, filtering, artifacts and windows.
- [x] Implement config, raw firmware, serial framing, signal validation and features.
- [x] Add SQLite session storage and background acquisition with explicit simulation and failure recovery.
- [x] Add manifest-driven subject-disjoint offline classifier workflow and validated model loading.
- [x] Integrate endpoints and separate EEG workspace into existing FastAPI app.
- [x] Remove fake telemetry and unsupported GPIO assumptions; preserve MRI interfaces.
- [x] Run tests, check browser desktop/mobile/error states, document real results and remaining blockers.

Review focus: disconnected data must not remain current; timestamp rollover must not create false gaps; recording errors must surface; source changes must not mix sessions; held-out subjects/content must never cross splits. Tests accompany owning modules.

Execution notes: retained existing dirty workspace as explicitly requested; no commits or remote changes. Independent final review identified excessive ASCII throughput at 500 Hz; added failing regression then capped firmware/host to 100–250 Hz. Full runtime check exposed pre-existing TensorFlow 2.15 incompatibility with bundled model artifacts; upgraded local CPU runtime and requirements to 2.21. Browser plugin unavailable; used regular Playwright. Exact results live in docs/VALIDATION.md.

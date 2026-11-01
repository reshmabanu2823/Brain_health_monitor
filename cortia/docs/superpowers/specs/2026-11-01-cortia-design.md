# CORTIA design

Fresh local workstation application, authorized by user’s complete development brief and “proceed”. FastAPI owns serial USB, authenticated REST/WebSocket APIs, SQLite metadata, private raw files, and separate EEG/MRI services. React/TypeScript/Vite serves unified dashboard. No legacy EEG/UI code reuse. MRI model artifacts alone imported from requested source, with provenance and actual model contract.

Chosen approach: local workstation. Alternative hosted backend plus local bridge adds synchronization and remote sensitive-data handling; deferred. Implementation choices delegated by “proceed”. No further design approval gate.

Hardware uses documented UNO-R4 binary Chords protocol: 6 ADC channels per packet, selected single channel, 14-bit unsigned big endian, counter, 500 Hz default or explicitly configured 250 Hz firmware. WHORU/START/STOP, 230400 baud. Native rate retained. No fake streams. Missing samples invalidate window. Raw ADC count units until gain calibration exists; never falsely show microvolts. Strict connection ownership; only owner sees live data. Single-process backend required.

Pipeline: validate counters/finite samples; retain immutable raw records; raw flatline/clipping/step heuristics; eight-second segments; fourth-order SOS bandpass 0.5–29.5 Hz; optional line notch only if frequency inside retained passband; Welch PSD (4-second Hann, 50% overlap); exact boundary interpolation for integrals. Delta/theta/alpha/beta cutoff at 29.5 Hz. No gamma. Artifact heuristics not validated artifact removal. No single-channel ICA claim. Segment outputs trace to raw offsets and config version.

Baseline uses >=3 completed sessions with >=3 valid windows each, identical eyes/task/montage/acquisition metadata. Each session contributes one feature average. Store frozen cohort IDs, mean/median/sample standard deviation. Undefined z-scores remain null. Three-SD flags exploratory; not disease or clinically meaningful change. Artifact, data gap and baseline deviations separately labeled.

MRI: independent four-class image classifier; original model tensor shape, preprocessing and labels validated. Raster upload size/dimension limits. MR single-frame DICOM optional. TFLite actual inference; Grad-CAM only from compatible Keras graph with matching classification, never substituted maps. Saliency not segmentation. Hash model files; history per user. No general MRI health diagnosis or clinical accuracy claims.

Auth: Argon2, opaque expiring hashed session tokens in HttpOnly same-site cookies; same-origin mutations; user filters on every data route, file and WebSocket. No seeded users. SQLite via SQLAlchemy, migration version table; PostgreSQL-compatible ORM types. Private application storage permissions. Rate-limited auth, bounded uploads and queues. Sensitive local storage requires OS disk encryption for at-rest encryption.

AI: evidence renderer always available. Optional external model can select only backend-generated statement IDs; never free-form medical/numeric text. Explicit per-request opt-in before external evidence transmission. Store evidence digest, provider, session and selected IDs.

Dashboard: Overview, Live EEG, Brainwaves, Baselines, MRI, History, Insights, Methods. Real empty/loading/error states. Export JSON/CSV reports from server records. Recordings include context and device config. Profile and session data isolated.

Verification: analytical test fixtures only in tests; real MRI artifact smoke tests; auth/isolation/API/WebSocket tests; serial parser tests with fragmentation/corruption/gaps; frontend build and browser flows. Physical hardware remains unverified absent board. Clinical validation outside scope.

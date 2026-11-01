# Remaining work — 2026-11-01 follow-up

## Needed to finish physical EEG acceptance

No `/dev/ttyACM*` or `/dev/ttyUSB*` device is attached in this environment.
Connect the UNO R4/BioAmp setup with the intended Chords firmware, then complete
the [hardware checklist](hardware.md). Record firmware identity, selected channel,
actual 250/500 Hz rate, montage, gain and bandwidth. Check real waveforms, packet
loss, USB interruption/reconnect, recording persistence and baseline creation from
actual comparable recordings. Software tests do not complete these checks.

Physical long-duration recording and signal-quality threshold validation require
that setup. Accelerated temporary test workloads now verify 2.7 million samples
across 60-minute fixtures at both supported rates; this is not real-time hardware
testing. No real baseline or EEG health results exist yet.

## Needed to live-test external AI

CORTIA has no configured endpoint, model or key. Put provider settings in local
`.env` using `.env.example`, then restart. Keep keys local. Generate an explanation
from an actual recording with explicit external-send consent; verify response
selection, saved evidence digest and provider failure handling. Backend evidence
summaries already work without a provider. Six real loopback HTTP tests now verify
consent, transport, evidence persistence, rejected findings and provider failures;
no live provider test has occurred.

## MRI follow-up

Grad-CAM now works with the separately derived, parity-checked float32 bundle.
The original export still withholds mismatching attribution. Both behaviors are
intentional. The full 314-image repository benchmark now verifies 100% winning-class
agreement with Keras and actual Grad-CAM on 308 images; six correctly withhold
attribution because no positive activation exists.

Benchmark accuracy is 75.48%, with only 29.8% glioma recall and 55.6% pituitary recall.
The selected model manifest now exposes these known limitations. Model improvement
and independent medical/clinical validation remain separate research work. Original
training overlap and patient independence are unknown; this reused repository
dataset cannot establish diagnostic suitability.

Independent review finds no blocking software defects. Exporter tests now also
verify rejection and staging cleanup when no image yields usable Grad-CAM.

A separate EfficientNetV2S candidate now passes actual inference, export parity,
Grad-CAM and browser checks. On the same 314 images, accuracy rises to 80.89% and
glioma recall to 59.5%, but no-tumor recall falls to 85.2%; no-tumor images assigned
a tumor class increase from 1 to 12. It remains experimental. Source training
cannot be fully reproduced: 5,230 recorded training/validation image files are
unavailable. [Full comparison and provenance](mri-candidate.md).

## Optional future deployment work

Current agreed design is a single-process local workstation. Remote hosting,
PostgreSQL driver/migrations, multi-process device coordination and storage
compression/retention are future extensions. A remote server also needs a local
hardware bridge to access the user's USB device. None has been deployed.

## Current verified delivery

77 backend tests, six browser cases passing against both active and candidate
bundles including actual Grad-CAM persistence,
production build and Python dependency compatibility pass. App, API health and
local API docs return HTTP 200 at `http://127.0.0.1:8010`.
See [completion report](completion-report.md), [validation evidence](validation.md)
and [MRI export provenance](mri-export.md).

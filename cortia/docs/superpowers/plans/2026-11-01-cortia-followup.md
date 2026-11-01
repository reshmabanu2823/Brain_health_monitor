# CORTIA remaining-work plan

Existing authorization: original full brief, prior “proceed”, and current request to continue remaining work.
Spec: `docs/superpowers/specs/2026-11-01-cortia-design.md`.

## MRI export and attribution

The original Keras graph produces Grad-CAM. Its supplied TFLite export differs by
about 0.095 on N1.JPG. An experimental unoptimized float32 export differs by less
than 0.000005. Derive a new version from the existing Keras weights without training,
keep the original bundle intact, and record source hashes and conversion settings.
Reject activation unless actual images pass class agreement and maximum absolute
probability difference <=0.001. Preserve per-image attribution agreement checks.

- [x] Write export tests for source tampering, empty verification sets, existing output protection, and real inference/Grad-CAM.
- [x] Observe failure, implement exporter, verify tests.
- [x] Export to a separate directory and verify images from all four dataset classes.
- [x] Activate locally through ignored `.env`; document changed model scores and hashes.
- [x] Verify backend, build, browser MRI attribution/persistence, dependencies and live health.

Evidence: 41 backend tests, six browser tests (derived bundle with Grad-CAM required),
production build and dependency compatibility pass. Nine real images pass <=0.001
export parity, maximum observed difference 0.000004955654; all nine Grad-CAM pass.
Root, API health and local API docs return HTTP 200 on port 8010.
Independent read-only review: no blocking findings; source and all nine fixture
hashes independently checked. Optional additional coverage for all-Grad-CAM-unavailable
export rejection is recorded in `docs/remaining.md`.

## External constraints

- Physical serial acceptance cannot run: no ttyACM/ttyUSB device present.
- Live external AI cannot run: no endpoint/model/key configured.
- Remote deployment and clinical validation remain outside verified local workstation delivery.

## Review focus

Never overwrite original artifacts or an existing derived bundle. Verify source integrity
before conversion. Publish output only after all images pass parity. Failed checks leave
no usable output bundle. Reports retain actual artifact SHA-256; historical predictions
remain unchanged. Attribution must still fail closed on disagreement.

# API and storage contract

Interactive OpenAPI: `/docs`. Machine schema: `/openapi.json`. Both serve locally. All data routes require the `cortia_session` HttpOnly cookie. Public health output contains no user data. Responses prevent caching and embedding.

## Endpoints

| Method | Path | Input / output |
| --- | --- | --- |
| POST | `/api/auth/register` | `{username,password}`; creates account and eight-hour cookie |
| POST | `/api/auth/login` | Credentials; creates session cookie |
| POST | `/api/auth/logout` | Revokes current token, removes cookie |
| GET | `/api/auth/me` | Owner profile `{id,username,created_at}` |
| GET | `/api/health` | Process status and explicit validation flags |
| GET | `/api/devices/ports` | Available serial port descriptions |
| GET | `/api/devices/status` | Owner-scoped hardware state and recent signal |
| POST | `/api/devices/connect` | `{port,sampling_hz:250|500,channel:0..5}` |
| POST | `/api/devices/disconnect` | Releases owner’s acquisition, interrupts active recording |
| WS | `/api/live` | Cookie-authenticated snapshots about every 150 ms |
| POST | `/api/sessions/start` | `{eyes:"open"|"closed",task,montage,notes?}`; requires received live packets |
| POST | `/api/sessions/stop` | Finalizes recording, keeps trailing partial raw window |
| GET | `/api/sessions?limit=100&offset=0` | Owner recordings, newest first, maximum 500 per page |
| GET | `/api/sessions/{id}` | Context, acquisition config, counts, session means, latest segment and baseline comparison |
| GET | `/api/sessions/{id}/segments?limit=200&offset=0` | Up to 1,000 stored analysis windows with raw offsets |
| GET | `/api/sessions/{id}/anomalies` | Categorized engineering/statistical events, capped at 1,000 |
| GET | `/api/sessions/{id}/raw` | Raw CSV download; completed/interrupted recordings only |
| GET | `/api/sessions/{id}/report` | JSON session report plus matched baseline comparison; records export digest |
| GET | `/api/baselines` | Frozen personal baseline versions, newest first, capped at 100 |
| POST | `/api/baselines` | `{session_ids:[...]}`; >=3 distinct completed comparable sessions, >=3 usable windows each |
| GET | `/api/mri/status` | Model/runtime availability and provenance |
| POST | `/api/mri/predict` | Multipart `file`; bounded validated image, actual inference |
| GET | `/api/mri/history` | Owner uploads and predictions, latest 100 |
| GET | `/api/mri/{id}/image` | Owner’s decoded PNG pixels; identity metadata removed |
| GET | `/api/mri/{id}/report` | Original upload digest, prediction and model provenance JSON |
| POST | `/api/sessions/{id}/explanations` | `{use_external_ai:false,consent_to_send_metrics:false}` |
| GET | `/api/sessions/{id}/explanations` | Owner’s evidence snapshots, latest 100 |

Different-user and missing resources both return 404. Anonymous requests return 401; schema errors 422; hardware conflicts 409; oversized bodies 413; unavailable model 503; invalid/unavailable external AI 502. Invalid AI configuration or missing consent returns 422. Internal errors return generic text without sensitive input.

## WebSocket data

```
{
  "state": "disconnected|connecting|streaming|busy",
  "live_available": true,
  "stream_id": 1,
  "recording_id": "uuid-or-null",
  "recording_samples": 250,
  "config": {"sampling_hz": 500, "channel": 0, "units": "ADC_count", "...": "..."},
  "samples": [{"sequence": 1, "sample_time": 0.002,
               "received_at": 1790000000.0, "counter": 1,
               "value": 8192, "missing": 0, "discontinuity": false}],
  "latest": null
}
```

Numbers above illustrate the **schema only**, not a recording or seeded data. A different user sees `busy`, no samples, no recording ID and no latest analysis. `live_available` requires recently received real packets. `stream_id` changes on acquisition generation, resetting server/client waveform cursors. A bounded 2,500-point live ring may lose visual points for slow clients; raw recording persistence is separate. A reconnect does not imply reconstruction of missed visual data. Token revocation is checked during the stream.

Each computed window includes pipeline version, sample count/rate, quality reasons, band boundaries, power/relative power/ratios, PSD, FFT, peak and limitations. Excluded windows have null power/spectral interpretation; quality metadata remains. Denominator-unstable ratios and baseline z-scores are JSON null, never Infinity/NaN.

## Schema v1

| Table | Responsibility / references |
| --- | --- |
| `schema_versions` | Explicit initial schema version |
| `users` | Unique normalized username, Argon2 hash, timestamp |
| `auth_tokens` | SHA-256 token digest, owner, expiry; plaintext token only in client cookie |
| `eeg_devices` | Owner-scoped acquisition configuration at connection |
| `recording_sessions` | Owner/device IDs, context/config, lifecycle, counts, raw path, feature means |
| `processed_segments` | Session, half-open raw sample offsets, versioned analysis result JSON |
| `extracted_features` | Per-segment numerical feature vector |
| `personalized_baselines` | Owner, frozen session cohort, context/config, statistics |
| `anomaly_records` | Session/segment references, category, trigger and explanation |
| `mri_uploads` | Owner, generated private path, source content digest, timestamp |
| `mri_predictions` | One actual model prediction per upload, explanation availability and model hash |
| `ai_explanations` | Owner/session, evidence digest, provider/type and rendered statements |
| `reports` | Session, export timestamp/format and content digest |

Calculated metrics live inside versioned segment results and session feature means; separate metric rows would duplicate the same results without additional provenance. Raw EEG stays in private append-only CSV, not a row per sample in SQLite. Images are decoded PNG files with generated UUID paths. No private data directory is statically mounted. Raw CSV is larger than binary storage; long-duration deployments should add compressed chunks and tested retention/export controls.

Foreign keys are enforced in SQLite. ORM types are portable to PostgreSQL, but PostgreSQL runtime and migrations beyond v1 require separate validation. Single local backend process is a hard operational constraint.

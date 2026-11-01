import { useEffect, useRef, useState } from "react";
import {
  ScanLine,
  Upload,
  Loader2,
  Download,
  ChevronRight,
  Circle,
} from "lucide-react";
import type { MRI, Action } from "../types";
import { api, date, number, title } from "../api";
import { Card, Empty, Badge, Note } from "../ui";

export function MRIPage({
  mris,
  action,
  busy,
  refresh,
  notify,
}: {
  mris: MRI[];
  action: Action;
  busy: boolean;
  refresh: () => Promise<void>;
  notify: (s: string) => void;
}) {
  const [status, setStatus] = useState<{
    available: boolean;
    reason?: string;
  } | null>(null);
  const [selected, setSelected] = useState<MRI | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const input = useRef<HTMLInputElement>(null);
  useEffect(() => {
    void api<{ available: boolean; reason?: string }>("/mri/status")
      .then(setStatus)
      .catch((e) => setStatus({ available: false, reason: e.message }));
  }, []);
  const result = selected || mris[0];
  async function upload() {
    if (!file) return;
    const data = new FormData();
    data.append("file", file);
    const row = await api<MRI>("/mri/predict", { method: "POST", body: data });
    setSelected(row);
    setFile(null);
    if (input.current) input.current.value = "";
    await refresh();
    notify("Actual model inference saved.");
  }
  return (
    <>
      <div className="context-strip">
        <ScanLine size={18} />
        <span>Four-class image classifier · independent of EEG</span>
        <Badge tone={status?.available ? "green" : "amber"}>
          {status
            ? status.available
              ? "Model ready"
              : "Model unavailable"
            : "Checking model"}
        </Badge>
      </div>
      <div className="two-column">
        <Card title="Upload an MRI image" subtitle="Single image · up to 10 MB">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void action(upload);
            }}
          >
            <div className="upload-zone">
              <span className="empty-icon">
                <Upload size={26} />
              </span>
              <h3>Choose your scan</h3>
              <p>
                PNG, JPEG, WEBP, BMP, TIFF
                <br />
                Single-frame MR DICOM with optional decoder
              </p>
              <input
                ref={input}
                id="mri-file"
                type="file"
                aria-label="MRI image"
                accept=".png,.jpg,.jpeg,.webp,.bmp,.tif,.tiff,.dcm,.dicom"
                onChange={(e) => setFile(e.target.files?.[0] || null)}
              />
              <label htmlFor="mri-file" className="secondary">
                {file ? file.name : "Browse files"}
              </label>
              {file && (
                <span className="fine-print">
                  {number(file.size / 1024, 0)} KB selected
                </span>
              )}
            </div>
            <button
              className="primary wide"
              disabled={busy || !file || !status?.available}
            >
              {busy ? (
                <Loader2 className="spin" size={17} />
              ) : (
                <ScanLine size={17} />
              )}
              Run model analysis
            </button>
          </form>
          {status && !status.available && <Note>{status.reason}</Note>}
          <Note>
            Raster validation checks file integrity, not whether an image is
            MRI. Upload only appropriate de-identified scans.
          </Note>
        </Card>
        <Card
          title="Model scope"
          subtitle="Understand what this model can establish"
        >
          <div className="scope-list">
            {[
              "Glioma tumor class",
              "Meningioma tumor class",
              "Pituitary tumor class",
              "No tumor class",
            ].map((t) => (
              <div key={t}>
                <Circle size={9} />
                {t}
              </div>
            ))}
          </div>
          <Note>
            Outputs are model class predictions, not diagnoses. “No tumor” is a
            dataset label, not confirmation of a healthy brain.
          </Note>
          <p className="muted padded-text">
            The loaded classifier analyzes resized 2D images. It
            does not assess general brain health, lesion size, or severity.
            Scores are not calibrated clinical confidence.
          </p>
        </Card>
      </div>
      {result ? (
        <Card
          title="Classification result"
          subtitle={`${date(result.created_at)} · model prediction`}
          action={
            <a
              className="secondary"
              href={`/api/mri/${result.id}/report`}
              download
            >
              <Download size={15} />
              Export
            </a>
          }
        >
          <div className="mri-result">
            <figure>
              <img
                src={`/api/mri/${result.id}/image`}
                alt="Uploaded MRI image"
              />
              <figcaption>
                Uploaded image · identity metadata removed
              </figcaption>
            </figure>
            <div>
              <span className="eyebrow">PREDICTED DATASET CLASS</span>
              <h2 className="result-label">{title(result.result.label)}</h2>
              <Badge>Model prediction · not diagnosis</Badge>
              <div className="probabilities">
                {Object.entries(result.result.probabilities).map(
                  ([key, value]) => (
                    <div key={key}>
                      <div>
                        <span>{title(key)}</span>
                        <strong>{number(value * 100, 1)}%</strong>
                      </div>
                      <div className="probability-track">
                        <span style={{ width: `${value * 100}%` }} />
                      </div>
                    </div>
                  ),
                )}
              </div>
              <p className="fine-print">
                Preprocessing: {result.result.preprocessing}
              </p>
            </div>
            {result.result.explainability.available ? (
              <figure>
                <img
                  src={result.result.explainability.overlay}
                  alt="Actual classifier Grad-CAM saliency overlay"
                />
                <figcaption>
                  Grad-CAM · classifier saliency, not lesion segmentation
                </figcaption>
              </figure>
            ) : null}
          </div>
          {!result.result.explainability.available && (
            <Note>{result.result.explainability.reason}</Note>
          )}
          <details>
            <summary>Model provenance & limitations</summary>
            <p className="hash">SHA-256: {result.result.model_sha256}</p>
            {result.result.limitations.map((l) => (
              <p key={l} className="muted">
                {l}
              </p>
            ))}
          </details>
        </Card>
      ) : (
        <Card>
          <Empty
            title="No MRI predictions yet"
            text="Results appear after a valid upload completes actual model inference."
          />
        </Card>
      )}
      {mris.length > 0 && (
        <Card title="Previous MRI analyses">
          <div className="session-rows">
            {mris.map((m) => (
              <button key={m.id} onClick={() => setSelected(m)}>
                <span className="row-icon">
                  <ScanLine size={18} />
                </span>
                <div>
                  <strong>{title(m.result.label)}</strong>
                  <span>{date(m.created_at)}</span>
                </div>
                <Badge>Model prediction</Badge>
                <ChevronRight size={16} />
              </button>
            ))}
          </div>
        </Card>
      )}
    </>
  );
}

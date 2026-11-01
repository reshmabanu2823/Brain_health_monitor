import { useEffect, useState } from "react";
import { Loader2, Radio, RefreshCw, Circle, Square } from "lucide-react";
import type { Live, Action } from "../types";
import { api, post } from "../api";
import { Note, Badge } from "../ui";

export function DeviceSetup({
  live,
  busy,
  action,
}: {
  live: Live;
  busy: boolean;
  action: Action;
}) {
  const [ports, setPorts] = useState<{ port: string; description: string }[]>(
    [],
  );
  const [port, setPort] = useState("");
  const [hz, setHz] = useState(500);
  const [channel, setChannel] = useState(0);
  const refresh = async () => {
    const rows =
      await api<{ port: string; description: string }[]>("/devices/ports");
    setPorts(rows);
    if (rows.length && !port) setPort(rows[0].port);
  };
  useEffect(() => {
    void action(refresh);
  }, []);
  return (
    <div className="form-stack">
      <label>
        Serial device
        <div className="inline-input">
          <select
            aria-label="Serial device"
            value={port}
            onChange={(e) => setPort(e.target.value)}
            disabled={live.state !== "disconnected"}
          >
            <option value="">
              {ports.length ? "Select device" : "No serial devices found"}
            </option>
            {ports.map((p) => (
              <option key={p.port} value={p.port}>
                {p.port} · {p.description}
              </option>
            ))}
          </select>
          <button
            className="icon-button bordered"
            aria-label="Refresh serial devices"
            onClick={() => void action(refresh)}
            disabled={busy}
          >
            <RefreshCw size={16} />
          </button>
        </div>
      </label>
      <div className="two-fields">
        <label>
          Firmware sample rate
          <select
            value={hz}
            onChange={(e) => setHz(Number(e.target.value))}
            disabled={live.state !== "disconnected"}
          >
            <option value={500}>500 Hz · Chords default</option>
            <option value={250}>250 Hz · modified firmware</option>
          </select>
        </label>
        <label>
          EEG input
          <select
            value={channel}
            onChange={(e) => setChannel(Number(e.target.value))}
            disabled={live.state !== "disconnected"}
          >
            {[0, 1, 2, 3, 4, 5].map((n) => (
              <option key={n} value={n}>
                A{n} · channel {n + 1}
              </option>
            ))}
          </select>
        </label>
      </div>
      <Note>
        Match firmware settings. CORTIA checks observed throughput and
        interrupts acquisition on substantial mismatch.
      </Note>
      {live.state === "disconnected" ? (
        <button
          className="primary wide"
          disabled={busy || !port}
          onClick={() =>
            void action(async () => {
              await post("/devices/connect", {
                port,
                sampling_hz: hz,
                channel,
              });
            })
          }
        >
          {busy ? <Loader2 className="spin" size={16} /> : <Radio size={16} />}
          Connect hardware
        </button>
      ) : live.state === "busy" ? (
        <Badge tone="amber">Hardware owned by another user</Badge>
      ) : (
        <button
          className="secondary wide"
          disabled={busy}
          onClick={() =>
            void action(async () => {
              await post("/devices/disconnect");
            })
          }
        >
          Disconnect hardware
        </button>
      )}
    </div>
  );
}
export function RecordingControls({
  live,
  busy,
  action,
  refresh,
  notify,
}: {
  live: Live;
  busy: boolean;
  action: Action;
  refresh: () => Promise<void>;
  notify: (s: string) => void;
}) {
  const [eyes, setEyes] = useState("closed"),
    [task, setTask] = useState("rest"),
    [montage, setMontage] = useState(""),
    [notes, setNotes] = useState("");
  return (
    <form
      className="form-stack"
      onSubmit={(e) => {
        e.preventDefault();
        void action(async () => {
          await post("/sessions/start", { eyes, task, montage, notes });
          await refresh();
          notify("Recording started from live hardware.");
        });
      }}
    >
      <div className="two-fields">
        <label>
          Eyes
          <select
            value={eyes}
            onChange={(e) => setEyes(e.target.value)}
            disabled={!!live.recording_id}
          >
            <option value="closed">Closed</option>
            <option value="open">Open</option>
          </select>
        </label>
        <label>
          Task
          <input
            required
            maxLength={100}
            value={task}
            onChange={(e) => setTask(e.target.value)}
            disabled={!!live.recording_id}
          />
        </label>
      </div>
      <label>
        Electrode placement / reference
        <input
          required
          maxLength={100}
          placeholder="e.g. Fp1 referenced to left ear"
          value={montage}
          onChange={(e) => setMontage(e.target.value)}
          disabled={!!live.recording_id}
        />
      </label>
      <label>
        Session notes <span className="optional">optional</span>
        <input
          maxLength={1000}
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          disabled={!!live.recording_id}
          placeholder="Conditions worth remembering"
        />
      </label>
      {live.recording_id ? (
        <button
          type="button"
          className="stop wide"
          disabled={busy}
          onClick={() =>
            void action(async () => {
              await post("/sessions/stop");
              await refresh();
              notify(
                "Recording saved. Raw data and analysis remain traceable.",
              );
            })
          }
        >
          <Square size={15} fill="currentColor" />
          Stop & save recording
        </button>
      ) : (
        <button
          className="primary wide"
          disabled={busy || !live.live_available}
        >
          <Circle size={14} fill="currentColor" />
          Start recording
        </button>
      )}
      <p className="fine-print">
        Keep still and follow your electrode manufacturer’s instructions. No
        signal is generated when hardware is disconnected.
      </p>
    </form>
  );
}

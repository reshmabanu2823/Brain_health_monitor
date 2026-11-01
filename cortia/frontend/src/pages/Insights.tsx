import { useState, useEffect } from "react";
import { Sparkles, Loader2 } from "lucide-react";
import type { Recording, Insight, Action } from "../types";
import { api, post, date } from "../api";
import { Card, Empty, Badge, Note } from "../ui";

export function InsightsPage({
  sessions,
  action,
  busy,
}: {
  sessions: Recording[];
  action: Action;
  busy: boolean;
}) {
  const [sid, setSid] = useState(sessions[0]?.id || "");
  const [external, setExternal] = useState(false);
  const [insights, setInsights] = useState<Insight[]>([]);
  useEffect(() => {
    let cancelled = false;
    setInsights([]);
    if (sid)
      void action(async () => {
        const rows = await api<Insight[]>(`/sessions/${sid}/explanations`);
        if (!cancelled) setInsights(rows);
      });
    return () => {
      cancelled = true;
    };
  }, [sid]);
  return (
    <>
      <div className="insight-banner">
        <Sparkles size={25} />
        <div>
          <h2>Understanding starts with evidence.</h2>
          <p>
            Explanations draw from backend-calculated measurements. Actual data
            remains separate from interpretation.
          </p>
        </div>
      </div>
      <Card
        title="Explain a recording"
        subtitle="Backend evidence summaries work without an external AI service"
      >
        {sessions.length ? (
          <div className="form-stack">
            <label>
              Recording
              <select value={sid} onChange={(e) => setSid(e.target.value)}>
                {sessions.map((s) => (
                  <option key={s.id} value={s.id}>
                    {date(s.started_at)} · {s.context.task}
                  </option>
                ))}
              </select>
            </label>
            <label className="checkbox-row">
              <input
                type="checkbox"
                checked={external}
                onChange={(e) => setExternal(e.target.checked)}
              />
              <span>
                Use configured external AI to select evidence statements
                <small>
                  I consent to send curated metrics. No raw EEG, images, or
                  account details are sent.
                </small>
              </span>
            </label>
            <button
              className="primary fit"
              disabled={busy || !sid}
              onClick={() =>
                void action(async () => {
                  const item = await post<Insight>(
                    `/sessions/${sid}/explanations`,
                    {
                      use_external_ai: external,
                      consent_to_send_metrics: external,
                    },
                  );
                  setInsights((rows) => [item, ...rows]);
                })
              }
            >
              {busy ? (
                <Loader2 className="spin" size={16} />
              ) : (
                <Sparkles size={16} />
              )}
              Generate explanation
            </button>
          </div>
        ) : (
          <Empty
            title="Measurements come first"
            text="Record EEG before requesting an explanation. No values or clinical findings are invented to fill this view."
          />
        )}
      </Card>
      {insights.map((i) => (
        <Card
          key={i.id}
          title={
            i.ai_generated
              ? "AI-assisted evidence selection"
              : "Verified evidence summary"
          }
          subtitle={`${date(i.created_at)} · ${i.provider}`}
          action={
            <Badge>
              {i.ai_generated ? "AI assisted" : "Backend generated"}
            </Badge>
          }
        >
          <div className="insight-statements">
            {i.statements.map((s, index) => (
              <p key={s}>
                <span>{String(index + 1).padStart(2, "0")}</span>
                {s}
              </p>
            ))}
          </div>
          <details>
            <summary>Evidence provenance</summary>
            <p className="hash">Snapshot SHA-256: {i.evidence_digest}</p>
            <p className="muted">
              Summaries preserve their original evidence snapshot. They may
              predate newer baseline versions.
            </p>
          </details>
        </Card>
      ))}
      <Note>
        External AI can select only pre-approved evidence statements. It cannot
        add measurements, free-form diagnoses, or unsupported findings.
      </Note>
    </>
  );
}

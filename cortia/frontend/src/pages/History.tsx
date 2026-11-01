import { useState } from "react";
import { Download } from "lucide-react";
import type { Recording } from "../types";
import { date, number, title } from "../api";
import { Trends } from "../charts";
import { Card, Empty, Badge, Note } from "../ui";

export function HistoryPage({
  sessions,
  choose,
}: {
  sessions: Recording[];
  choose: (id: string) => Promise<void>;
}) {
  const [left, setLeft] = useState(""),
    [right, setRight] = useState("");
  const a = sessions.find((s) => s.id === left),
    b = sessions.find((s) => s.id === right);
  const valid = sessions.filter((s) => s.valid_windows > 0);
  return (
    <>
      <Card
        title="Recording history"
        subtitle="Raw samples, quality decisions, and calculated features remain linked"
      >
        {sessions.length ? (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Recording</th>
                  <th>Context</th>
                  <th>Samples</th>
                  <th>Quality windows</th>
                  <th>Status</th>
                  <th>Reports</th>
                </tr>
              </thead>
              <tbody>
                {sessions.map((s) => (
                  <tr key={s.id}>
                    <td>
                      <button
                        className="table-link"
                        onClick={() => void choose(s.id)}
                      >
                        {date(s.started_at)}
                      </button>
                    </td>
                    <td>
                      {s.context.task} · {s.context.eyes}
                      <small>{s.context.montage}</small>
                    </td>
                    <td>
                      {number(s.sample_count, 0)}
                      <small>{s.missing_samples} missing</small>
                    </td>
                    <td>
                      {s.valid_windows} usable
                      <small>{s.invalid_windows} excluded</small>
                    </td>
                    <td>
                      <Badge tone={s.state === "completed" ? "green" : "amber"}>
                        {title(s.state)}
                      </Badge>
                    </td>
                    <td>
                      <div className="report-links">
                        <a
                          href={`/api/sessions/${s.id}/report`}
                          download
                          title="Download JSON report"
                        >
                          JSON <Download size={12} />
                        </a>
                        {s.state !== "recording" && (
                          <a
                            href={`/api/sessions/${s.id}/raw`}
                            download
                            title="Download raw CSV"
                          >
                            CSV <Download size={12} />
                          </a>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <Empty
            title="No recordings yet"
            text="Recordings appear here after hardware acquisition starts. Exports contain actual stored data."
          />
        )}
      </Card>
      <Card
        title="Band power over time"
        subtitle="Session mean relative power · comparison requires matched recording conditions"
      >
        {valid.length >= 2 ? (
          <Trends sessions={valid} />
        ) : (
          <Empty
            title="Trends need more recordings"
            text="At least two sessions with usable windows are needed to display change over time."
          />
        )}
      </Card>
      <Card
        title="Compare two sessions"
        subtitle="Descriptive differences only; context and hardware affect interpretation"
      >
        {valid.length >= 2 ? (
          <>
            <div className="two-fields">
              <label>
                Reference session
                <select value={left} onChange={(e) => setLeft(e.target.value)}>
                  <option value="">Select reference</option>
                  {valid.map((s) => (
                    <option key={s.id} value={s.id}>
                      {date(s.started_at)} · {s.context.task}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Comparison session
                <select
                  value={right}
                  onChange={(e) => setRight(e.target.value)}
                >
                  <option value="">Select comparison</option>
                  {valid
                    .filter((s) => s.id !== left)
                    .map((s) => (
                      <option key={s.id} value={s.id}>
                        {date(s.started_at)} · {s.context.task}
                      </option>
                    ))}
                </select>
              </label>
            </div>
            {a && b && (
              <>
                <Note>
                  {JSON.stringify({ ...a.context, notes: "" }) !==
                    JSON.stringify({ ...b.context, notes: "" }) ||
                  JSON.stringify(a.config) !== JSON.stringify(b.config)
                    ? "Recording conditions differ. Changes may reflect acquisition or task differences."
                    : "Recording context matches. Differences remain descriptive, not clinical findings."}
                </Note>
                <div className="table-scroll">
                  <table>
                    <thead>
                      <tr>
                        <th>Feature</th>
                        <th>Reference</th>
                        <th>Comparison</th>
                        <th>Difference</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(a.features)
                        .filter(([k]) => k in b.features)
                        .map(([k, v]) => (
                          <tr key={k}>
                            <td>{title(k)}</td>
                            <td>{number(v, 4)}</td>
                            <td>{number(b.features[k], 4)}</td>
                            <td>{number(b.features[k] - v, 4)}</td>
                          </tr>
                        ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </>
        ) : (
          <Empty
            title="Comparison not available"
            text="Record two usable sessions to compare measured features."
          />
        )}
      </Card>
    </>
  );
}

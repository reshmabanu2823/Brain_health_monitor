import { useEffect, useState } from "react";
import { Waves, ChevronRight } from "lucide-react";
import type { Recording, Comparison, Analysis } from "../types";
import { api, date, title, number } from "../api";
import { Card, Empty, Badge, Note } from "../ui";

export function SessionRows({
  sessions,
  choose,
}: {
  sessions: Recording[];
  choose: (id: string) => Promise<void>;
}) {
  return (
    <div className="session-rows">
      {sessions.map((s) => (
        <button key={s.id} onClick={() => void choose(s.id)}>
          <span className="row-icon">
            <Waves size={18} />
          </span>
          <div>
            <strong>
              {title(s.context.task)} · eyes {s.context.eyes}
            </strong>
            <span>
              {date(s.started_at)} · {s.valid_windows} usable windows
            </span>
          </div>
          <Badge
            tone={
              s.state === "completed"
                ? "green"
                : s.state === "recording"
                  ? "amber"
                  : "neutral"
            }
          >
            {title(s.state)}
          </Badge>
          <ChevronRight size={16} />
        </button>
      ))}
    </div>
  );
}
export function BaselineComparison({ comparison }: { comparison: Comparison }) {
  return (
    <Card
      title="Personal baseline comparison"
      subtitle={
        comparison.included_in_baseline
          ? "This recording is included in baseline: in-sample comparison."
          : "Exploratory session-level standard deviations"
      }
    >
      {!comparison.available ? (
        <Empty title="No matching baseline" text={comparison.reason} />
      ) : (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Feature</th>
                <th>Current</th>
                <th>Baseline mean</th>
                <th>Z-score</th>
                <th>Interpretation</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(comparison.deviations || {}).map(([key, v]) => (
                <tr key={key}>
                  <td>{title(key)}</td>
                  <td>{number(v.value, 4)}</td>
                  <td>{number(v.baseline_mean, 4)}</td>
                  <td>{number(v.z_score)}</td>
                  <td>
                    <Badge tone={v.flagged ? "amber" : "neutral"}>
                      {v.flagged
                        ? "Exploratory flag"
                        : v.z_score === null
                          ? "Insufficient variance"
                          : "Within 3 SD"}
                    </Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

export function SessionEvidence({
  session,
  onWindow,
}: {
  session: Recording;
  onWindow: (result: Analysis) => void;
}) {
  const [segments, setSegments] = useState<
    { id: string; start_index: number; end_index: number; result: Analysis }[]
  >([]);
  const [events, setEvents] = useState<
    {
      id: string;
      category: string;
      details: { reason?: string; explanation?: string };
    }[]
  >([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [active, setActive] = useState("");
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");
    setSegments([]);
    setEvents([]);
    setActive("");
    Promise.all([
      api<typeof segments>(`/sessions/${session.id}/segments`),
      api<typeof events>(`/sessions/${session.id}/anomalies`),
    ])
      .then(([windows, flags]) => {
        if (!cancelled) {
          setSegments(windows);
          setEvents(flags);
        }
      })
      .catch((e) => {
        if (!cancelled) setError(e.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [session.id]);
  return (
    <>
      <Card
        title="Recorded analysis windows"
        subtitle="Select a window to inspect its spectrum. Raw offsets remain traceable."
      >
        {error ? (
          <div className="error" role="alert">
            {error}
          </div>
        ) : loading ? (
          <p className="muted">Loading stored windows…</p>
        ) : segments.length ? (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Window</th>
                  <th>Raw sample interval</th>
                  <th>Quality</th>
                  <th>Flags</th>
                  <th>Inspect</th>
                </tr>
              </thead>
              <tbody>
                {segments.map((segment, index) => (
                  <tr key={segment.id}>
                    <td>{index + 1}</td>
                    <td>
                      {segment.start_index}–{segment.end_index - 1}
                    </td>
                    <td>
                      <Badge
                        tone={segment.result.quality.usable ? "green" : "amber"}
                      >
                        {segment.result.quality.usable ? "Usable" : "Excluded"}
                      </Badge>
                    </td>
                    <td>
                      {segment.result.quality.reasons.map(title).join(", ") ||
                        "No configured flags"}
                    </td>
                    <td>
                      <button
                        className="text-button"
                        onClick={() => {
                          setActive(segment.id);
                          onWindow(segment.result);
                        }}
                      >
                        {active === segment.id ? "Selected" : "View analysis"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <Empty
            title="No complete windows"
            text="A trailing partial recording remains available in raw CSV. It does not produce spectral metrics."
          />
        )}
        {segments.length === 200 && (
          <Note>
            Showing the first 200 windows. The paginated segments API exposes
            remaining stored windows.
          </Note>
        )}
      </Card>
      <Card
        title="Signal and pattern events"
        subtitle="Engineering and statistical flags; never disorder labels"
      >
        {events.length ? (
          <div className="insight-statements">
            {events.map((e) => (
              <p key={e.id}>
                <Badge tone="amber">{title(e.category)}</Badge>
                {e.details.explanation ||
                  title(e.details.reason || "Configured threshold exceeded")}
              </p>
            ))}
          </div>
        ) : (
          <p className="muted">
            {loading
              ? "Loading events…"
              : "No stored event flags for this recording. This does not establish artifact-free EEG or clinical normality."}
          </p>
        )}
      </Card>
    </>
  );
}

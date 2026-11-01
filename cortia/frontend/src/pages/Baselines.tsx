import { useState } from "react";
import {
  History as HistoryIcon,
  Check,
  Target,
  Fingerprint,
} from "lucide-react";
import type { Recording, Baseline, Action } from "../types";
import { post, date, title, number } from "../api";
import { Card, Empty, Note, Stat } from "../ui";

export function BaselinesPage({
  sessions,
  baselines,
  busy,
  action,
  refresh,
  notify,
}: {
  sessions: Recording[];
  baselines: Baseline[];
  busy: boolean;
  action: Action;
  refresh: () => Promise<void>;
  notify: (s: string) => void;
}) {
  const [ids, setIds] = useState<string[]>([]);
  const eligible = sessions.filter(
    (s) => s.state === "completed" && s.valid_windows >= 3,
  );
  const current = baselines[0];
  return (
    <>
      <div className="stats-grid three">
        <Stat
          label="Baseline versions"
          value={String(baselines.length)}
          detail="Frozen cohorts preserve provenance"
          icon={<HistoryIcon size={17} />}
        />
        <Stat
          label="Eligible sessions"
          value={String(eligible.length)}
          detail="Completed · at least 3 usable windows"
          icon={<Check size={17} />}
        />
        <Stat
          label="Current cohort"
          value={
            current
              ? `${current.session_ids.length} sessions`
              : "Not established"
          }
          detail={
            current
              ? `Created ${date(current.created_at)}`
              : "Select 3 or more comparable recordings"
          }
          icon={<Target size={17} />}
        />
      </div>
      <Card
        title={
          current
            ? "Create a new baseline version"
            : "Establish your personal baseline"
        }
        subtitle="Same eyes, task, electrode montage, and acquisition configuration"
      >
        {eligible.length ? (
          <>
            <div className="baseline-select">
              {eligible.map((s) => (
                <label className="checkbox-row" key={s.id}>
                  <input
                    type="checkbox"
                    checked={ids.includes(s.id)}
                    onChange={(e) =>
                      setIds(
                        e.target.checked
                          ? [...ids, s.id]
                          : ids.filter((id) => id !== s.id),
                      )
                    }
                  />
                  <span>
                    <strong>
                      {date(s.started_at)} · {s.context.task}
                    </strong>
                    <small>
                      Eyes {s.context.eyes} · {s.context.montage} ·{" "}
                      {s.valid_windows} usable windows
                    </small>
                  </span>
                </label>
              ))}
            </div>
            <div className="card-actions">
              <span className="muted">{ids.length} selected · minimum 3</span>
              <button
                className="primary"
                disabled={busy || ids.length < 3}
                onClick={() =>
                  void action(async () => {
                    await post("/baselines", { session_ids: ids });
                    setIds([]);
                    await refresh();
                    notify("Baseline stored from selected recordings.");
                  })
                }
              >
                <Fingerprint size={16} />
                Calculate baseline
              </button>
            </div>
          </>
        ) : (
          <Empty
            title="A baseline needs your recordings"
            text="Collect at least three completed sessions, each with three usable eight-second windows. Keep recording conditions consistent."
          />
        )}
        <Note>
          Each session contributes one mean per feature. Three sessions is an
          engineering minimum, not validated clinical sufficiency.
        </Note>
      </Card>
      {baselines.map((b) => (
        <Card
          key={b.id}
          title={`Baseline · ${date(b.created_at)}`}
          subtitle={`${b.session_ids.length} sessions · ${b.context.task} · eyes ${b.context.eyes} · ${b.context.montage}`}
        >
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Feature</th>
                  <th>Mean</th>
                  <th>Median</th>
                  <th>Sample SD</th>
                  <th>Sessions</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(b.statistics).map(([key, s]) => (
                  <tr key={key}>
                    <td>{title(key)}</td>
                    <td>{number(s.mean, 4)}</td>
                    <td>{number(s.median, 4)}</td>
                    <td>{number(s.std, 4)}</td>
                    <td>{s.n}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      ))}
    </>
  );
}

import { DeviceSetup, RecordingControls } from "./pages/Acquisition";
import {
  SessionRows,
  BaselineComparison,
  SessionEvidence,
} from "./pages/SessionViews";
import { BaselinesPage } from "./pages/Baselines";
import { MRIPage } from "./pages/MRI";
import { HistoryPage } from "./pages/History";
import { InsightsPage } from "./pages/Insights";
import { Methods } from "./pages/Methods";
import { useCallback, useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import {
  Activity,
  ArrowRight,
  BarChart3,
  BookOpen,
  Brain,
  Check,
  ChevronRight,
  Circle,
  CircleHelp,
  Clock3,
  Fingerprint,
  FlaskConical,
  History as HistoryIcon,
  LayoutDashboard,
  Loader2,
  LogOut,
  Menu,
  Plus,
  Radio,
  ScanLine,
  ShieldCheck,
  Sparkles,
  Waves,
  X,
} from "lucide-react";
import type { User, Recording, Baseline, Live, Point, MRI } from "./types";
import { api, post, date, number, title } from "./api";
import { BandChart, Spectrum, Waveform, colors } from "./charts";
import {
  Badge,
  Brand,
  Card,
  Empty,
  LinkButton,
  Note,
  SignalEmpty,
  Stat,
} from "./ui";

type Page =
  | "Overview"
  | "Live EEG"
  | "Brainwaves"
  | "Baselines"
  | "MRI Analysis"
  | "History & reports"
  | "AI Insights"
  | "Methods";
const nav = [
  { name: "Overview", icon: LayoutDashboard },
  { name: "Live EEG", icon: Activity },
  { name: "Brainwaves", icon: BarChart3 },
  { name: "Baselines", icon: Fingerprint },
  { name: "MRI Analysis", icon: ScanLine },
  { name: "History & reports", icon: HistoryIcon },
  { name: "AI Insights", icon: Sparkles },
  { name: "Methods", icon: BookOpen },
] as const;
const descriptions: Record<Page, string> = {
  Overview: "A clearer view of your brain activity.",
  "Live EEG": "Acquire, inspect, and record your actual signal.",
  Brainwaves: "From signal to spectrum. Every calculation, traceable.",
  Baselines: "Your patterns. Your point of reference.",
  "MRI Analysis": "A separate perspective, through image classification.",
  "History & reports": "Your recordings, in context and over time.",
  "AI Insights": "Understand what your measurements can tell you.",
  Methods: "Transparent calculations. Clear boundaries.",
};

export default function App() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    api<User>("/auth/me")
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setLoading(false));
  }, []);
  if (loading)
    return (
      <div className="app-loading">
        <Brand />
        <Loader2 className="spin" />
        <p>Opening your workspace…</p>
      </div>
    );
  return user ? (
    <Workspace user={user} onLogout={() => setUser(null)} />
  ) : (
    <Auth onLogin={setUser} />
  );
}
function Auth({ onLogin }: { onLogin: (u: User) => void }) {
  const [register, setRegister] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const data = new FormData(event.currentTarget);
    try {
      onLogin(
        await post<User>(
          `/auth/${register ? "register" : "login"}`,
          Object.fromEntries(data),
        ),
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <main className="auth-layout">
      <section className="auth-story">
        <Brand />
        <div className="auth-story-content">
          <span className="eyebrow light">PERSONAL BRAIN MONITORING</span>
          <h1>
            Understand your
            <br />
            own signal.
          </h1>
          <p>
            Real recordings. Individual baselines.
            <br />A thoughtful approach to brain activity.
          </p>
          <div className="brain-art" aria-hidden="true">
            <Brain size={240} strokeWidth={0.55} />
            <span className="orbit one" />
            <span className="orbit two" />
            <span className="art-label">CORTIA / RESEARCH WORKSPACE</span>
          </div>
        </div>
        <div className="auth-foot">
          <ShieldCheck size={17} /> Local storage. Private by design.
        </div>
      </section>
      <section className="auth-form">
        <span className="eyebrow">YOUR RESEARCH WORKSPACE</span>
        <h2>
          {register ? "Start your personal record." : "Welcome to CORTIA."}
        </h2>
        <p>
          {register
            ? "Create an account on this computer."
            : "Sign in to your local monitoring workspace."}
        </p>
        <form onSubmit={submit}>
          <label>
            Username
            <input
              name="username"
              required
              minLength={3}
              maxLength={64}
              pattern="[a-zA-Z0-9_.-]+"
              autoComplete="username"
              placeholder="Your username"
            />
          </label>
          <label>
            Password
            <input
              name="password"
              type="password"
              required
              minLength={12}
              maxLength={128}
              autoComplete={register ? "new-password" : "current-password"}
              placeholder="At least 12 characters"
            />
          </label>
          {error && (
            <div className="error" role="alert">
              {error}
            </div>
          )}
          <button className="primary wide" disabled={busy}>
            {busy ? <Loader2 className="spin" size={17} /> : null}
            {register ? "Create account" : "Sign in"}
            <ArrowRight size={17} />
          </button>
        </form>
        <p className="auth-switch">
          {register ? "Already have an account?" : "New to CORTIA?"}{" "}
          <button
            onClick={() => {
              setRegister(!register);
              setError("");
            }}
          >
            {register ? "Sign in" : "Create account"}
          </button>
        </p>
        <div className="auth-disclaimer">
          <FlaskConical size={18} />
          <span>
            Research and personal monitoring only.
            <br />
            Not a clinically validated diagnostic device.
          </span>
        </div>
      </section>
    </main>
  );
}
function Workspace({ user, onLogout }: { user: User; onLogout: () => void }) {
  const [page, setPage] = useState<Page>("Overview");
  const [menu, setMenu] = useState(false);
  const [sessions, setSessions] = useState<Recording[]>([]);
  const [baselines, setBaselines] = useState<Baseline[]>([]);
  const [mris, setMris] = useState<MRI[]>([]);
  const [selected, setSelected] = useState<Recording | null>(null);
  const [live, setLive] = useState<Live>({
    state: "disconnected",
    samples: [],
    recording_id: null,
    latest: null,
  });
  const [points, setPoints] = useState<Point[]>([]);
  const [wsOnline, setWsOnline] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState("");
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const notify = (text: string) => {
    setToast(text);
    if (toastTimer.current) clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(""), 4500);
  };
  const refresh = useCallback(async () => {
    try {
      const [s, b, m] = await Promise.all([
        api<Recording[]>("/sessions"),
        api<Baseline[]>("/baselines"),
        api<MRI[]>("/mri/history"),
      ]);
      setSessions(s);
      setBaselines(b);
      setMris(m);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => {
    void refresh();
  }, [refresh]);
  useEffect(() => {
    if (!live.recording_id) return;
    const id = setInterval(() => void refresh(), 5000);
    return () => clearInterval(id);
  }, [live.recording_id, refresh]);
  useEffect(() => {
    let socket: WebSocket | null = null;
    let timer: ReturnType<typeof setTimeout>;
    let disposed = false;
    let streamId: number | null | undefined = undefined;
    const connect = () => {
      if (disposed) return;
      socket = new WebSocket(
        `${location.protocol === "https:" ? "wss:" : "ws:"}//${location.host}/api/live`,
      );
      socket.onopen = () => setWsOnline(true);
      socket.onmessage = (e) => {
        const value: Live = JSON.parse(e.data);
        setLive(value);
        if (value.state === "disconnected" || value.state === "busy") {
          setPoints([]);
          streamId = value.stream_id;
        } else if (value.stream_id !== streamId) {
          streamId = value.stream_id;
          setPoints(value.samples);
        } else if (value.samples.length)
          setPoints((current) => [...current, ...value.samples].slice(-2500));
      };
      socket.onclose = () => {
        setWsOnline(false);
        setPoints([]);
        setLive({
          state: "disconnected",
          samples: [],
          recording_id: null,
          latest: null,
          error: "Live stream unavailable. Reconnecting…",
        });
        if (!disposed) timer = setTimeout(connect, 2500);
      };
    };
    connect();
    return () => {
      disposed = true;
      clearTimeout(timer);
      socket?.close();
    };
  }, []);
  async function action(fn: () => Promise<void>) {
    setBusy(true);
    setError("");
    try {
      await fn();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function choose(id: string) {
    await action(async () => {
      setSelected(await api<Recording>(`/sessions/${id}`));
      setPage("Brainwaves");
    });
  }
  const last = sessions[0];
  const analysis = selected ? selected.latest_segment : live.latest;
  const navigate = (p: Page) => {
    setPage(p);
    setMenu(false);
    setError("");
  };
  const liveAvailable = !!live.live_available && wsOnline;
  return (
    <div className="shell">
      <aside className={`sidebar ${menu ? "open" : ""}`}>
        <Brand />
        <button
          className="mobile-close icon-button"
          aria-label="Close navigation"
          onClick={() => setMenu(false)}
        >
          <X size={20} />
        </button>
        <div className="workspace-label">
          <span className="workspace-dot" />
          Personal workspace
          <ChevronRight size={14} />
        </div>
        <span className="nav-label">MONITOR & UNDERSTAND</span>
        <nav>
          {nav.slice(0, 4).map(({ name, icon: Icon }) => (
            <button
              key={name}
              className={page === name ? "active" : ""}
              onClick={() => navigate(name)}
            >
              <Icon size={18} />
              {name}
              {name === "Live EEG" && liveAvailable && (
                <span className="nav-live" />
              )}
            </button>
          ))}
          <span className="nav-label second">EXPLORE & REFLECT</span>
          {nav.slice(4).map(({ name, icon: Icon }) => (
            <button
              key={name}
              className={page === name ? "active" : ""}
              onClick={() => navigate(name)}
            >
              <Icon size={18} />
              {name}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="research-card">
            <FlaskConical size={18} />
            <strong>Built around evidence.</strong>
            <p>
              Measurements first.
              <br />
              Interpretation with care.
            </p>
            <button onClick={() => navigate("Methods")}>
              Our approach <ArrowRight size={13} />
            </button>
          </div>
          <div className="profile">
            <span className="avatar">
              {user.username.slice(0, 2).toUpperCase()}
            </span>
            <div>
              <strong>{user.username}</strong>
              <span>Personal account</span>
            </div>
            <button
              className="icon-button"
              aria-label="Sign out"
              disabled={busy}
              onClick={() =>
                void action(async () => {
                  await post("/auth/logout");
                  onLogout();
                })
              }
            >
              <LogOut size={17} />
            </button>
          </div>
        </div>
      </aside>
      {menu && <div className="scrim" onClick={() => setMenu(false)} />}
      <div className="main">
        <header className="topbar">
          <div>
            <button
              className="mobile-menu icon-button"
              aria-label="Open navigation"
              onClick={() => setMenu(true)}
            >
              <Menu size={20} />
            </button>
            <span className="breadcrumb">
              Workspace <ChevronRight size={12} /> <strong>{page}</strong>
            </span>
          </div>
          <div className="topbar-right">
            <span className="local-label">
              <ShieldCheck size={14} />
              Local workspace
            </span>
            <span className={`server-dot ${wsOnline ? "ready" : ""}`} />
            <span className="server-label">
              {wsOnline ? "Backend connected" : "Reconnecting"}
            </span>
          </div>
        </header>
        <main className="content">
          <div className="page-heading">
            <div>
              <span className="eyebrow">
                CORTIA /{" "}
                {page === "Overview"
                  ? "PERSONAL MONITORING"
                  : page.toUpperCase()}
              </span>
              <h1>
                {page === "Overview" ? "Your brain, in perspective." : page}
              </h1>
              <p>{descriptions[page]}</p>
            </div>
            {page === "Overview" && (
              <button className="primary" onClick={() => navigate("Live EEG")}>
                <Plus size={17} />
                New recording
              </button>
            )}
            {page === "Brainwaves" && (
              <select
                aria-label="Analysis source"
                value={selected?.id || ""}
                onChange={(e) => {
                  if (e.target.value) void choose(e.target.value);
                  else setSelected(null);
                }}
              >
                <option value="">Live analysis</option>
                {sessions.map((s) => (
                  <option key={s.id} value={s.id}>
                    {date(s.started_at)} · {s.context.task}
                  </option>
                ))}
              </select>
            )}
          </div>
          {error && (
            <div className="error error-banner" role="alert">
              {error}
              <button aria-label="Dismiss error" onClick={() => setError("")}>
                <X size={15} />
              </button>
            </div>
          )}
          {live.error && page === "Live EEG" && (
            <div className="note amber">
              <CircleHelp size={16} />
              {live.error}
            </div>
          )}
          {loading ? (
            <div className="loading-panel">
              <Loader2 className="spin" />
              Loading your records…
            </div>
          ) : (
            <>
              {page === "Overview" && (
                <>
                  <section className="intro-banner">
                    <div>
                      <span className="eyebrow light">KNOW YOUR NORMAL</span>
                      <h2>Every brain has its own rhythm.</h2>
                      <p>
                        Start with a recording. Build a baseline.
                        <br />
                        Discover how your signal changes over time.
                      </p>
                      <button onClick={() => navigate("Live EEG")}>
                        Start monitoring <ArrowRight size={15} />
                      </button>
                    </div>
                    <div className="intro-art" aria-hidden="true">
                      <Brain size={155} strokeWidth={0.65} />
                      <span className="art-ring" />
                      <span className="intro-coordinate">
                        01 / YOUR PERSONAL SIGNAL
                      </span>
                    </div>
                  </section>
                  <div className="stats-grid">
                    <Stat
                      label="EEG connection"
                      value={
                        liveAvailable
                          ? "Streaming"
                          : live.state === "busy"
                            ? "Device in use"
                            : "Disconnected"
                      }
                      detail={
                        liveAvailable
                          ? `${live.config?.sampling_hz} Hz · channel ${Number(live.config?.channel) + 1}`
                          : "Connect hardware to receive EEG"
                      }
                      icon={<Radio size={17} />}
                    />
                    <Stat
                      label="Signal quality"
                      value={
                        liveAvailable && live.latest
                          ? live.latest.quality.usable
                            ? "Usable"
                            : "Review signal"
                          : "Awaiting signal"
                      }
                      detail="Exploratory artifact checks"
                      icon={<Activity size={17} />}
                    />
                    <Stat
                      label="Recorded sessions"
                      value={String(sessions.length)}
                      detail={
                        last
                          ? `Latest ${date(last.started_at)}`
                          : "Your first recording starts here"
                      }
                      icon={<HistoryIcon size={17} />}
                    />
                    <Stat
                      label="Personal baseline"
                      value={
                        baselines.length ? "Established" : "Not established"
                      }
                      detail={
                        baselines.length
                          ? `${baselines[0].session_ids.length} independent sessions`
                          : "Requires 3 comparable sessions"
                      }
                      icon={<Fingerprint size={17} />}
                    />
                  </div>
                  <div className="overview-grid">
                    <Card
                      title="Live EEG signal"
                      subtitle="One channel · raw acquisition"
                      action={
                        <Badge tone={liveAvailable ? "green" : "neutral"}>
                          {liveAvailable ? "Receiving" : "Offline"}
                        </Badge>
                      }
                    >
                      {liveAvailable && points.length ? (
                        <Waveform points={points} />
                      ) : (
                        <SignalEmpty />
                      )}
                      <div className="card-footer">
                        <span>
                          <Circle size={9} />{" "}
                          {liveAvailable
                            ? "Measured ADC counts"
                            : "Hardware connection required"}
                        </span>
                        <LinkButton onClick={() => navigate("Live EEG")}>
                          Open monitor
                        </LinkButton>
                      </div>
                    </Card>
                    <Card
                      title="Your monitoring journey"
                      subtitle="A foundation built on real recordings"
                    >
                      <div className="steps">
                        {[
                          {
                            n: "01",
                            title: "Connect your device",
                            text: "Arduino UNO R4 + BioAmp EXG Pill",
                            done: liveAvailable,
                          },
                          {
                            n: "02",
                            title: "Record with context",
                            text: "Keep electrode placement and task consistent",
                            done: sessions.some((s) => s.valid_windows > 0),
                          },
                          {
                            n: "03",
                            title: "Build your baseline",
                            text: "Three valid, comparable sessions",
                            done: baselines.length > 0,
                          },
                        ].map((step) => (
                          <div className="step" key={step.n}>
                            <span className={step.done ? "done" : ""}>
                              {step.done ? <Check size={16} /> : step.n}
                            </span>
                            <div>
                              <strong>{step.title}</strong>
                              <p>{step.text}</p>
                            </div>
                          </div>
                        ))}
                      </div>
                      <Note>
                        Your baseline comes from your recordings. Never from
                        population averages or generated values.
                      </Note>
                    </Card>
                  </div>
                  <div className="two-column">
                    <Card
                      title="Recent recordings"
                      action={
                        <LinkButton
                          onClick={() => navigate("History & reports")}
                        >
                          View history
                        </LinkButton>
                      }
                    >
                      {sessions.length ? (
                        <SessionRows
                          sessions={sessions.slice(0, 3)}
                          choose={choose}
                        />
                      ) : (
                        <Empty
                          title="Your record starts here"
                          text="Completed recordings and their measured features appear here."
                        />
                      )}
                    </Card>
                    <Card
                      title="MRI image analysis"
                      subtitle="Independent from your EEG measurements"
                      action={<ScanLine size={20} className="muted" />}
                    >
                      <div className="mri-overview">
                        <span className="mri-mini">
                          <ScanLine size={34} />
                        </span>
                        <div>
                          <h3>A separate view of your scan.</h3>
                          <p>
                            Upload an MRI image for the existing four-class
                            research model. Review its output and limitations.
                          </p>
                          <LinkButton onClick={() => navigate("MRI Analysis")}>
                            Explore MRI analysis
                          </LinkButton>
                        </div>
                      </div>
                    </Card>
                  </div>
                  <Note>
                    For research and personal monitoring. CORTIA does not
                    diagnose conditions or measure intelligence, attention,
                    anxiety, or depression.
                  </Note>
                </>
              )}
              {page === "Live EEG" && (
                <>
                  <div className="live-grid">
                    <Card
                      title="Acquisition setup"
                      subtitle="Documented Chords UNO-R4 protocol"
                    >
                      <DeviceSetup live={live} busy={busy} action={action} />
                    </Card>
                    <Card
                      title="Live waveform"
                      subtitle={
                        liveAvailable
                          ? `${live.config?.sampling_hz} samples/second · ADC counts`
                          : "Measured signals appear after hardware connection"
                      }
                      action={
                        <Badge tone={liveAvailable ? "green" : "neutral"}>
                          {liveAvailable ? "Live signal" : "Unavailable"}
                        </Badge>
                      }
                    >
                      {liveAvailable && points.length ? (
                        <Waveform points={points} />
                      ) : (
                        <SignalEmpty />
                      )}
                      <div className="live-info">
                        <span>
                          <Radio size={14} />
                          {liveAvailable
                            ? "Receiving hardware samples"
                            : "No hardware data"}
                        </span>
                        <span>
                          <Clock3 size={14} />
                          {number(
                            (live.recording_samples || 0) /
                              (live.config?.sampling_hz || 500),
                            1,
                          )}{" "}
                          s recorded
                        </span>
                      </div>
                    </Card>
                  </div>
                  <div className="two-column">
                    <Card
                      title="Recording controls"
                      subtitle="Context makes recordings comparable"
                    >
                      <RecordingControls
                        live={live}
                        busy={busy}
                        action={action}
                        refresh={refresh}
                        notify={notify}
                      />
                    </Card>
                    <Card
                      title="Signal integrity"
                      subtitle="Quality checks use eight-second windows"
                    >
                      {liveAvailable && live.latest ? (
                        <>
                          <div className="quality-result">
                            <Badge
                              tone={
                                live.latest.quality.usable ? "green" : "amber"
                              }
                            >
                              {live.latest.quality.usable
                                ? "Passes configured checks"
                                : "Window excluded"}
                            </Badge>
                            <h3>
                              {live.latest.quality.usable
                                ? "Usable for exploratory analysis"
                                : "Signal needs review"}
                            </h3>
                            <p>
                              {live.latest.quality.reasons
                                .map(title)
                                .join(" · ") ||
                                "No flatline, clipping, abrupt-step or missing-sample flag in latest window."}
                            </p>
                          </div>
                          <Note>
                            Passing heuristics does not prove artifact-free EEG.
                            One channel cannot reliably separate brain, eye, and
                            muscle activity.
                          </Note>
                        </>
                      ) : (
                        <Empty
                          title="Quality assessment pending"
                          text="Connect hardware and collect an uninterrupted eight-second window."
                        />
                      )}
                    </Card>
                  </div>
                </>
              )}
              {page === "Brainwaves" && (
                <>
                  <div className="context-strip">
                    <Waves size={18} />
                    <span>
                      {selected
                        ? `Recorded session · ${date(selected.started_at)} · ${selected.context.eyes} eyes · ${selected.context.montage}`
                        : "Live analysis · latest complete eight-second window"}
                    </span>
                    <Badge>
                      {selected ? "Recorded data" : "Hardware data"}
                    </Badge>
                  </div>
                  {analysis && analysis.quality.usable ? (
                    <>
                      <div className="band-grid">
                        {Object.entries(analysis.power || {}).map(
                          ([band, value]) => (
                            <div className="band-card" key={band}>
                              <span style={{ color: colors[band] }}>
                                ● {title(band)}
                              </span>
                              <strong>
                                {number(
                                  (analysis.relative_power?.[band] || 0) * 100,
                                  1,
                                )}
                                <small>%</small>
                              </strong>
                              <p>
                                {number(value)} ADC² ·{" "}
                                {band === "delta"
                                  ? "0.5–4"
                                  : band === "theta"
                                    ? "4–8"
                                    : band === "alpha"
                                      ? "8–13"
                                      : "13–29.5"}{" "}
                                Hz
                              </p>
                            </div>
                          ),
                        )}
                      </div>
                      <div className="two-column">
                        <Card
                          title="Power spectral density"
                          subtitle="Welch estimate · ADC²/Hz"
                        >
                          <Spectrum analysis={analysis} />
                        </Card>
                        <Card
                          title="Relative band power"
                          subtitle="Share of retained 0.5–29.5 Hz power"
                        >
                          <BandChart analysis={analysis} />
                        </Card>
                      </div>
                      <div className="ratio-grid">
                        {Object.entries(analysis.ratios || {}).map(
                          ([key, value]) => (
                            <Card key={key} title={title(key) + " ratio"}>
                              <div className="ratio-value">
                                {number(value)}
                                <Badge>Exploratory</Badge>
                              </div>
                              <p className="muted">
                                {value === null
                                  ? "Denominator too small for a stable ratio."
                                  : "Calculated band power ratio. No direct cognitive or diagnostic meaning."}
                              </p>
                            </Card>
                          ),
                        )}
                      </div>
                      <Card
                        title="FFT amplitude spectrum"
                        subtitle="Hann-windowed amplitude · ADC counts"
                      >
                        <Spectrum analysis={analysis} fft />
                      </Card>
                    </>
                  ) : (
                    <Card>
                      <Empty
                        title={
                          analysis
                            ? "Window excluded from interpretation"
                            : "No brainwave analysis available"
                        }
                        text={
                          analysis
                            ? `Quality flags: ${analysis.quality.reasons.map(title).join(", ")}. Raw samples remain preserved.`
                            : "Record a usable EEG window or choose a previous session."
                        }
                        action={
                          <button
                            className="secondary"
                            onClick={() => navigate("Live EEG")}
                          >
                            Open live monitor <ArrowRight size={16} />
                          </button>
                        }
                      />
                    </Card>
                  )}
                  {selected && (
                    <SessionEvidence
                      session={selected}
                      onWindow={(result) =>
                        setSelected((current) =>
                          current
                            ? { ...current, latest_segment: result }
                            : null,
                        )
                      }
                    />
                  )}
                  {selected?.baseline && (
                    <BaselineComparison comparison={selected.baseline} />
                  )}
                  <Note>
                    Beta stops at 29.5 Hz. Gamma unavailable. Results depend on
                    montage, task, eyes, hardware bandwidth, filtering, and
                    artifacts.
                  </Note>
                </>
              )}
              {page === "Baselines" && (
                <BaselinesPage
                  sessions={sessions}
                  baselines={baselines}
                  busy={busy}
                  action={action}
                  refresh={refresh}
                  notify={notify}
                />
              )}
              {page === "MRI Analysis" && (
                <MRIPage
                  mris={mris}
                  action={action}
                  busy={busy}
                  refresh={refresh}
                  notify={notify}
                />
              )}
              {page === "History & reports" && (
                <HistoryPage sessions={sessions} choose={choose} />
              )}
              {page === "AI Insights" && (
                <InsightsPage sessions={sessions} action={action} busy={busy} />
              )}
              {page === "Methods" && <Methods />}
            </>
          )}
          <footer className="page-footer">
            <span>
              <Waves size={13} /> CORTIA · Personal brain monitoring
            </span>
            <span>Measured with care. Interpreted with context.</span>
          </footer>
        </main>
      </div>
      {toast && (
        <div className="toast" role="status">
          <Check size={16} />
          {toast}
        </div>
      )}
    </div>
  );
}

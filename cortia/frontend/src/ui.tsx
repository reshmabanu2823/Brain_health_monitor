import type { ReactNode } from "react";
import { Activity, ArrowUpRight, CircleHelp, Radio, Waves } from "lucide-react";
export function Brand() {
  return (
    <div className="brand">
      <span className="brand-icon">
        <Waves size={23} />
      </span>
      <span>
        CORTIA<span className="brand-period">.</span>
      </span>
    </div>
  );
}
export function Empty({
  title = "No recording yet",
  text = "Connect your EEG device to start collecting real signal data.",
  action,
}: {
  title?: string;
  text?: string;
  action?: ReactNode;
}) {
  return (
    <div className="empty">
      <span className="empty-icon">
        <Activity size={25} />
      </span>
      <h3>{title}</h3>
      <p>{text}</p>
      {action}
    </div>
  );
}
export function Card({
  title,
  subtitle,
  children,
  action,
  className = "",
}: {
  title?: string;
  subtitle?: string;
  children: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <section className={`card ${className}`}>
      {title && (
        <div className="card-head">
          <div>
            <h2>{title}</h2>
            {subtitle && <p>{subtitle}</p>}
          </div>
          {action}
        </div>
      )}
      {children}
    </section>
  );
}
export function Badge({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: string;
}) {
  return (
    <span className={`badge ${tone}`}>
      <i />
      {children}
    </span>
  );
}
export function Note({ children }: { children: ReactNode }) {
  return (
    <div className="note">
      <CircleHelp size={16} />
      <span>{children}</span>
    </div>
  );
}
export function Stat({
  label,
  value,
  detail,
  icon,
}: {
  label: string;
  value: string;
  detail: string;
  icon: ReactNode;
}) {
  return (
    <section className="stat">
      <div className="stat-label">
        {label}
        <span>{icon}</span>
      </div>
      <strong>{value}</strong>
      <p>{detail}</p>
    </section>
  );
}
export function SignalEmpty() {
  return (
    <div className="signal-empty">
      <div className="grid-background" />
      <span className="empty-icon">
        <Radio size={26} />
      </span>
      <h3>Waiting for your signal</h3>
      <p>Live EEG appears here when hardware is connected.</p>
      <span className="micro">NO LIVE DATA · NO SIMULATED READINGS</span>
    </div>
  );
}
export function LinkButton({
  children,
  onClick,
}: {
  children: ReactNode;
  onClick: () => void;
}) {
  return (
    <button className="text-button" onClick={onClick}>
      {children}
      <ArrowUpRight size={15} />
    </button>
  );
}

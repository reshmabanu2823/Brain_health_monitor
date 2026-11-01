import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  BarChart,
  Bar,
  Cell,
  LineChart,
  Line,
  Legend,
} from "recharts";
import type { Analysis, Point, Recording } from "./types";
export const colors: Record<string, string> = {
  delta: "#98a6de",
  theta: "#d3ac66",
  alpha: "#4d9e8e",
  beta: "#c78483",
};
const axis = { fontSize: 11, fill: "#7a8886" };
export function Waveform({ points }: { points: Point[] }) {
  const sampled = points
    .filter((_, i) => i % Math.max(1, Math.floor(points.length / 800)) === 0)
    .map((p) => ({
      time: p.sample_time,
      value: p.missing || p.discontinuity ? null : p.value,
    }));
  return (
    <div className="chart">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={sampled}>
          <CartesianGrid stroke="#e9eeeb" vertical={false} />
          <XAxis
            dataKey="time"
            tick={axis}
            tickFormatter={(n) => `${Number(n).toFixed(1)}s`}
            minTickGap={50}
          />
          <YAxis tick={axis} domain={["auto", "auto"]} width={55} />
          <Tooltip
            formatter={(v) => [numberValue(v), "ADC counts"]}
            labelFormatter={(v) => `${Number(v).toFixed(3)} seconds`}
          />
          <Line
            type="linear"
            dataKey="value"
            stroke="#368b79"
            dot={false}
            strokeWidth={1.2}
            isAnimationActive={false}
            connectNulls={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
function numberValue(v: unknown) {
  return typeof v === "number" ? v.toFixed(2) : String(v);
}
export function Spectrum({
  analysis,
  fft = false,
}: {
  analysis: Analysis;
  fft?: boolean;
}) {
  const source = fft ? analysis.fft : analysis.psd;
  if (!source) return null;
  const values = "density" in source ? source.density : source.amplitude;
  const rows = source.frequency_hz.map((f, i) => ({
    frequency: f,
    value: values[i],
  }));
  return (
    <div className="chart">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={rows}>
          <defs>
            <linearGradient
              id={fft ? "fftFill" : "psdFill"}
              x1="0"
              y1="0"
              x2="0"
              y2="1"
            >
              <stop offset="0%" stopColor="#4d9e8e" stopOpacity={0.3} />
              <stop offset="100%" stopColor="#4d9e8e" stopOpacity={0.01} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke="#e9eeeb" vertical={false} />
          <XAxis
            dataKey="frequency"
            tick={axis}
            type="number"
            domain={[0.5, 29.5]}
            unit=" Hz"
          />
          <YAxis
            tick={axis}
            width={58}
            tickFormatter={(n) => Number(n).toPrecision(2)}
          />
          <Tooltip
            formatter={(v) => [numberValue(v), fft ? "ADC counts" : "ADC²/Hz"]}
            labelFormatter={(v) => `${v} Hz`}
          />
          <Area
            type="monotone"
            dataKey="value"
            stroke="#4d9e8e"
            fill={`url(#${fft ? "fftFill" : "psdFill"})`}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
export function BandChart({ analysis }: { analysis: Analysis }) {
  const rows = Object.entries(analysis.relative_power || {}).map(
    ([name, value]) => ({ name, value: value * 100 }),
  );
  return (
    <div className="chart small-chart">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows} barSize={34}>
          <CartesianGrid stroke="#e9eeeb" vertical={false} />
          <XAxis dataKey="name" tick={axis} axisLine={false} tickLine={false} />
          <YAxis
            tick={axis}
            unit="%"
            domain={[0, 100]}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip
            formatter={(v) => [`${numberValue(v)}%`, "Relative power"]}
          />
          <Bar dataKey="value" radius={[5, 5, 0, 0]}>
            {rows.map((row) => (
              <Cell key={row.name} fill={colors[row.name]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
export function Trends({ sessions }: { sessions: Recording[] }) {
  const rows = [...sessions]
    .reverse()
    .filter((s) => s.valid_windows > 0)
    .map((s) => ({
      date: new Date(s.started_at).toLocaleDateString(),
      ...Object.fromEntries(
        Object.entries(s.features)
          .filter(([k]) => k.startsWith("relative_"))
          .map(([k, v]) => [k.replace("relative_", ""), v * 100]),
      ),
    }));
  return (
    <div className="chart">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={rows}>
          <CartesianGrid stroke="#e9eeeb" />
          <XAxis dataKey="date" tick={axis} />
          <YAxis unit="%" tick={axis} />
          <Tooltip />
          <Legend />
          {Object.entries(colors).map(([name, color]) => (
            <Line
              key={name}
              type="linear"
              dataKey={name}
              stroke={color}
              dot={{ r: 3 }}
              connectNulls={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

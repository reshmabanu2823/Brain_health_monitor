export type User = { id: string; username: string; created_at: string };
export type Features = Record<string, number>;
export type Analysis = {
  quality: { usable: boolean; reasons: string[]; missing_samples: number };
  power: Features | null;
  relative_power: Features | null;
  ratios: Record<string, number | null> | null;
  psd: { frequency_hz: number[]; density: number[] } | null;
  fft: { frequency_hz: number[]; amplitude: number[] } | null;
  peak_hz: number | null;
  units: string;
  duration_seconds: number;
};
export type Recording = {
  id: string;
  state: string;
  started_at: string;
  ended_at: string | null;
  end_reason: string | null;
  context: { eyes: string; task: string; montage: string; notes?: string };
  config: { sampling_hz: number; channel: number; [key: string]: unknown };
  sample_count: number;
  missing_samples: number;
  valid_windows: number;
  invalid_windows: number;
  features: Features;
  latest_segment?: Analysis | null;
  baseline?: Comparison;
};
export type Comparison = {
  available: boolean;
  reason?: string;
  included_in_baseline?: boolean;
  baseline_id?: string;
  deviations?: Record<
    string,
    {
      value: number;
      baseline_mean: number;
      difference: number;
      z_score: number | null;
      flagged: boolean;
      explanation: string;
    }
  >;
};
export type Baseline = {
  id: string;
  created_at: string;
  session_ids: string[];
  context: Recording["context"];
  config: Recording["config"];
  statistics: Record<
    string,
    { mean: number; median: number; std: number; n: number }
  >;
};
export type Point = {
  sequence: number;
  sample_time: number;
  received_at: number;
  counter: number;
  value: number;
  missing: number;
  discontinuity: boolean;
};
export type Live = {
  state: string;
  stream_id?: number | null;
  live_available?: boolean;
  error?: string;
  config?: Recording["config"];
  samples: Point[];
  recording_id: string | null;
  recording_samples?: number;
  latest: Analysis | null;
};
export type MRI = {
  id: string;
  created_at: string;
  filename: string;
  result: {
    kind: string;
    label: string;
    probabilities: Features;
    model_sha256: string;
    preprocessing: string;
    limitations: string[];
    explainability: {
      available: boolean;
      reason?: string;
      overlay?: string;
      method?: string;
      limitation?: string;
    };
  };
};
export type Insight = {
  id: string;
  created_at: string;
  kind: string;
  ai_generated: boolean;
  provider: string;
  statements: string[];
  evidence_digest: string;
};

export type Action = (fn: () => Promise<void>) => Promise<void>;

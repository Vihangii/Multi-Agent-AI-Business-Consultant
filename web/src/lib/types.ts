// Shapes returned by the FastAPI backend (backend/orchestrator.py PipelineResult.to_dict
// and backend/io_utils.py inspect_dataframe). Keep in sync with the Python side.

export type Frequency = "D" | "W" | "MS";

export interface InspectResult {
  columns: string[];
  row_count: number;
  detected_date_column: string | null;
  detected_revenue_column: string | null;
  /** Numeric columns other than date/revenue — candidates for a what-if driver */
  numeric_columns: string[];
  preview: Record<string, string>[];
}

export interface Analysis {
  total_records: number;
  date_range: { start: string; end: string; span_days: number };
  revenue: {
    total: number;
    mean: number;
    median: number;
    std_dev: number;
    min: number;
    max: number;
  };
  growth?: {
    overall_percent: number;
    direction: "increasing" | "decreasing" | "flat";
  };
  monthly?: {
    best_month: string;
    best_month_revenue: number;
    worst_month: string;
    worst_month_revenue: number;
    avg_monthly_revenue: number;
  };
  volatility?: {
    avg_monthly_change_percent: number;
    max_monthly_drop_percent: number;
    max_monthly_spike_percent: number;
  };
}

export interface Accuracy {
  holdout_points: number;
  holdout_start: string;
  holdout_end: string;
  mae: number;
  mape_percent: number | null;
  interval_coverage_percent: number;
  rating: "excellent" | "good" | "fair" | "poor" | "unknown";
}

export interface ForecastSummary {
  data_granularity: "daily" | "weekly" | "monthly";
  forecast_frequency: Frequency;
  forecast_periods: number;
  last_actual_date: string;
  last_actual_value: number;
  forecast_end_date: string;
  forecast_end_value: number;
  predicted_growth_percent: number | null;
  forecast_trend: "upward" | "downward" | "flat" | "undetermined";
  confidence_interval: { lower: number; upper: number };
  avg_forecasted_value: number;
  peak_forecasted_value: number;
  peak_forecasted_date: string;
  accuracy?: Accuracy;
  regressor?: string;
}

export interface WhatIfScenario {
  change_percent: number;
  driver_value: number | null;
  forecast_end_value: number;
  avg_forecasted_value: number;
  total_forecasted: number;
  delta_vs_baseline: number;
  delta_vs_baseline_percent: number | null;
  series: { ds: string; predicted: number }[];
}

export interface WhatIf {
  driver: string | null;
  /** "regressor" = learned from a driver column; "uplift" = plain % applied to the forecast */
  method: "regressor" | "uplift";
  baseline_driver_value: number | null;
  steps: number[];
  scenarios: WhatIfScenario[];
}

export interface ForecastPoint {
  ds: string;
  predicted: number;
  lower_bound: number;
  upper_bound: number;
}

export interface CleanedPoint {
  ds: string;
  y: number;
}

export interface AnomalyPoint {
  date: string;
  actual: number;
  expected: number;
  deviation: number;
  deviation_percent: number | null;
  z_score: number;
  direction: "spike" | "drop";
  severity: "high" | "medium";
  outside_interval: boolean;
}

export interface AnomalyPeriod {
  period: string;
  revenue: number;
  previous_revenue: number;
  change_percent: number;
  direction: "spike" | "drop";
  severity: "high" | "medium";
}

export interface Anomalies {
  points: AnomalyPoint[];
  periods: AnomalyPeriod[];
  summary: {
    point_count: number;
    spike_count: number;
    drop_count: number;
    largest_drop: AnomalyPoint | null;
    largest_spike: AnomalyPoint | null;
    period_count: number;
    anomalous_share_percent: number;
    error?: string;
  };
}

export interface ToolCallTrace {
  tool: string;
  arguments: Record<string, unknown>;
  result_preview: string;
  ms: number;
}

export interface QaResult {
  status: "passed" | "corrected" | "unverified" | "skipped";
  issues: { claim: string; correct_value: string; section: string }[];
  corrections: number;
  provider?: string | null;
  model?: string | null;
  note?: string | null;
}

export interface AgentInfo {
  mode: "tools" | "static";
  provider: string;
  model: string;
  tool_calls: ToolCallTrace[];
  rounds: number;
  usage: { input_tokens?: number; output_tokens?: number };
  qa: QaResult;
  original_report?: string;
}

export interface AnalyzeResult {
  success: boolean;
  error: string | null;
  elapsed_seconds: number;
  analysis: Analysis;
  cleaned_data: CleanedPoint[];
  forecast_summary: ForecastSummary;
  forecast: ForecastPoint[];
  whatif?: WhatIf | null;
  anomalies?: Anomalies;
  recommendations?: string;
  recommendations_error?: string;
  agent?: AgentInfo;
  columns: string[];
  date_column: string;
  revenue_column: string;
  regressor_column: string | null;
  raw_row_count: number;
  cleaned_row_count: number;
}

export interface HealthResult {
  status: string;
  service: string;
  openai_configured: boolean;
  openai_model: string;
  max_upload_mb: number;
  auth_required: boolean;
  /** Platform cap on multipart bodies (4.5 on Vercel). Larger files must go via file_url. */
  max_multipart_mb: number;
  file_url_allowed_hosts: string[];
  platform: "vercel" | "server";
  rate_limit_per_minute: number;
  languages: string[];
  whatif_steps: number[];
  llm_provider: "openai" | "anthropic" | "ollama" | null;
  llm_model: string | null;
  llm_configured: boolean;
  llm_provider_setting: string;
  strategist_mode: "tools" | "static";
  critic_enabled: boolean;
}

export interface AnalyzeOptions {
  periods?: number | null;
  frequency?: Frequency | null;
  skipRecommendations: boolean;
  dateColumn?: string | null;
  revenueColumn?: string | null;
  regressorColumn?: string | null;
  language?: string | null;
}

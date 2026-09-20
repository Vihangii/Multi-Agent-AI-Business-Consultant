// Shapes returned by the FastAPI backend (backend/orchestrator.py PipelineResult.to_dict
// and backend/io_utils.py inspect_dataframe). Keep in sync with the Python side.

export type Frequency = "D" | "W" | "MS";

export interface InspectResult {
  columns: string[];
  row_count: number;
  detected_date_column: string | null;
  detected_revenue_column: string | null;
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

export interface AnalyzeResult {
  success: boolean;
  error: string | null;
  elapsed_seconds: number;
  analysis: Analysis;
  cleaned_data: CleanedPoint[];
  forecast_summary: ForecastSummary;
  forecast: ForecastPoint[];
  recommendations?: string;
  recommendations_error?: string;
  columns: string[];
  date_column: string;
  revenue_column: string;
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
}

export interface AnalyzeOptions {
  periods?: number | null;
  frequency?: Frequency | null;
  skipRecommendations: boolean;
  dateColumn?: string | null;
  revenueColumn?: string | null;
}

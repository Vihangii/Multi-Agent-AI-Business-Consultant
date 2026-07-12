import logging
import io
import pandas as pd
import requests
import streamlit as st
import plotly.graph_objects as go

# Configure page settings
st.set_page_config(
    page_title="AI Business Consultant",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Set up logging
logger = logging.getLogger("frontend")

# ---------------------------------------------------------------------------
# Custom Styling (Premium Design System)
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
        /* Base styles */
        @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap');
        
        html, body, [class*="css"] {
            font-family: 'Outfit', sans-serif;
        }
        
        /* Main header gradient */
        .main-header {
            background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 50%, #60a5fa 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-weight: 800;
            font-size: 3rem;
            margin-bottom: 0.5rem;
            text-align: left;
        }
        .subtitle {
            font-size: 1.25rem;
            color: #64748b;
            margin-bottom: 2rem;
            font-weight: 300;
        }
        
        /* Card component styling */
        .metric-card {
            background: rgba(255, 255, 255, 0.08);
            border-radius: 16px;
            padding: 1.5rem;
            border: 1px solid rgba(255, 255, 255, 0.1);
            box-shadow: 0 4px 30px rgba(0, 0, 0, 0.05);
            backdrop-filter: blur(10px);
            -webkit-backdrop-filter: blur(10px);
            margin-bottom: 1rem;
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }
        .metric-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 40px rgba(59, 130, 246, 0.1);
            border-color: rgba(59, 130, 246, 0.3);
        }
        .metric-label {
            font-size: 0.875rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: #94a3b8;
            font-weight: 600;
        }
        .metric-value {
            font-size: 2rem;
            font-weight: 700;
            color: #f8fafc;
            margin-top: 0.25rem;
            margin-bottom: 0.25rem;
        }
        .metric-value-dark {
            color: #0f172a;
        }
        .metric-desc {
            font-size: 0.8rem;
            color: #64748b;
        }
        
        /* Sidebar styling override */
        .css-1d391kg {
            background-color: #0f172a;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Sample Data Generator
# ---------------------------------------------------------------------------
@st.cache_data
def generate_sample_csv() -> bytes:
    """Generate a clean synthetic daily revenue CSV file for testing."""
    import numpy as np
    
    dates = pd.date_range(start="2024-01-01", end="2026-06-30", freq="D")
    n = len(dates)
    
    # Generate realistic revenue: Trend + Seasonality + Noise
    trend = np.linspace(500, 1200, n)
    weekly_seasonality = 150 * np.sin(2 * np.pi * dates.dayofweek / 7.0)
    yearly_seasonality = 300 * np.sin(2 * np.pi * dates.dayofyear / 365.25)
    noise = np.random.normal(0, 100, n)
    
    revenue = trend + weekly_seasonality + yearly_seasonality + noise
    revenue = np.clip(revenue, 100, None)  # Ensure no negative revenue
    
    sample_df = pd.DataFrame({
        "TransactionDate": dates.strftime("%Y-%m-%d"),
        "GrossRevenue": np.round(revenue, 2),
    })
    
    output = io.StringIO()
    sample_df.to_csv(output, index=False)
    return output.getvalue().encode("utf-8")


# ---------------------------------------------------------------------------
# API Interactor
# ---------------------------------------------------------------------------
def call_analyze_api(
    backend_url: str,
    file_bytes: bytes,
    file_name: str,
    periods: int,
    frequency: str | None,
    skip_recommendations: bool,
) -> dict | None:
    """Call the FastAPI backend's /analyze endpoint."""
    endpoint = f"{backend_url.rstrip('/')}/analyze"
    files = {"file": (file_name, file_bytes, "text/csv")}
    params = {
        "periods": periods,
        "skip_recommendations": skip_recommendations,
    }
    if frequency:
        params["frequency"] = frequency
        
    try:
        response = requests.post(endpoint, files=files, params=params, timeout=120)
        if response.status_code == 200:
            return response.json()
        else:
            try:
                error_detail = response.json().get("detail", response.text)
            except Exception:
                error_detail = response.text
            st.error(f"❌ Backend Error ({response.status_code}): {error_detail}")
            return None
    except requests.exceptions.ConnectionError:
        st.error(
            f"❌ Connection failed. Could not reach the API backend at `{backend_url}`. "
            "Please ensure your FastAPI backend is running and the address is correct."
        )
        return None
    except Exception as e:
        st.error(f"❌ Unexpected connection failure: {str(e)}")
        return None


# ---------------------------------------------------------------------------
# Application Layout
# ---------------------------------------------------------------------------
def main():
    # Render Application Title
    st.markdown('<div class="main-header">Multi-Agent AI Business Consultant</div>', unsafe_allow_html=True)
    st.markdown('<div class="subtitle">Data-driven automated business analysis, forecasting, and strategic consulting</div>', unsafe_allow_html=True)

    # 1. Sidebar - Configuration & Inputs
    st.sidebar.image("https://img.icons8.com/clouds/150/combo-chart.png", width=100)
    st.sidebar.header("🛠 Configuration")
    
    backend_url = st.sidebar.text_input(
        "API Backend URL",
        value="http://localhost:8000",
        help="FastAPI backend host and port configuration.",
    )
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("📂 Upload Dataset")
    
    uploaded_file = st.sidebar.file_uploader(
        "Choose CSV/Excel File",
        type=["csv", "xlsx", "xls"],
        help="Upload sales or revenue transactions containing date and revenue columns.",
    )
    
    # Sample file download button
    sample_bytes = generate_sample_csv()
    st.sidebar.download_button(
        label="📥 Download Sample CSV",
        data=sample_bytes,
        file_name="sample_daily_sales.csv",
        mime="text/csv",
        help="Download an artificial daily sales dataset to try out the consultant instantly.",
    )
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("🔮 Forecasting Options")
    
    forecast_periods = st.sidebar.slider(
        "Forecast Horizon",
        min_value=7,
        max_value=365,
        value=180,
        step=7,
        help="Number of future intervals to forecast.",
    )
    
    freq_options = {
        "Auto-detect": None,
        "Daily ('D')": "D",
        "Weekly ('W')": "W",
        "Monthly ('MS')": "MS",
    }
    selected_freq_label = st.sidebar.selectbox(
        "Frequency Override",
        options=list(freq_options.keys()),
        help="Enforce forecasting at a particular time granularity.",
    )
    frequency_override = freq_options[selected_freq_label]
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("🤖 AI Consult Strategy")
    
    skip_recommendations = st.sidebar.checkbox(
        "Skip AI Recommendations",
        value=False,
        help="Enable this to bypass Stage 3 (OpenAI recommendations) for offline testing.",
    )
    
    # Process File button
    analyze_triggered = st.sidebar.button(
        "🚀 Run Consultant Pipeline",
        type="primary",
        disabled=(uploaded_file is None),
        use_container_width=True,
    )
    
    # Initialize session state storage
    if "result" not in st.session_state:
        st.session_state.result = None
    if "raw_df" not in st.session_state:
        st.session_state.raw_df = None
        
    # Trigger analysis on click
    if analyze_triggered and uploaded_file is not None:
        with st.spinner("⚡ Running Multi-Agent Consulting Pipeline... Please wait."):
            # Load raw data locally for local reference/plotting
            file_bytes = uploaded_file.read()
            uploaded_file.seek(0)
            
            try:
                if uploaded_file.name.endswith(".csv"):
                    st.session_state.raw_df = pd.read_csv(io.BytesIO(file_bytes))
                else:
                    st.session_state.raw_df = pd.read_excel(io.BytesIO(file_bytes))
            except Exception as e:
                st.error(f"Could not read the file locally: {e}")
                st.session_state.raw_df = None
                
            # Call API
            api_result = call_analyze_api(
                backend_url=backend_url,
                file_bytes=file_bytes,
                file_name=uploaded_file.name,
                periods=forecast_periods,
                frequency=frequency_override,
                skip_recommendations=skip_recommendations,
            )
            
            if api_result:
                st.session_state.result = api_result
                st.toast("🎉 Pipeline finished successfully!", icon="✅")
                
    # 2. Main View
    if st.session_state.result is None:
        # Welcome View
        st.info("👈 Upload your business transactional data in the sidebar and click **Run Consultant Pipeline** to begin.")
        
        # Explain the workflow
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(
                """
                ### 🔍 1. Data Agent
                - Detects date and revenue columns automatically.
                - Cleans outliers, formats dates, aggregates duplicates.
                - Calculates statistical growth and volatility benchmarks.
                """
            )
        with col2:
            st.markdown(
                """
                ### 📈 2. Forecast Agent
                - Fits a Facebook Prophet ML forecasting model.
                - Evaluates historical trend and seasonal seasonality.
                - Projects future growth along with confidence intervals.
                """
            )
        with col3:
            st.markdown(
                """
                ### 🚀 3. Recommendation Agent
                - Analyzes predictions using OpenAI GPT models.
                - Provides tactical growth strategies.
                - Prepares prioritized 90-day execution action plans.
                """
            )
    else:
        # Render Results
        res = st.session_state.result
        analysis = res.get("analysis", {})
        forecast_sum = res.get("forecast_summary", {})
        forecast_data = res.get("forecast", [])
        
        # Build Tabs
        tab_dash, tab_chart, tab_ai, tab_data = st.tabs([
            "📊 Executive Dashboard",
            "📈 Revenue Forecast Charts",
            "🚀 Strategic AI Report",
            "📋 View Cleaned Data",
        ])
        
        # --- TAB 1: EXECUTIVE DASHBOARD ---
        with tab_dash:
            st.subheader("📌 Key Performance Indicators")
            
            # Metric Columns
            mc1, mc2, mc3, mc4 = st.columns(4)
            
            # Total Revenue
            total_rev = analysis.get("revenue", {}).get("total", 0)
            mc1.markdown(
                f"""
                <div class="metric-card">
                    <div class="metric-label">Total Revenue</div>
                    <div class="metric-value">${total_rev:,.2f}</div>
                    <div class="metric-desc">Dataset cumulative revenue</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            
            # Avg Performance
            avg_val = analysis.get("monthly", {}).get("avg_monthly_revenue", 0)
            val_lbl = "Avg Monthly"
            if avg_val == 0:
                avg_val = analysis.get("revenue", {}).get("mean", 0)
                val_lbl = "Avg Daily"
            mc2.markdown(
                f"""
                <div class="metric-card">
                    <div class="metric-label">{val_lbl}</div>
                    <div class="metric-value">${avg_val:,.2f}</div>
                    <div class="metric-desc">Mean performance level</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            
            # Growth direction
            growth_pct = analysis.get("growth", {}).get("overall_percent", 0.0)
            growth_dir = analysis.get("growth", {}).get("direction", "stable").upper()
            growth_color = "#10b981" if growth_dir == "INCREASING" else "#ef4444"
            mc3.markdown(
                f"""
                <div class="metric-card">
                    <div class="metric-label">Historical Growth</div>
                    <div class="metric-value" style="color: {growth_color};">{growth_pct:+.2f}%</div>
                    <div class="metric-desc">Overall trend: {growth_dir}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            
            # Forecast Outlook
            f_growth = forecast_sum.get("predicted_growth_percent", 0.0)
            f_trend = forecast_sum.get("forecast_trend", "stable").upper()
            ft_color = "#10b981" if f_trend == "UPWARD" else "#ef4444"
            mc4.markdown(
                f"""
                <div class="metric-card">
                    <div class="metric-label">Forecast Outlook</div>
                    <div class="metric-value" style="color: {ft_color};">{f_growth:+.2f}%</div>
                    <div class="metric-desc">Trend: {f_trend} (6-Month outlook)</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            
            # Metadata & Data Agent summary
            st.markdown("### 🔍 Data Processing & Detection Details")
            c1, c2 = st.columns(2)
            with c1:
                st.write(f"**Detected Date Column:** `{res.get('date_column')}`")
                st.write(f"**Detected Revenue Column:** `{res.get('revenue_column')}`")
                st.write(f"**Total Records Processed:** `{res.get('raw_row_count')}` rows")
            with c2:
                st.write(f"**Date Range:** {analysis.get('date_range', {}).get('start')} to {analysis.get('date_range', {}).get('end')} ({analysis.get('date_range', {}).get('span_days')} days)")
                st.write(f"**Active Records (Filtered & Cleaned):** `{res.get('cleaned_row_count')}` rows")
                st.write(f"**Granularity (Detected by Forecast):** `{forecast_sum.get('data_granularity')}`")
                
            # Monthly Breakdown
            if "monthly" in analysis:
                st.markdown("### 📆 Monthly Records Breakdown")
                mon = analysis["monthly"]
                bc1, bc2 = st.columns(2)
                bc1.info(f"🏆 **Best Month:** {mon.get('best_month')} (${mon.get('best_month_revenue', 0):,.2f})")
                bc2.warning(f"📉 **Worst Month:** {mon.get('worst_month')} (${mon.get('worst_month_revenue', 0):,.2f})")
                
        # --- TAB 2: REVENUE FORECAST CHARTS ---
        with tab_chart:
            st.subheader("📈 Revenue Projections (Prophet Forecasting)")
            
            if forecast_data:
                # Load forecast df
                f_df = pd.DataFrame(forecast_data)
                f_df["ds"] = pd.to_datetime(f_df["ds"])
                
                # Fetch actual data locally if available
                raw_df_local = st.session_state.raw_df
                date_col_api = res.get("date_column")
                rev_col_api = res.get("revenue_column")
                
                # Initialize Plotly figure
                fig = go.Figure()
                
                # Plot confidence interval shaded area first
                fig.add_trace(
                    go.Scatter(
                        x=pd.concat([f_df["ds"], f_df["ds"].iloc[::-1]]),
                        y=pd.concat([f_df["upper_bound"], f_df["lower_bound"].iloc[::-1]]),
                        fill="toself",
                        fillcolor="rgba(59, 130, 246, 0.15)",
                        line=dict(color="rgba(255,255,255,0)"),
                        hoverinfo="skip",
                        showlegend=True,
                        name="95% Confidence Interval",
                    )
                )
                
                # Plot predicted model line
                fig.add_trace(
                    go.Scatter(
                        x=f_df["ds"],
                        y=f_df["predicted"],
                        line=dict(color="#3b82f6", width=3, dash="dash" if "last_actual_date" in forecast_sum else "solid"),
                        name="Forecasted Trend",
                    )
                )
                
                # Overlay actual raw records if successfully read
                if raw_df_local is not None and date_col_api in raw_df_local.columns and rev_col_api in raw_df_local.columns:
                    try:
                        raw_plot_df = raw_df_local[[date_col_api, rev_col_api]].copy()
                        raw_plot_df.columns = ["ds", "y"]
                        raw_plot_df["ds"] = pd.to_datetime(raw_plot_df["ds"], errors="coerce")
                        raw_plot_df["y"] = pd.to_numeric(
                            raw_plot_df["y"].astype(str).str.replace(r"[^\d.\-]", "", regex=True),
                            errors="coerce"
                        )
                        raw_plot_df = raw_plot_df.dropna().sort_values("ds")
                        
                        fig.add_trace(
                            go.Scatter(
                                x=raw_plot_df["ds"],
                                y=raw_plot_df["y"],
                                mode="markers",
                                marker=dict(color="rgba(16, 185, 129, 0.7)", size=5),
                                name="Actual Transactions",
                            )
                        )
                    except Exception as e:
                        logger.warning("Could not overlay actual data on plot: %s", e)
                        
                # Update layout aesthetics
                fig.update_layout(
                    title="Actual Revenue vs Model Predictions",
                    xaxis_title="Timeline",
                    yaxis_title="Revenue ($)",
                    hovermode="x unified",
                    template="plotly_dark",
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                    margin=dict(l=20, r=20, t=60, b=20),
                    height=550,
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
                # Forecast metrics summary
                st.markdown("#### 🔮 Forecast Forecast Metrics & Peak Values")
                f1, f2, f3 = st.columns(3)
                f1.metric("Peak Forecasted Value", f"${forecast_sum.get('peak_forecasted_value', 0):,.2f}")
                f2.metric("Peak Forecast Date", str(forecast_sum.get("peak_forecasted_date")))
                f3.metric("Forecast Horizon End Value", f"${forecast_sum.get('forecast_end_value', 0):,.2f}")
            else:
                st.warning("No forecast dataset returned from backend API.")
                
        # --- TAB 3: STRATEGIC AI REPORT ---
        with tab_ai:
            st.subheader("🚀 Strategic Consultation Recommendations")
            
            recommendations_md = res.get("recommendations")
            
            if recommendations_md:
                st.markdown(recommendations_md)
                
                # Add download report button
                st.download_button(
                    label="📥 Export Report as Markdown",
                    data=recommendations_md,
                    file_name="AI_Consultant_Report.md",
                    mime="text/markdown",
                    use_container_width=True,
                )
            elif skip_recommendations:
                st.warning("AI Consultation recommendations were skipped. Toggle off 'Skip AI Recommendations' in the sidebar options to generate them.")
            else:
                st.error("No consultation report returned from the Recommendation Agent.")
                
        # --- TAB 4: VIEW CLEANED DATA ---
        with tab_data:
            st.subheader("📋 Pre-processed Datatable")
            st.write("Below is the aggregated timeline after cleansing and date parsing:")
            
            if forecast_data:
                # Load forecast df for table
                f_df_table = pd.DataFrame(forecast_data)
                st.dataframe(f_df_table, use_container_width=True)
            else:
                st.warning("No data table available.")


if __name__ == "__main__":
    main()

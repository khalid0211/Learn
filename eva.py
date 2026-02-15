import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime

# --- Page Configuration ---
st.set_page_config(page_title="EVM Calculator", layout="wide", page_icon="📊")

# --- Helper Functions ---

def calculate_evm_metrics(bac, pv, ev, ac):
    """Calculate all EVM metrics."""
    metrics = {}
    
    # 1. Variances
    metrics['SV'] = ev - pv
    metrics['CV'] = ev - ac
    
    # 2. Performance Indices
    metrics['SPI'] = ev / pv if pv != 0 else 0
    metrics['CPI'] = ev / ac if ac != 0 else 0
    
    # 3. Forecasts
    # EAC (Typical) - Assumes future performance is typical of past
    metrics['EAC_Typical'] = bac / metrics['CPI'] if metrics['CPI'] != 0 else 0
    # EAC (Atypical) - Assumes future performance returns to baseline
    metrics['EAC_Atypical'] = ac + (bac - ev)
    
    metrics['ETC_Typical'] = metrics['EAC_Typical'] - ac
    metrics['ETC_Atypical'] = metrics['EAC_Atypical'] - ac
    
    # 4. Variance at Completion
    metrics['VAC'] = bac - metrics['EAC_Typical']
    
    # 5. To-Complete Performance Index
    metrics['TCPI_BAC'] = (bac - ev) / (bac - ac) if (bac - ac) != 0 else 0
    metrics['TCPI_EAC'] = (bac - ev) / (metrics['EAC_Typical'] - ac) if (metrics['EAC_Typical'] - ac) != 0 else 0

    return metrics

def generate_s_curve_plot(bac, start_date, finish_date, data_date, ev, ac):
    """Generates an interactive S-Curve using Plotly with Beta Dist (alpha=2, beta=2)."""
    
    total_duration = (finish_date - start_date).days
    if total_duration <= 0:
        return go.Figure()

    # Generate Time Axis (Days)
    x_days = np.linspace(0, total_duration, 100)
    
    # Beta Distribution Calculation (alpha=2, beta=2)
    # Formula: Cumulative % = 3t^2 - 2t^3
    t = x_days / total_duration
    y_percent = 3 * np.power(t, 2) - 2 * np.power(t, 3)
    pv_curve = bac * y_percent
    
    # Calculate Elapsed Days for Vertical Line
    elapsed_days = (data_date - start_date).days
    
    # Create Plotly Figure
    fig = go.Figure()

    # 1. Add PV S-Curve (Baseline)
    fig.add_trace(go.Scatter(
        x=x_days, 
        y=pv_curve, 
        mode='lines', 
        name='Planned Value (PV)', 
        line=dict(color='royalblue', width=3),
        hovertemplate='Day: %{x:.0f}<br>PV: $%{y:,.0f}<extra></extra>'
    ))

    # 2. Add Data Date Line
    fig.add_vline(x=elapsed_days, line_width=2, line_dash="dash", line_color="gray",
                  annotation_text=f"Data Date (Day {elapsed_days})", annotation_position="top left")

    # 3. Add EV Point
    fig.add_trace(go.Scatter(
        x=[elapsed_days], 
        y=[ev], 
        mode='markers+text', 
        name='Earned Value (EV)', 
        marker=dict(size=12, color='green', symbol='triangle-up'),
        text=["EV"], 
        textposition="top center",
        hovertemplate=f'EV: ${ev:,.0f}<extra></extra>'
    ))

    # 4. Add AC Point
    fig.add_trace(go.Scatter(
        x=[elapsed_days], 
        y=[ac], 
        mode='markers+text', 
        name='Actual Cost (AC)', 
        marker=dict(size=12, color='red', symbol='triangle-down'),
        text=["AC"], 
        textposition="bottom center",
        hovertemplate=f'AC: ${ac:,.0f}<extra></extra>'
    ))

    # 5. Add BAC Line
    fig.add_hline(y=bac, line_width=1, line_dash="dot", line_color="purple",
                  annotation_text=f"BAC: ${bac:,.0f}")

    # Update Layout
    fig.update_layout(
        title="Project S-Curve (Beta Distribution α=2, β=2)",
        xaxis_title="Days from Start",
        yaxis_title="Value ($)",
        hovermode="x unified",
        template="plotly_white",
        height=500
    )
    
    return fig

# --- Main Application ---

st.title("📊 Earned Value Management (EVM) Calculator")
st.markdown("""
This application calculates EVM metrics and generates an S-Curve based on your project data.
**S-Curve Formula**: Cumulative Beta Distribution ($\\alpha=2, \\beta=2$) → $3t^2 - 2t^3$ """)

# --- Sidebar Inputs ---
st.sidebar.header("Project Inputs")

bac = st.sidebar.number_input("BAC (Budget at Completion)", min_value=0.0, value=100000.0, step=1000.0)
start_date = st.sidebar.date_input("Plan Start Date", value=datetime(2023, 1, 1))
finish_date = st.sidebar.date_input("Plan Finish Date", value=datetime(2023, 12, 31))
data_date = st.sidebar.date_input("Data Date (Status Date)", value=datetime(2023, 6, 30))

st.sidebar.markdown("---")
st.sidebar.markdown("### Current Values")
ac = st.sidebar.number_input("AC (Actual Cost)", min_value=0.0, value=45000.0, step=1000.0)
ev = st.sidebar.number_input("EV (Earned Value)", min_value=0.0, value=40000.0, step=1000.0)
pv = st.sidebar.number_input("PV (Planned Value)", min_value=0.0, value=50000.0, step=1000.0)

# --- Validation ---
if start_date >= finish_date:
    st.error("Error: Plan Finish Date must be after Plan Start Date.")
elif data_date < start_date or data_date > finish_date:
    st.warning("Warning: Data Date is outside the planned project duration.")

else:
    # --- Calculate Metrics ---
    metrics = calculate_evm_metrics(bac, pv, ev, ac)

    # --- Layout: Top Row Metrics ---
    st.subheader("Performance Overview")
    
    col1, col2, col3, col4 = st.columns(4)
    
    # Helper for metric cards
    def format_metric(label, value, prefix="$", delta=None, is_ratio=False):
        if is_ratio:
            val_str = f"{value:.2f}"
        else:
            val_str = f"{prefix}{value:,.0f}"
        
        st.metric(label=label, value=val_str, delta=delta)

    with col1:
        format_metric("Schedule Variance (SV)", metrics['SV'], delta="Target: > $0")
        st.metric("SPI (Schedule Perf.)", f"{metrics['SPI']:.2f}", delta="Target: > 1.0")
    
    with col2:
        format_metric("Cost Variance (CV)", metrics['CV'], delta="Target: > $0")
        st.metric("CPI (Cost Perf.)", f"{metrics['CPI']:.2f}", delta="Target: > 1.0")
        
    with col3:
        format_metric("EAC (Typical)", metrics['EAC_Typical'])
        format_metric("ETC (Typical)", metrics['ETC_Typical'])
        
    with col4:
        format_metric("VAC (at EAC)", metrics['VAC'])
        st.metric("TCPI (for BAC)", f"{metrics['TCPI_BAC']:.2f}")

    # --- Layout: Charts and Tables ---
    col_chart, col_table = st.columns([2, 1])
    
    with col_chart:
        st.subheader("S-Curve Visualization")
        fig = generate_s_curve_plot(bac, start_date, finish_date, data_date, ev, ac)
        st.plotly_chart(fig, use_container_width=True)
        
        st.info(f"""
        **Chart Interpretation**: 
        - The Blue Line represents the Planned Value (Baseline) using Beta distribution.
        - **EV Marker**: Value earned vs Work Done.
        - **AC Marker**: Money spent.
        - In this example, the project is **{'Over Budget' if ac > ev else 'Under Budget'}** 
          and **{'Behind Schedule' if ev < pv else 'Ahead of Schedule'}**.
        """)

    with col_table:
        st.subheader("Detailed Forecast")
        
        # Create a clean dataframe for the forecast details
        forecast_data = {
            "Scenario": ["Typical (Trends Continue)", "Atypical (Return to Plan)"],
            "EAC": [metrics['EAC_Typical'], metrics['EAC_Atypical']],
            "ETC": [metrics['ETC_Typical'], metrics['ETC_Atypical']],
            "TCPI": [metrics['TCPI_EAC'], metrics['TCPI_BAC']] # Note: TCPI for EAC is usually used with typical EAC
        }
        
        df_forecast = pd.DataFrame(forecast_data)
        
        # Format currency columns
        def format_currency(x):
            return f"${x:,.0f}"
        
        st.dataframe(
            df_forecast.style.format({'EAC': format_currency, 'ETC': format_currency}),
            hide_index=True,
            use_container_width=True
        )
        
        st.markdown("### Status Summary")
        if metrics['SPI'] >= 1 and metrics['CPI'] >= 1:
            st.success("✅ Project is Ahead of Schedule and Under Budget.")
        elif metrics['SPI'] < 1 and metrics['CPI'] >= 1:
            st.warning("⚠️ Project is Behind Schedule but Under Budget.")
        elif metrics['SPI'] >= 1 and metrics['CPI'] < 1:
            st.warning("⚠️ Project is Ahead of Schedule but Over Budget.")
        else:
            st.error("❌ Project is Behind Schedule and Over Budget.")

# --- Footer ---
st.markdown("---")
st.caption("Built with Streamlit. S-Curve logic based on Beta Distribution (α=2, β=2).")
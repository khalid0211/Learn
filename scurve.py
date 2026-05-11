import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
from scipy.special import betainc

# Set page configuration
st.set_page_config(
    page_title="Cash Flow Curve & NPV Calculator",
    page_icon="📊",
    layout="wide"
)

HOW_IT_WORKS = """
**How This Works**:
1. **Cash Flow Modeling**: Uses Beta CDF `I_t(α, β)` to generate cumulative spending curve
   - α controls early-stage weighting (↑α = more late spending)
   - β controls late-stage weighting (↑β = more early spending)
2. **PV (NPV) calculation**:
   - Divides timeline into `intervals` segments
   - Calculates incremental cash flow in each segment
   - Discounts each segment's cash flow using `(1 + r)^-t`
   - Sums all discounted cash flows (nominal total = **$1**; with **r > 0**, PV **< $1**)
3. **Key insight**:
   - Front-loaded curves (α < β) → **Higher PV** (closer to **$1**; spend sooner)
   - Back-loaded curves (α > β) → **Lower PV** (spend later)
   - S-curves (α ≈ β) → PV between the two extremes
"""

SCENARIO_GUIDE = """
### Example scenarios

| Scenario | Suggested parameters | Expected outcome |
| :-- | :-- | :-- |
| R&D Project | α=1.5, β=4.0 | High NPV (early spending avoids inflation) |
| Construction Project | α=3.0, β=3.0 | Moderate NPV (balanced timing) |
| Marketing Campaign | α=4.0, β=1.5 | Low NPV (late spending loses to inflation) |
| Emergency Response | α=1.0, β=3.0 | Very high NPV (immediate spending) |
| Long-Term Infrastructure | α=5.0, β=2.0 | Very low NPV (decades of delayed spending) |

*“High / low NPV” here means **relative** present value of **$1** nominal spend for that curve at your discount rate (same PV measure as in the sidebar; with **r > 0**, values are **≤ $1** but front-loaded profiles rank higher).*
"""

# Title and description
st.title("📊 Cash Flow Curve & NPV Calculator")
st.markdown(
    """
<div style="background-color:#0a2540;color:#ffffff;padding:12px 18px;margin:0 0 1rem 0;
border-radius:4px;font-size:1rem;line-height:1.5;">
<strong style="color:#ffffff;">Author</strong>
<span style="color:#ffffff;"> — Dr. Khalid Ahmad Khan · </span>
<a href="https://www.linkedin.com/in/khalidahmadkhan/" target="_blank" rel="noopener noreferrer"
style="color:#ffffff;text-decoration:underline;">LinkedIn profile</a>
</div>
""",
    unsafe_allow_html=True,
)
st.markdown("""
This tool models cash flow patterns using the **Beta Cumulative Distribution Function (CDF)** and calculates Net Present Value (NPV) 
considering inflation. All cash flows are normalized to a total budget of $1.
""")

# Sidebar for user inputs
st.sidebar.header("🔧 Parameters")
alpha = st.sidebar.number_input(
    "Alpha (α) - Shape parameter",
    min_value=0.01,
    value=2.0,
    step=0.1,
    help="Controls early-stage weighting (α < β = front-loaded)"
)
beta = st.sidebar.number_input(
    "Beta (β) - Shape parameter",
    min_value=0.01,
    value=2.0,
    step=0.1,
    help="Controls late-stage weighting (α > β = back-loaded)"
)
n_years = st.sidebar.number_input(
    "Project Duration (n) - Years",
    min_value=1,
    value=3,
    step=1,
    help="Total project duration in years"
)
inflation_pct = st.sidebar.number_input(
    "Annual inflation / discount rate (%)",
    min_value=0.0,
    max_value=50.0,
    value=10.0,
    step=0.1,
    format="%.1f",
    help="Enter as percent per year (e.g., 10.0 = 10%). Used as the discount rate in PV.",
)
inflation_rate = inflation_pct / 100.0

# Advanced settings (collapsible)
with st.sidebar.expander("⚙️ Advanced Settings"):
    intervals = st.number_input(
        "Calculation Intervals",
        min_value=100,
        max_value=5000,
        value=1000,
        step=100,
        help="Number of time intervals for numerical integration (higher = more accurate)"
    )
    show_grid = st.checkbox("Show Grid on Plot", value=True)
    show_linear = st.checkbox("Show Linear Reference Line", value=True)

# Main calculation function
def calculate_cashflow_and_npv(alpha, beta, n_years, inflation_rate, intervals=1000):
    n_years = int(n_years)
    intervals = int(intervals)
    # Generate normalized time points [0, 1]
    t_norm = np.linspace(0, 1, intervals + 1)
    
    # Calculate cumulative cash flow using Beta CDF
    C = betainc(alpha, beta, t_norm)  # I_t(α, β)
    
    # Convert to real time (years)
    t_years = t_norm * n_years
    
    # Calculate incremental cash flow (fraction of budget per interval)
    delta_C = np.diff(C)  # Length = intervals
    
    # Calculate discount factors (cash flow assumed at end of interval)
    discount_factors = 1 / ((1 + inflation_rate) ** t_years[1:])
    
    # Calculate NPV (sum of discounted incremental cash flows)
    npv = np.sum(delta_C * discount_factors)
    
    return t_norm, C, t_years, delta_C, discount_factors, npv

# Perform calculation
try:
    t_norm, C, t_years, delta_C, discount_factors, npv = calculate_cashflow_and_npv(
        alpha, beta, n_years, inflation_rate, intervals
    )
    
    # Create two columns for layout
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Plot the cash flow curve
        fig, ax = plt.subplots(figsize=(10, 6))
        
        # Plot main curve
        ax.plot(t_norm, C, 'b-', linewidth=2.5, label=f'Cash Flow Curve (α={alpha}, β={beta})')
        
        # Add linear reference if requested
        if show_linear:
            ax.plot(t_norm, t_norm, 'k--', alpha=0.7, linewidth=1.5, label='Linear Reference (C=t)')
        
        # Formatting
        ax.set_xlabel('Normalized Time (t)', fontsize=12)
        ax.set_ylabel('Normalized Cumulative Cost (C(t))', fontsize=12)
        ax.set_title(f'Cash Flow Pattern: α={alpha}, β={beta} over {n_years} Years', fontsize=14, pad=20)
        
        if show_grid:
            ax.grid(True, alpha=0.3)
        
        ax.legend()
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        
        # Add annotations for key points
        key_points = [0.25, 0.5, 0.75]
        for t in key_points:
            idx = np.argmin(np.abs(t_norm - t))
            c_val = C[idx]
            ax.annotate(f'{c_val:.1%}', 
                        xy=(t_norm[idx], c_val),
                        xytext=(5, 5), 
                        textcoords='offset points',
                        fontsize=9,
                        bbox=dict(boxstyle='round,pad=0.3', facecolor='yellow', alpha=0.3))
        
        st.pyplot(fig, clear_figure=True)
        plt.close(fig)

        st.markdown("---")
        st.markdown(HOW_IT_WORKS)

    with col2:
        # Display NPV and key metrics
        st.subheader("💰 Financial Analysis")
        
        # PV of $1 nominal spend (same as NPV here; always ≤ $1 when discount rate ≥ 0)
        pct_vs_undisc = (npv - 1.0) * 100
        st.metric(
            label="Present value (PV of $1 nominal spend)",
            value=f"${npv:.4f}",
            delta=f"{pct_vs_undisc:.2f}% vs. undiscounted total" if inflation_rate > 0 else "0% (no discounting)",
            delta_color="off",
        )
        
        # Key interpretation
        st.info("""
        **PV interpretation** (positive discount rate **r**):
        - Total nominal spend is **$1**; discounting future increments gives **PV ≤ $1**.
        - **Higher PV** (closer to **$1**): more **front-loaded** spend (less lost to discounting).
        - **Lower PV**: more **back-loaded** spend (more lost to discounting).
        - **r = 0**: PV equals **$1** for any schedule.
        """)
        
        # Cash flow timing metrics
        st.subheader("⏱️ Timing Metrics")
        
        # Time to 50% spend
        t_50_idx = np.argmin(np.abs(C - 0.5))
        t_50_norm = t_norm[t_50_idx]
        t_50_years = t_50_norm * n_years
        
        col2a, col2b = st.columns(2)
        with col2a:
            st.metric("Time to 50% Spend", f"{t_50_years:.2f} yrs")
        with col2b:
            st.metric("As % of Timeline", f"{t_50_norm*100:.1f}%")
        
        # Early vs late spending
        early_spend = C[np.argmin(np.abs(t_norm - 0.25))]  # 25% time
        late_spend = 1 - C[np.argmin(np.abs(t_norm - 0.75))]  # Remaining after 75% time
        
        st.metric("Spend in First 25% Time", f"{early_spend:.1%}")
        st.metric("Spend in Last 25% Time", f"{late_spend:.1%}")
        
        # Curve type classification
        st.subheader("📈 Curve Classification")
        if alpha < beta * 0.8:
            curve_type = "🔴 **Strongly Front-Loaded**"
        elif alpha < beta:
            curve_type = "🟠 **Moderately Front-Loaded**"
        elif abs(alpha - beta) < 0.2:
            curve_type = "🟢 **S-Curve (Symmetric)**"
        elif alpha > beta * 1.2:
            curve_type = "🔵 **Moderately Back-Loaded**"
        else:
            curve_type = "⚫ **Strongly Back-Loaded**"
        
        st.markdown(curve_type)
        
        # Sensitivity note
        st.caption(f"""
        *Calculation based on {intervals} time intervals.
        NPV assumes cash flows occur at end of each interval.
        Discount rate = {inflation_rate*100:.1f}% APR (inflation used as discount rate).
        """)

except Exception as e:
    st.error(f"❌ Calculation Error: {str(e)}")
    st.info("""
    **Troubleshooting Tips**:
    1. Ensure α > 0 and β > 0 (values must be positive)
    2. Try reducing the number of intervals if seeing precision issues
    3. Check that inflation rate is between 0% and 50%
    """)
    st.markdown("---")
    st.markdown(HOW_IT_WORKS)

st.markdown("---")
st.markdown(SCENARIO_GUIDE)

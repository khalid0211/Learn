import streamlit as st
import duckdb
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

DB_FILE = "hospital_data.duckdb"

def init_db():
    conn = duckdb.connect(DB_FILE)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cases (
            case_id VARCHAR PRIMARY KEY,
            description VARCHAR,
            case_date DATE,
            manager VARCHAR,
            notes VARCHAR,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS case_data (
            case_id VARCHAR,
            department VARCHAR,
            fully_met INTEGER,
            fully_met_pct DOUBLE,
            partially_met INTEGER,
            partially_met_pct DOUBLE,
            not_met INTEGER,
            not_met_pct DOUBLE,
            not_applicable INTEGER,
            year INTEGER,
            PRIMARY KEY (case_id, department, year)
        )
    """)
    conn.close()

def get_cases():
    conn = duckdb.connect(DB_FILE)
    df = conn.execute("SELECT case_id, description, case_date, manager FROM cases ORDER BY case_date DESC").df()
    conn.close()
    return df

def add_case(case_id, description, case_date, manager, notes):
    conn = duckdb.connect(DB_FILE)
    conn.execute("""
        INSERT INTO cases (case_id, description, case_date, manager, notes)
        VALUES (?, ?, ?, ?, ?)
    """, [case_id, description, case_date, manager, notes])
    conn.close()

def save_case_data(case_id, df, year):
    conn = duckdb.connect(DB_FILE)
    conn.execute("DELETE FROM case_data WHERE case_id = ? AND year = ?", [case_id, year])
    
    for _, row in df.iterrows():
        conn.execute("""
            INSERT INTO case_data (case_id, department, fully_met, fully_met_pct, partially_met, partially_met_pct, not_met, not_met_pct, not_applicable, year)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            case_id,
            row.get('Department', row.get('department', '')),
            int(row.get('Fully Met', row.get('fully_met', 0))),
            float(row.get('Fully Met %', row.get('fully_met_pct', 0))),
            int(row.get('Partially Met', row.get('partially_met', 0))),
            float(row.get('Partially Met %', row.get('partially_met_pct', 0))),
            int(row.get('Not Met', row.get('not_met', 0))),
            float(row.get('Not Met %', row.get('not_met_pct', 0))),
            int(row.get('Not Applicable', row.get('not_applicable', 0))),
            year
        ])
    conn.close()

def get_case_data(case_id, year):
    conn = duckdb.connect(DB_FILE)
    df = conn.execute("""
        SELECT department, fully_met, fully_met_pct, partially_met, partially_met_pct, 
               not_met, not_met_pct, not_applicable
        FROM case_data 
        WHERE case_id = ? AND year = ?
    """, [case_id, year]).df()
    conn.close()
    return df

def get_case_years(case_id):
    conn = duckdb.connect(DB_FILE)
    years = conn.execute("SELECT DISTINCT year FROM case_data WHERE case_id = ?", [case_id]).fetchall()
    conn.close()
    return [y[0] for y in years]

def analyze_data(before_df, after_df):
    if before_df.empty or after_df.empty:
        return pd.DataFrame(columns=['Department', 'Before', 'After', 'Variance'])

    # Handle both lowercase (from DB) and capitalized (from CSV) column names
    dept_col = 'department' if 'department' in before_df.columns else 'Department'
    pct_col = 'fully_met_pct' if 'fully_met_pct' in before_df.columns else 'Fully Met %'

    after_dept_col = 'department' if 'department' in after_df.columns else 'Department'
    after_pct_col = 'fully_met_pct' if 'fully_met_pct' in after_df.columns else 'Fully Met %'

    dept_data = []
    for _, before_row in before_df.iterrows():
        dept_name = str(before_row.get(dept_col, '')).strip()
        if not dept_name or dept_name == '-' or 'Sum' in dept_name:
            continue

        after_row = after_df[after_df[after_dept_col].astype(str).str.strip() == dept_name]
        if after_row.empty:
            continue

        before_pct = float(before_row.get(pct_col, 0) or 0)
        after_pct = float(after_row.iloc[0].get(after_pct_col, 0) or 0)
        variance = after_pct - before_pct

        dept_data.append({
            'Department': dept_name,
            'Before': before_pct,
            'After': after_pct,
            'Variance': variance
        })

    if not dept_data:
        return pd.DataFrame(columns=['Department', 'Before', 'After', 'Variance'])

    return pd.DataFrame(dept_data)

def generate_summary(analysis_df):
    if analysis_df is None or analysis_df.empty or len(analysis_df) == 0:
        return "No data available for analysis."
    
    total_before = analysis_df['Before'].mean()
    total_after = analysis_df['After'].mean()
    total_change = total_after - total_before
    
    improved = analysis_df[analysis_df['Variance'] > 0]
    declined = analysis_df[analysis_df['Variance'] < 0]
    
    top_improved = improved.nlargest(3, 'Variance')
    top_declined = declined.nsmallest(3, 'Variance')
    best_depts = analysis_df[analysis_df['After'] >= 90]['Department'].tolist()
    
    summary = f"""
**Overall Performance:** The hospital's overall compliance rate has {'improved' if total_change >= 0 else 'declined'} from **{total_before:.1f}%** to **{total_after:.1f}%**, representing a **{total_change:+.1f} percentage point** change. {len(improved)} out of {len(analysis_df)} departments showed improvement, while {len(declined)} departments experienced decline.

**Key Improvements:** {', '.join([f"{row['Department']} (+{row['Variance']:.1f}%)" for _, row in top_improved.iterrows()]) if len(top_improved) > 0 else 'None'} demonstrated the most significant improvements. Departments achieving 90%+ compliance include: {', '.join(best_depts) if best_depts else 'None'}.

**Areas of Concern:** {', '.join([f"{row['Department']} ({row['Variance']:.1f}%)" for _, row in top_declined.iterrows()]) if len(top_declined) > 0 else 'No departments declined'} require attention. Recommendations: Focus resources on underperforming departments, maintain momentum in high-performing areas, and implement best practices from top-improving departments across the organization.
"""
    return summary

st.set_page_config(page_title="Hospital Performance Dashboard", layout="wide")
init_db()

# Custom CSS to match HTML template styling
st.markdown("""
<style>
    .stApp {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    }
    .main .block-container {
        padding-top: 2rem;
        max-width: 1400px;
    }
    h1, h2, h3 {
        color: white !important;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: rgba(255,255,255,0.1);
        border-radius: 10px;
        padding: 5px;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: transparent;
        color: white;
        border-radius: 8px;
        padding: 10px 20px;
    }
    .stTabs [aria-selected="true"] {
        background-color: white !important;
        color: #667eea !important;
    }
    .stSelectbox label, .stTextInput label, .stDateInput label, .stTextArea label, .stNumberInput label {
        color: white !important;
    }
    div[data-testid="stMetricValue"] {
        font-size: 1.8rem;
    }
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border: none;
        padding: 12px 30px;
        font-weight: 600;
    }
    .stButton > button[kind="primary"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 15px rgba(0,0,0,0.2);
    }
    div[data-testid="stExpander"] {
        background: white;
        border-radius: 15px;
        border: none;
    }
    .stDataFrame {
        border-radius: 10px;
    }
</style>
""", unsafe_allow_html=True)

st.title("🏥 Hospital Performance Dashboard")
st.markdown("<p style='color: white; text-align: center; margin-bottom: 20px;'>Compare and analyze hospital department performance between two periods</p>", unsafe_allow_html=True)

tab1, tab2 = st.tabs(["📊 Analysis", "➕ Add New Case"])

with tab1:
    cases = get_cases()

    if cases.empty:
        st.warning("No cases found. Please add a case first.")
    else:
        case_options = cases['case_id'].tolist()
        selected_case = st.selectbox("Select Case ID", case_options)

        if selected_case:
            case_info = cases[cases['case_id'] == selected_case].iloc[0]
            st.markdown(f"**Description:** {case_info['description']} | **Manager:** {case_info['manager']} | **Date:** {case_info['case_date']}")

            years = get_case_years(selected_case)

            if len(years) < 2:
                st.warning("Need at least 2 years of data to compare. Please upload additional data.")
                if years:
                    st.markdown("### Available Data")
                    for y in years:
                        data = get_case_data(selected_case, y)
                        st.markdown(f"**Year {y}**: {len(data)} departments")
                        st.dataframe(data, hide_index=True)
            else:
                year_options = sorted(years)
                col1, col2 = st.columns(2)
                with col1:
                    before_year = st.selectbox("Before Period", year_options, index=0, key="before_year")
                with col2:
                    after_year = st.selectbox("After Period", year_options, index=len(year_options)-1, key="after_year")

                if before_year == after_year:
                    st.error("Please select different periods for comparison.")
                else:
                    run_analysis = st.button("Analyze & Compare", type="primary")

                    if run_analysis:
                        st.session_state['run_analysis'] = True
                        st.session_state['show_summary'] = False

                    if st.session_state.get('run_analysis', False):
                        before_df = get_case_data(selected_case, before_year)
                        after_df = get_case_data(selected_case, after_year)
                        analysis = analyze_data(before_df, after_df)

                        if analysis.empty:
                            st.warning("No matching departments found between the two periods.")
                        else:
                            total_before = analysis['Before'].mean()
                            total_after = analysis['After'].mean()
                            total_change = total_after - total_before
                            improved_count = len(analysis[analysis['Variance'] > 0])
                            declined_count = len(analysis[analysis['Variance'] < 0])
                            unchanged_count = len(analysis[analysis['Variance'] == 0])

                            st.divider()

                            # Summary Cards
                            col1, col2, col3, col4 = st.columns(4)
                            with col1:
                                st.markdown("""
                                <div style="background: white; border-radius: 15px; padding: 20px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); text-align: center;">
                                    <p style="color: #666; font-size: 12px; text-transform: uppercase; margin-bottom: 5px;">Overall Compliance - Before</p>
                                    <p style="font-size: 2rem; font-weight: bold; color: #667eea; margin: 0;">{:.1f}%</p>
                                </div>
                                """.format(total_before), unsafe_allow_html=True)
                            with col2:
                                st.markdown("""
                                <div style="background: white; border-radius: 15px; padding: 20px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); text-align: center;">
                                    <p style="color: #666; font-size: 12px; text-transform: uppercase; margin-bottom: 5px;">Overall Compliance - After</p>
                                    <p style="font-size: 2rem; font-weight: bold; color: #10b981; margin: 0;">{:.1f}%</p>
                                </div>
                                """.format(total_after), unsafe_allow_html=True)
                            with col3:
                                change_color = "#10b981" if total_change >= 0 else "#ef4444"
                                change_icon = "📈" if total_change >= 0 else "📉"
                                st.markdown("""
                                <div style="background: white; border-radius: 15px; padding: 20px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); text-align: center;">
                                    <p style="color: #666; font-size: 12px; text-transform: uppercase; margin-bottom: 5px;">Change in Compliance</p>
                                    <p style="font-size: 2rem; font-weight: bold; color: {}; margin: 0;">{:+.1f}%</p>
                                    <p style="font-size: 12px; color: {};">{} {}</p>
                                </div>
                                """.format(change_color, total_change, change_color, change_icon, "Improvement" if total_change >= 0 else "Decline"), unsafe_allow_html=True)
                            with col4:
                                st.markdown("""
                                <div style="background: white; border-radius: 15px; padding: 20px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); text-align: center;">
                                    <p style="color: #666; font-size: 12px; text-transform: uppercase; margin-bottom: 5px;">Departments Improved</p>
                                    <p style="font-size: 2rem; font-weight: bold; color: #10b981; margin: 0;">{}</p>
                                </div>
                                """.format(improved_count), unsafe_allow_html=True)

                            st.markdown("<br>", unsafe_allow_html=True)

                            # Charts Container
                            chart_col1, chart_col2 = st.columns(2)

                            with chart_col1:
                                st.markdown("### Compliance Comparison by Department")
                                fig_bar = go.Figure()
                                fig_bar.add_trace(go.Bar(
                                    name=f'Before ({before_year})',
                                    x=analysis['Department'],
                                    y=analysis['Before'],
                                    marker_color='rgba(102, 126, 234, 0.7)'
                                ))
                                fig_bar.add_trace(go.Bar(
                                    name=f'After ({after_year})',
                                    x=analysis['Department'],
                                    y=analysis['After'],
                                    marker_color='rgba(16, 185, 129, 0.7)'
                                ))
                                fig_bar.update_layout(
                                    barmode='group',
                                    yaxis_title='Fully Met %',
                                    yaxis=dict(range=[0, 100]),
                                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                                    margin=dict(l=20, r=20, t=40, b=20),
                                    height=350
                                )
                                st.plotly_chart(fig_bar, use_container_width=True)

                            with chart_col2:
                                st.markdown("### Variance Distribution")
                                fig_pie = go.Figure(data=[go.Pie(
                                    labels=['Improved', 'Declined', 'No Change'],
                                    values=[improved_count, declined_count, unchanged_count],
                                    hole=0.5,
                                    marker_colors=['rgba(16, 185, 129, 0.8)', 'rgba(239, 68, 68, 0.8)', 'rgba(156, 163, 175, 0.8)']
                                )])
                                fig_pie.update_layout(
                                    margin=dict(l=20, r=20, t=40, b=20),
                                    height=350
                                )
                                st.plotly_chart(fig_pie, use_container_width=True)

                            st.markdown("<br>", unsafe_allow_html=True)

                            # Variance Table
                            st.markdown("### Key Variances by Department")
                            analysis_sorted = analysis.sort_values('Variance', ascending=False)

                            def get_status(variance):
                                if variance > 0:
                                    return "📈 Improved"
                                elif variance < 0:
                                    return "📉 Declined"
                                return "➖ No Change"

                            display_df = analysis_sorted.copy()
                            display_df['Status'] = display_df['Variance'].apply(get_status)
                            display_df.columns = ['Department', f'Before ({before_year}) %', f'After ({after_year}) %', 'Change %', 'Status']

                            def highlight_row(row):
                                change = row['Change %']
                                if change > 0:
                                    return ['background-color: rgba(16, 185, 129, 0.1); color: #10b981'] * len(row)
                                elif change < 0:
                                    return ['background-color: rgba(239, 68, 68, 0.1); color: #ef4444'] * len(row)
                                return [''] * len(row)

                            st.dataframe(
                                display_df.style.apply(highlight_row, axis=1),
                                hide_index=True,
                                use_container_width=True
                            )

                            st.markdown("<br>", unsafe_allow_html=True)

                            # Department Cards
                            st.markdown("### Department Details")
                            num_cols = 3
                            rows = [analysis_sorted.iloc[i:i+num_cols] for i in range(0, len(analysis_sorted), num_cols)]

                            for row_data in rows:
                                cols = st.columns(num_cols)
                                for idx, (_, dept) in enumerate(row_data.iterrows()):
                                    with cols[idx]:
                                        variance_color = "#10b981" if dept['Variance'] > 0 else ("#ef4444" if dept['Variance'] < 0 else "#888")
                                        variance_sign = "+" if dept['Variance'] > 0 else ""
                                        st.markdown(f"""
                                        <div style="background: white; border-radius: 15px; padding: 20px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); margin-bottom: 15px;">
                                            <h4 style="color: #333; margin-bottom: 15px; padding-bottom: 10px; border-bottom: 2px solid #667eea;">{dept['Department']}</h4>
                                            <div style="display: flex; justify-content: space-between; text-align: center;">
                                                <div style="flex: 1; padding: 10px; background: #f8f9fa; border-radius: 8px; margin-right: 5px;">
                                                    <p style="font-size: 11px; color: #666; text-transform: uppercase; margin: 0;">Before</p>
                                                    <p style="font-size: 18px; font-weight: bold; color: #333; margin: 0;">{dept['Before']:.1f}%</p>
                                                </div>
                                                <div style="flex: 1; padding: 10px; background: #f8f9fa; border-radius: 8px; margin-right: 5px;">
                                                    <p style="font-size: 11px; color: #666; text-transform: uppercase; margin: 0;">After</p>
                                                    <p style="font-size: 18px; font-weight: bold; color: #333; margin: 0;">{dept['After']:.1f}%</p>
                                                </div>
                                                <div style="flex: 1; padding: 10px; background: #f8f9fa; border-radius: 8px;">
                                                    <p style="font-size: 11px; color: #666; text-transform: uppercase; margin: 0;">Change</p>
                                                    <p style="font-size: 18px; font-weight: bold; color: {variance_color}; margin: 0;">{variance_sign}{dept['Variance']:.1f}%</p>
                                                </div>
                                            </div>
                                        </div>
                                        """, unsafe_allow_html=True)

                            st.markdown("<br>", unsafe_allow_html=True)

                            # Executive Summary Button
                            if st.button("Generate Executive Summary", type="primary"):
                                st.session_state['show_summary'] = True

                            if st.session_state.get('show_summary', False):
                                st.markdown("""
                                <div style="background: white; border-radius: 15px; padding: 30px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); margin-top: 20px;">
                                    <h3 style="color: #667eea; margin-bottom: 20px;">📋 Executive Summary</h3>
                                """, unsafe_allow_html=True)
                                summary = generate_summary(analysis)
                                st.markdown(summary)
                                st.markdown("</div>", unsafe_allow_html=True)

                            # Raw Data Expander
                            with st.expander("View Raw Data"):
                                col1, col2 = st.columns(2)
                                with col1:
                                    st.markdown(f"**Before ({before_year}) Data**")
                                    st.dataframe(before_df, hide_index=True)
                                with col2:
                                    st.markdown(f"**After ({after_year}) Data**")
                                    st.dataframe(after_df, hide_index=True)

with tab2:
    st.subheader("Add New Case")
    with st.form("add_case_form"):
        col1, col2 = st.columns(2)
        with col1:
            case_id = st.text_input("Case ID *")
            description = st.text_input("Description *")
        with col2:
            case_date = st.date_input("Date", datetime.today())
            manager = st.text_input("Manager *")
        
        notes = st.text_area("Notes")
        submitted = st.form_submit_button("Save Case")
        
        if submitted:
            if not case_id or not description or not manager:
                st.error("Please fill in all required fields (*)")
            else:
                try:
                    add_case(case_id, description, case_date, manager, notes)
                    st.success(f"Case {case_id} created successfully!")
                except Exception as e:
                    st.error(f"Error: Case ID may already exist.")
    
    st.divider()
    st.subheader("Upload Data for Case")
    
    case_to_upload = st.selectbox("Select Case to Upload Data", 
                                   get_cases()['case_id'].tolist() if not get_cases().empty else [],
                                   key="upload_case")
    
    if case_to_upload:
        uploaded_file = st.file_uploader("Upload CSV File", type=["csv"])
        
        if uploaded_file:
            try:
                df = pd.read_csv(uploaded_file)
                st.dataframe(df.head())
                
                year_col = None
                if 'Year' in df.columns:
                    year_col = 'Year'
                elif 'year' in df.columns:
                    year_col = 'year'
                
                data_year = None
                if year_col:
                    years = df[year_col].unique()
                    selected_year = st.selectbox("Select Year to Upload", years)
                    year_df = df[df[year_col] == selected_year]
                    data_year = selected_year
                else:
                    data_year = st.number_input("Enter Year", min_value=2000, max_value=2100, value=2024)
                    year_df = df
                
                if st.button("Save Data"):
                    save_case_data(case_to_upload, year_df, data_year)
                    st.success(f"Data saved for year {data_year}")
                    
                    
            except Exception as e:
                st.error(f"Error reading CSV: {e}")

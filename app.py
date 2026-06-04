import streamlit as st
import pandas as pd
from ScannerClassV2 import Fund, PortfolioBuilder
from Allocations import PORTFOLIO_ALLOCATIONS
import plotly.express as px

st.set_page_config(page_title="Portfolio Builder", layout="wide")

st.title("403b Portfolio Builder")
st.markdown("Selects top funds for each allocation category in each model portfolio.")
st.subheader("How it works:")
st.markdown(''' Funds are scored based on a combination of 5-year return, Sharpe Ratio and expense ratio to determine a cumlative scoring guideline for ranking funds within each allocation category. The scores are weighed most heavily on 5-year return counting for 60% of the score, followed by Sharpe at 25% and Expense Ratio at 15%.''')
# Load the Excel file (cached)
@st.cache_data
def load_funds():
    df = pd.read_excel('Aspire_403b_funds.xlsx')
    
    # Convert text numbers to actual numbers
    numeric_columns = ['expratio', 'tr1yr', 'tr3yr', 'tr5yr', 'beta', 'alpha', 'sharpratio']
    for col in numeric_columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    
    # Convert to Fund objects
    funds = []
    for _, row in df.iterrows():
        fund = Fund(
        name=row['name'],
        ticker=row['ticker'],
        category=row['objname'],
        expense_ratio=float(row['expratio']) if pd.notna(row['expratio']) else 0,
        return_1yr=float(row['tr1yr']) if pd.notna(row['tr1yr']) else 0,
        return_3yr=float(row['tr3yr']) if pd.notna(row['tr3yr']) else 0,
        return_5yr=float(row['tr5yr']) if pd.notna(row['tr5yr']) else 0,
        beta=float(row['beta']) if pd.notna(row['beta']) else 1.0,
        alpha=float(row['alpha']) if pd.notna(row['alpha']) else 0,
        sharpe_ratio=float(row['sharpratio']) if pd.notna(row['sharpratio']) else 0,
        morningstar_category=row['catname'] if pd.notna(row.get('catname')) else None,
        std3yr=float(row['std3yr']) if pd.notna(row['std3yr']) else 0,
        yield_val=float(row['secyield']) if pd.notna(row['secyield']) else 0
        )
        
        funds.append(fund)
    small_cap_funds = [f for f in funds if 'Small' in f.category]
    real_estate_funds = [f for f in funds if 'Real Estate' in f.category]
    
    
    return funds
    

try:
    funds = load_funds()
    st.success(f"✓ Loaded {len(funds)} funds")
except Exception as e:
    st.error(f"Error loading Excel file: {e}")
    st.stop()

# Sidebar control for number of top funds
st.sidebar.header("Portfolio Settings")
top_n = st.sidebar.slider("Number of funds per allocation", 3, 10, 5)

st.sidebar.markdown(f'Change weighting of scoring factors:')
if 'weight_return' not in st.session_state:
    st.session_state.weight_return = 60
if 'weight_sharpe' not in st.session_state:
    st.session_state.weight_sharpe = 25
if 'weight_expense' not in st.session_state:
    st.session_state.weight_expense = 15

# Reset button
def reset_weights():
    st.session_state.weight_return = 60
    st.session_state.weight_sharpe = 25
    st.session_state.weight_expense = 15


weight_return = st.sidebar.slider("Weight for 5-year return", 0, 100, key='weight_return', step=5)
weight_sharpe = st.sidebar.slider("Weight for Sharpe Ratio", 0, 100, key='weight_sharpe', step=5)
weight_expense = st.sidebar.slider("Weight for Expense Ratio", 0, 100, key='weight_expense', step=5)

st.sidebar.button("Reset to Defaults", on_click=reset_weights)
#     st.session_state.weight_return = 60
#     st.session_state.weight_sharpe = 25
#     st.session_state.weight_expense = 15
#     st.rerun()
total = weight_return + weight_sharpe + weight_expense
if total == 0:
    st.sidebar.error("Total weight cannot be zero. Please adjust the sliders.")
    st.stop()

weights = {
    'return': weight_return / total,
    'sharpe': weight_sharpe / total,
    'expense': weight_expense / total
}
st.sidebar.info(f"Normalized weights:\n- Return: {weights['return']:.1%}\n- Sharpe: {weights['sharpe']:.1%}\n- Expense: {weights['expense']:.1%}")

# Build portfolio
portfolio_choice = st.sidebar.selectbox(
    "Choose Portfolio",
    list(PORTFOLIO_ALLOCATIONS.keys())
)
builder = PortfolioBuilder(funds, portfolio_name=portfolio_choice)
portfolio = builder.build_portfolio(top_n=top_n, weights=weights)

# Display portfolio
st.markdown("---")
st.subheader(f"{portfolio_choice} Portfolio Allocation")



# Investment amount input
st.markdown("---")
st.subheader("Investment Breakdown")

col1, col2 = st.columns([1, 4])

with col1:
    investment_amount = st.number_input(
        "Investment Amount ($)",
        min_value=100,
        max_value=1000000000,
        value=100000,
        step=1000,
        format="%d"
    )

# Calculate dollar amounts per allocation
allocation_breakdown = []
for allocation_name, allocation_info in builder.allocations.items():
    pct = allocation_info['pct']
    dollar_amount = investment_amount * pct
    if pct > 0:  # Only include non-zero allocations
        allocation_breakdown.append({
            'Allocation': allocation_name,
            'Percentage': pct * 100,
            'Amount': dollar_amount
        })

breakdown_df = pd.DataFrame(allocation_breakdown)

# Create pie chart
with col2:
    if not breakdown_df.empty:
        fig = px.pie(
            breakdown_df,
            values='Amount',
            names='Allocation',
            title=f"{portfolio_choice} Portfolio - ${investment_amount:,.0f}",
            hole=0.4  # Makes it a donut chart
        )
        fig.update_traces(
            textposition='inside',
            textinfo='percent+label',
            hovertemplate='<b>%{label}</b><br>Amount: $%{value:,.2f}<br>Percentage: %{percent}<extra></extra>'
        )
        fig.update_layout(
        height=600,  # Adjust this number to your liking
        font=dict(size=14)  # Larger labels
        )
        st.plotly_chart(fig, use_container_width=True)

# Show the breakdown as a table too
st.markdown("**Dollar Breakdown by Allocation:**")
display_breakdown = breakdown_df.copy()
display_breakdown['Percentage'] = display_breakdown['Percentage'].apply(lambda x: f"{x:.1f}%")
display_breakdown['Amount'] = display_breakdown['Amount'].apply(lambda x: f"${x:,.2f}")
st.dataframe(display_breakdown, use_container_width=True, hide_index=True)


# Show summary
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Total Allocations", len(portfolio))
with col2:
    total_funds = sum(len(funds) for funds in portfolio.values())
    st.metric("Total Funds Selected", total_funds)
with col3:
    st.metric("Number of top funds per Allocation", top_n)

st.markdown("---")

# Display by allocation
for allocation_name in portfolio.keys():
    allocation_pct = builder.allocations[allocation_name]['pct']
    funds_list = portfolio[allocation_name]
    
    st.subheader(f"{allocation_name} ({allocation_pct * 100:.0f}%)")
    
    if funds_list:
        # Create table
        allocation_data = []
        for rank, fund in enumerate(funds_list, 1):
            allocation_data.append({
                'Rank': rank,
                'Fund Name': fund.name,
                'Ticker': fund.ticker,
                'Expense Ratio': f"{fund.expense_ratio :.2f}%",
                '5-Yr Avg Return': f"{fund.return_5yr * 100:.2f}%",
                'Sharpe Ratio': f"{fund.sharpe_ratio:.2f}",
                'Score': f"{fund.score:.3f}"
            })
        
        st.dataframe(pd.DataFrame(allocation_data), use_container_width=True, hide_index=True)
    else:
        st.warning(f"No funds found for this allocation")

st.markdown("---")

# Download full portfolio
portfolio_df = builder.portfolio_to_dataframe()
csv = portfolio_df.to_csv(index=False)
st.download_button(
    label="📥 Download Portfolio",
    data=csv,
    file_name="generated_portfolio.csv",
    mime="text/csv"
)

# Show data summary
with st.expander("Data Summary"):
    st.write(f"Total funds loaded: {len(funds)}")
    st.write(f"Funds with Sharpe Ratio data: {sum(1 for f in funds if f.sharpe_ratio > 0)}")
    
    st.subheader(f"Funds available for {portfolio_choice} Portfolio:")
    for allocation_name, allocation_info in builder.allocations.items():
        category_list = allocation_info['categories']
        
        available = [
            f for f in funds 
            if f.morningstar_cat in category_list
            and f.expense_ratio > 0.0
        ]
        
        st.write(f"  {allocation_name}: {len(available)} funds available")
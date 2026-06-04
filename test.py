import streamlit as st
import pandas as pd
from ScannerClassV1 import Fund, RankingEngine  # Import your classes

st.set_page_config(page_title="Fund Ranking Tool", layout="wide")

st.title("403(b) Fund Ranking Tool")
st.markdown("Adjust weights below to see how funds are ranked across categories.")

# Load the Excel file (cached so it doesn't reload every interaction)
@st.cache_data
def load_funds():
    df = pd.read_excel('Aspire_403b_funds.xlsx')
    # Convert to Fund objects
    funds = []
    for _, row in df.iterrows():
        fund = Fund(
            name=row['name'],
            ticker=row['ticker'],
            category=row['objname'],
            expense_ratio=row['expratio'],
            return_1yr=row['tr1yr'],
            return_3yr=row['tr'],
            return_5yr=row['tr5yr'],
            beta=row['beta'],
            alpha=row['alpha']
        )
        funds.append(fund)
    return funds

funds = load_funds()

# Sidebar sliders for weights
st.sidebar.header("Scoring Weights")
weight_expense = st.sidebar.slider("Expense Ratio Weight", 0, 100, 20) / 100
weight_return = st.sidebar.slider("3-Year Return Weight", 0, 100, 50) / 100
weight_risk = st.sidebar.slider("Risk (Beta) Weight", 0, 100, 30) / 100

# Normalize weights so they sum to 1
total = weight_expense + weight_return + weight_risk
weights = {
    'expense_ratio': weight_expense / total,
    'return_3yr': weight_return / total,
    'beta': weight_risk / total
}

# Rank and display
engine = RankingEngine(funds)
ranked_df = engine.rank_by_category(weights)

# Show by category
for category in ranked_df['Category'].unique():
    st.subheader(f"{category}")
    category_data = ranked_df[ranked_df['Category'] == category][
        ['Fund Name', 'Ticker', 'Expense Ratio', '3-Yr Return', 'Beta', 'Score', 'Tier']
    ]
    st.dataframe(category_data, use_container_width=True)

# Download results
csv = ranked_df.to_csv(index=False)
st.download_button(
    label="Download Rankings as CSV",
    data=csv,
    file_name="fund_rankings.csv",
    mime="text/csv"
)
import pandas as pd

# df = pd.read_excel('Aspire_403b_funds.xlsx')

# # Get unique catnames
# unique_catnames = df['catname'].unique()
# unique_catnames= sorted(unique_catnames)  # Sort alphabetically
# print(f"Total unique catnames: {len(unique_catnames)}")
# print("\nAll catnames:")
# for i, catname in enumerate(unique_catnames, 1):
#     print(f"{i}. {catname}")

# import pandas as pd
# from Allocations import PORTFOLIO_ALLOCATIONS

# df = pd.read_excel('Aspire_403b_funds.xlsx')

# # Check Conservative portfolio Small Cap allocation
# small_cap_categories = PORTFOLIO_ALLOCATIONS['Conservative']['allocations']['US Equity Small Cap']['categories']
# print(f"Looking for categories: {small_cap_categories}")

# # Find matching funds
# matching = df[df['catname'].isin(small_cap_categories)]
# print(f"\nFound {len(matching)} funds matching Small Cap categories")
# print("\nMatching fund catnames:")
# print(matching['catname'].unique())

# import pandas as pd
# df = pd.read_excel('Aspire_403b_funds.xlsx')
# fglgx = df[df['ticker'] == 'FGLGX']
# print(fglgx[['ticker', 'name', 'tr5yr', 'sharpratio', 'expratio', 'catname']])


# fglgx = df[df['ticker'] == 'FGLGX']
# print(f"catname: {fglgx['catname'].values}")
# print(f"estyle: {fglgx['estyle'].values}")

# import pandas as pd
# df = pd.read_excel('Aspire_403b_funds.xlsx')
# print(f"Expense ratio: min={df['expratio'].min()}, max={df['expratio'].max()}, mean={df['expratio'].mean()}")
# print(f"5-yr return: min={df['tr5yr'].min()}, max={df['tr5yr'].max()}, mean={df['tr5yr'].mean()}")

# import pandas as pd
# df = pd.read_excel('Aspire_403b_funds.xlsx')

# # Find top Sharpe ratios
# print("Top 10 Sharpe Ratios:")
# top_sharpe = df.nlargest(10, 'sharpratio')[['ticker', 'name', 'sharpratio', 'catname']]
# print(top_sharpe)

# print(f"\nSharpe ratio stats:")
# print(f"  Min: {df['sharpratio'].min()}")
# print(f"  Max: {df['sharpratio'].max()}")
# print(f"  Mean: {df['sharpratio'].mean()}")
# print(f"  Funds with sharpratio = 0 or null: {df['sharpratio'].isna().sum() + (df['sharpratio'] == 0).sum()}")

# import pandas as pd
# df = pd.read_excel('Aspire_403b_funds.xlsx')

# # Check a well-known fund to verify columns
# vfiax = df[df['ticker'] == 'VFIAX']
# print(vfiax[['ticker', 'name', 'expratio', 'std3yr', 'beta', 'secyield', 'tr1yr', 'tr3yr', 'tr5yr', 'objname', 'catname']].to_string())

import pandas as pd
df = pd.read_excel('Aspire_403b_funds.xlsx')

# Check a few well-known funds where we know expected volatility
funds = ['VFIAX', 'FCNTX', 'VSMAX']
print(df[df['ticker'].isin(funds)][['ticker', 'name', 'std3yr', 'beta']].to_string())
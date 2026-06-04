import pandas as pd
import streamlit as lt

class Fund:
    def __init__(self, ticker, name, fund_family, objname, return_1yr, return_3yr, return_5yr, beta, alpha):
        self.ticker = ticker
        self.name = name
        self.fund_type = fund_family
        self.objname = objname
        self.return_1yr = return_1yr
        self.return_3yr = return_3yr
        self.return_5yr = return_5yr
        self.beta = beta
        self.alpha = alpha
        self.score= None
        self.tier = None
    def score_logic(self):
        # logic to calculate score based on return and risk metrics
        pass

class RankingEngine:
    def __init__(self, funds_dataframe):
        self.funds = self._dataframe_to_objects(funds_dataframe)
    
    def rank_by_category(self, weights):
        """Group funds by category, score, and tier them"""
        by_category = {}
        for fund in self.funds:
            if fund.category not in by_category:
                by_category[fund.category] = []
            by_category[fund.category].append(fund)
        
        # Score and tier within each category
        for category, category_funds in by_category.items():
            for fund in category_funds:
                fund.calculate_score(weights)
            
            # Sort by score and assign tiers
            category_funds.sort(key=lambda f: f.score, reverse=True)
            tiers = self._assign_tiers(len(category_funds))
            for fund, tier in zip(category_funds, tiers):
                fund.assign_tier(tier)
        
        return self.funds
    

        

df=pd.read_excel('Aspire_403b_funds.xlsx')
# print('total rows: {}'.format(len(df)))
# print('total columns: {}'.format(len(df.columns)))
# print('unique fund types: {}'.format(df['name'].nunique()))
# print('unique by ticker: {}'.format(df['ticker'].nunique()))

tickers= df[df['ticker'].notna()]
print(len(tickers))
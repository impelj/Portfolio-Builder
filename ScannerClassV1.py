import pandas as pd
import streamlit as st
from typing import List, Dict

class Fund:
    def __init__(self, name: str, ticker: str, category: str, 
                 expense_ratio: float, return_1yr: float, return_3yr: float, 
                 return_5yr: float, beta: float, alpha: float):
        self.name = name
        self.ticker = ticker
        self.category = category
        self.expense_ratio = expense_ratio
        self.return_1yr = return_1yr
        self.return_3yr = return_3yr
        self.return_5yr = return_5yr
        self.beta = beta
        self.alpha = alpha
        self.score = None
        self.tier = None
    
    def calculate_score(self, weights: Dict[str, float]) -> float:
        """
        Calculate fund score based on weights.
        Weights should be a dict like:
        {
            'expense_ratio': 0.2,
            'return_3yr': 0.4,
            'beta': 0.4
        }
        """
        # Normalize values (0-1 range)
        expense_norm = 1 - (self.expense_ratio / 0.015)  # Assumes max expense is 1.5%
        return_norm = min(self.return_3yr / 0.20, 1.0)   # Assumes max return is 20%
        risk_norm = 1 - (self.beta / 2.0)                 # Assumes max beta is 2.0
        
        # Calculate weighted score
        self.score = (
            weights.get('expense_ratio', 0) * expense_norm +
            weights.get('return_3yr', 0) * return_norm +
            weights.get('beta', 0) * risk_norm
        )
        return self.score
    
    def assign_tier(self, tier: str):
        self.tier = tier
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for display in Streamlit"""
        return {
            'Fund Name': self.name,
            'Ticker': self.ticker,
            'Category': self.category,
            'Expense Ratio': round(self.expense_ratio, 4),
            'Beta': round(self.beta, 2),
            '3-Yr Return': round(self.return_3yr, 4),
            'Score': round(self.score, 3) if self.score else None,
            'Tier': self.tier
        }


class RankingEngine:
    def __init__(self, funds_list: List[Fund]):
        self.funds = funds_list
        self.ranked_funds = None
    
    def rank_by_category(self, weights: Dict[str, float]) -> pd.DataFrame:
        """
        Rank funds by category using provided weights.
        Returns a DataFrame sorted by tier and score.
        """
        # Group by category
        by_category = {}
        for fund in self.funds:
            if fund.category not in by_category:
                by_category[fund.category] = []
            by_category[fund.category].append(fund)
        
        # Score all funds
        for fund in self.funds:
            fund.calculate_score(weights)
        
        # Assign tiers within each category
        for category, category_funds in by_category.items():
            # Sort by score descending
            sorted_funds = sorted(category_funds, key=lambda f: f.score, reverse=True)
            
            # Divide into 5 tiers (or fewer if category is small)
            num_tiers = min(5, len(sorted_funds))
            tier_size = len(sorted_funds) / num_tiers
            
            for idx, fund in enumerate(sorted_funds):
                tier_num = min(int(idx / tier_size) + 1, num_tiers)
                fund.assign_tier(f'Tier {tier_num}')
        
        # Convert to DataFrame
        self.ranked_funds = pd.DataFrame([f.to_dict() for f in self.funds])
        return self.ranked_funds.sort_values(['Category', 'Tier', 'Score'], ascending=[True, True, False])
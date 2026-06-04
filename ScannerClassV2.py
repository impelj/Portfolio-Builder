import pandas as pd
from typing import List, Dict, Optional
from Allocations import PORTFOLIO_ALLOCATIONS

class Fund:
    def __init__(self, name: str, ticker: str, category: str, 
                 expense_ratio: float, return_1yr: float, return_3yr: float, 
                 return_5yr: float, beta: float, alpha: float, 
                 sharpe_ratio: Optional[float] = None, 
                 morningstar_category: Optional[str] = None,
                 std3yr: Optional[float] = None,
                 yield_val: Optional[float] = None):
        self.name = name
        self.ticker = ticker
        self.category = category
        self.morningstar_cat = morningstar_category
        self.expense_ratio = expense_ratio
        self.return_1yr = return_1yr
        self.return_3yr = return_3yr
        self.return_5yr = return_5yr
        self.beta = beta
        self.alpha = alpha
        self.sharpe_ratio = sharpe_ratio if sharpe_ratio else 0
        self.std3yr = std3yr if std3yr else 0
        self.yield_val = yield_val if yield_val else 0
        self.score = None
        self.tier = None
    
    def calculate_score_growth_focused(self, weights=None) -> float:
        """
        Growth-prioritized scoring:
        - 60% 5-year return (primary growth metric)
        - 25% Sharpe ratio (risk-adjusted)
        - 15% inverse of expense ratio (lower costs are better)
        """
        if weights is None:
            weights = {'return': 0.60, 'sharpe': 0.25, 'expense': 0.15}
        
        # Normalize to 0-1 range
        # 5-year return: 50% is perfect score
        if self.return_5yr is None or self.return_5yr <= 0:
            return_norm = 0
        else:
            return_norm = min(self.return_5yr / 0.50, 1.0) if self.return_5yr else 0
        
        # Sharpe ratio: 5 is perfect score
        if self.sharpe_ratio is None or self.sharpe_ratio <= 0:
            sharpe_norm = 0
        else:
            sharpe_norm = min(self.sharpe_ratio / 4.05, 1.0) if self.sharpe_ratio else 0.5
        
        # Expense ratio: penalize expensive funds (assume 12% is max)
        expense_norm = max(1 - (self.expense_ratio / 11.04), 0)
        
        # Calculate weighted score
        self.score = (
            weights['return'] * return_norm +
            weights['sharpe'] * sharpe_norm +
            weights['expense'] * expense_norm
        )
        return self.score
    
    def assign_tier(self, tier: str):
        self.tier = tier
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for display"""
        return {
            'Fund Name': self.name,
            'Ticker': self.ticker,
            'Category': self.category,
            'Expense Ratio': round(self.expense_ratio, 4),
            'Beta': round(self.beta, 2),
            '5-Yr Return': round(self.return_5yr, 4),
            'Sharpe': round(self.sharpe_ratio, 2),
            'Score': round(self.score, 3) if self.score else None,
            'Tier': self.tier
        }


class PortfolioBuilder:
    """
    Builds  portfolio with top-ranked funds by allocation
    """
    def __init__(self, funds: List[Fund], portfolio_name: str = 'Conservative'):
        self.funds = funds
        self.portfolio_name = portfolio_name
        self.allocations = PORTFOLIO_ALLOCATIONS[portfolio_name]['allocations']
        self.portfolio = {}

    
    def build_portfolio(self, top_n: int = 5, weights=None) -> Dict[str, List[Fund]]:
        """
        Build portfolio by selecting top N funds per allocation bucket
        Returns dict of allocation -> [top funds]
        """
        for allocation_name, allocation_info in self.allocations.items():
            # Filter funds by category
            category_list = allocation_info['categories']
            
            # Get funds in this allocation - use morningstar_cat, not category
            allocation_funds = [
                f for f in self.funds
                if f.morningstar_cat in category_list and f.expense_ratio > 0.0 # <- CHANGE THIS LINE
            ]
            
            # Score and sort
            for fund in allocation_funds:
                fund.calculate_score_growth_focused(weights=weights)
            
            allocation_funds.sort(key=lambda f: f.score, reverse=True)
            
            # Select top N
            top_funds = allocation_funds[:top_n]
            self.portfolio[allocation_name] = top_funds
    
        return self.portfolio
    
    def portfolio_to_dataframe(self) -> pd.DataFrame:
        """Convert portfolio to DataFrame for display"""
        rows = []
        for allocation_name, funds in self.portfolio.items():
            allocation_pct = self.allocations[allocation_name]['pct']
            
            for rank, fund in enumerate(funds, 1):
                rows.append({
                    'Allocation': allocation_name,
                    'Allocation %': f"{allocation_pct * 100:.0f}%",
                    'Rank': rank,
                    'Fund Name': fund.name,
                    'Ticker': fund.ticker,
                    'Expense Ratio': f"{fund.expense_ratio :.2f}%",
                    '5-Yr Return': f"{fund.return_5yr * 100:.2f}%",
                    'Sharpe Ratio': f"{fund.sharpe_ratio:.2f}",
                    'Score': f"{fund.score:.3f}"
                })
        
        return pd.DataFrame(rows)
        
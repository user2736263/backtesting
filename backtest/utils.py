"""
Utility functions for backtesting.
"""

from typing import Dict, Any
import json


def calculate_sharpe_ratio(returns: list, risk_free_rate: float = 0.0) -> float:
    """
    Calculate Sharpe ratio.
    
    Args:
        returns: List of periodic returns (as decimals, e.g., 0.01 for 1%)
        risk_free_rate: Risk-free rate (default 0.0)
    
    Returns:
        Sharpe ratio
    """
    if not returns or len(returns) == 0:
        return 0.0
    
    import numpy as np
    
    returns_array = np.array(returns)
    mean_return = np.mean(returns_array)
    std_return = np.std(returns_array)
    
    if std_return == 0:
        return 0.0
    
    sharpe = (mean_return - risk_free_rate) / std_return
    return float(sharpe)


def calculate_max_drawdown(equity_curve: list) -> float:
    """
    Calculate maximum drawdown.
    
    Args:
        equity_curve: List of equity values over time
    
    Returns:
        Maximum drawdown as a percentage (e.g., 0.15 for 15%)
    """
    if not equity_curve or len(equity_curve) == 0:
        return 0.0
    
    import numpy as np
    
    equity = np.array(equity_curve)
    running_max = np.maximum.accumulate(equity)
    drawdown = (equity - running_max) / running_max
    max_drawdown = float(np.min(drawdown))
    
    return abs(max_drawdown)  # Return as positive percentage


def format_percentage(value: float, decimals: int = 4) -> str:
    """Format a decimal as a percentage string."""
    return f"{value * 100:.{decimals}f}%"


def save_results_to_json(results: list, filename: str):
    """Save results to JSON file."""
    with open(filename, 'w') as f:
        json.dump(results, f, indent=2, default=str)


def load_results_from_json(filename: str) -> list:
    """Load results from JSON file."""
    with open(filename, 'r') as f:
        return json.load(f)


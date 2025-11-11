"""
Technical indicators module for backtesting.
Implements Supertrend indicator with configurable ATR and multiplier.
"""

import pandas as pd
import numpy as np
from typing import Tuple, Optional


def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Calculate Average True Range (ATR).
    
    Args:
        df: DataFrame with high, low, close columns
        period: ATR period
    
    Returns:
        Series with ATR values
    """
    high = df['high']
    low = df['low']
    close = df['close']
    
    # Calculate True Range
    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    # Calculate ATR as rolling mean of TR
    atr = tr.rolling(window=period).mean()
    
    return atr


def calculate_supertrend(
    df: pd.DataFrame,
    atr_period: int = 3,
    multiplier: float = 6.0
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """
    Calculate Supertrend indicator.
    
    Args:
        df: DataFrame with high, low, close columns
        atr_period: ATR period (1-50)
        multiplier: Supertrend multiplier (0.5-20)
    
    Returns:
        Tuple of (supertrend_values, trend_direction, upper_band, lower_band)
        - supertrend_values: The Supertrend line values
        - trend_direction: 1 for uptrend, -1 for downtrend
        - upper_band: Upper band values
        - lower_band: Lower band values
    """
    high = df['high']
    low = df['low']
    close = df['close']
    
    # Calculate ATR
    atr = calculate_atr(df, atr_period)
    
    # Calculate basic bands
    hl_avg = (high + low) / 2
    upper_band = hl_avg + (multiplier * atr)
    lower_band = hl_avg - (multiplier * atr)
    
    # Initialize arrays
    supertrend = pd.Series(index=df.index, dtype=float)
    trend = pd.Series(index=df.index, dtype=int)
    final_upper_band = pd.Series(index=df.index, dtype=float)
    final_lower_band = pd.Series(index=df.index, dtype=float)
    
    # Initialize first values
    supertrend.iloc[0] = lower_band.iloc[0]
    trend.iloc[0] = 1  # Start with uptrend
    final_upper_band.iloc[0] = upper_band.iloc[0]
    final_lower_band.iloc[0] = lower_band.iloc[0]
    
    # Calculate Supertrend
    for i in range(1, len(df)):
        # Update bands
        if close.iloc[i] <= final_upper_band.iloc[i-1]:
            final_upper_band.iloc[i] = min(upper_band.iloc[i], final_upper_band.iloc[i-1])
        else:
            final_upper_band.iloc[i] = upper_band.iloc[i]
        
        if close.iloc[i] >= final_lower_band.iloc[i-1]:
            final_lower_band.iloc[i] = max(lower_band.iloc[i], final_lower_band.iloc[i-1])
        else:
            final_lower_band.iloc[i] = lower_band.iloc[i]
        
        # Determine trend
        if close.iloc[i] <= final_lower_band.iloc[i-1]:
            trend.iloc[i] = -1  # Downtrend
        elif close.iloc[i] >= final_upper_band.iloc[i-1]:
            trend.iloc[i] = 1  # Uptrend
        else:
            trend.iloc[i] = trend.iloc[i-1]  # Continue previous trend
        
        # Set Supertrend value
        if trend.iloc[i] == 1:
            supertrend.iloc[i] = final_lower_band.iloc[i]
        else:
            supertrend.iloc[i] = final_upper_band.iloc[i]
    
    return supertrend, trend, final_upper_band, final_lower_band


def generate_signals(
    df: pd.DataFrame,
    atr_period: int = 3,
    multiplier: float = 6.0
) -> pd.Series:
    """
    Generate buy/sell signals based on Supertrend crossover.
    
    Args:
        df: DataFrame with high, low, close columns
        atr_period: ATR period (1-50)
        multiplier: Supertrend multiplier (0.5-20)
    
    Returns:
        Series with signals: 1 for buy, -1 for sell, 0 for no signal
    """
    _, trend, _, _ = calculate_supertrend(df, atr_period, multiplier)
    
    # Generate signals on trend changes
    signals = pd.Series(0, index=df.index)
    
    # Buy signal: trend changes from -1 to 1 (downtrend to uptrend)
    # Sell signal: trend changes from 1 to -1 (uptrend to downtrend)
    trend_change = trend.diff()
    
    signals[trend_change > 0] = 1   # Buy: trend went from -1 to 1
    signals[trend_change < 0] = -1  # Sell: trend went from 1 to -1
    
    return signals


if __name__ == "__main__":
    # Test with sample data
    dates = pd.date_range('2024-01-01', periods=100, freq='1min')
    np.random.seed(42)
    prices = 100 + np.cumsum(np.random.randn(100) * 0.5)
    
    df = pd.DataFrame({
        'open': prices + np.random.randn(100) * 0.1,
        'high': prices + abs(np.random.randn(100) * 0.2),
        'low': prices - abs(np.random.randn(100) * 0.2),
        'close': prices,
        'volume': np.random.randint(1000, 10000, 100)
    }, index=dates)
    
    supertrend, trend, upper, lower = calculate_supertrend(df, atr_period=3, multiplier=6.0)
    signals = generate_signals(df, atr_period=3, multiplier=6.0)
    
    print("Supertrend calculation test:")
    print(f"Trend values: {trend.value_counts()}")
    print(f"Signals: {signals.value_counts()}")
    print(f"\nFirst 10 signals:\n{signals.head(10)}")


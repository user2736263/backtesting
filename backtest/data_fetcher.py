"""
Historical data collection module for backtesting.
Fetches 1 month of 1-minute OHLCV data for SOL/USDC using CCXT.
"""

import ccxt
import pandas as pd
import os
from datetime import datetime, timedelta
from typing import Optional, Tuple
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Cache directory
CACHE_DIR = "backtest_data_cache"
os.makedirs(CACHE_DIR, exist_ok=True)


def fetch_historical_data(
    symbol: str = "SOL/USDC",
    timeframe: str = "1m",
    days: int = 30,
    exchange_name: str = "binance"
) -> pd.DataFrame:
    """
    Fetch historical OHLCV data for the specified symbol.
    
    Args:
        symbol: Trading pair (e.g., "SOL/USDC")
        timeframe: Candle timeframe (e.g., "1m", "5m")
        days: Number of days of historical data to fetch
        exchange_name: Exchange to use (binance, coinbase, etc.)
    
    Returns:
        DataFrame with columns: timestamp, open, high, low, close, volume
    """
    cache_file = os.path.join(CACHE_DIR, f"{symbol.replace('/', '_')}_{timeframe}_{days}d.csv")
    
    # Check cache first
    if os.path.exists(cache_file):
        print(f"📦 Found cached data: {cache_file}")
        logger.info(f"Loading cached data from {cache_file}")
        df = pd.read_csv(cache_file, index_col=0, parse_dates=True)
        logger.info(f"Loaded {len(df)} candles from cache")
        print(f"✓ Loaded {len(df)} candles from cache")
        return df
    
    # Try multiple exchanges as fallback
    exchanges_to_try = [exchange_name, "binance", "coinbase", "kraken", "okx"]
    
    for exchange_id in exchanges_to_try:
        try:
            print(f"🌐 Attempting to fetch data from {exchange_id}...")
            logger.info(f"Attempting to fetch data from {exchange_id}...")
            exchange = getattr(ccxt, exchange_id)({
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'spot'  # Use spot for historical data
                }
            })
            
            # Calculate since timestamp (days ago)
            since = exchange.milliseconds() - (days * 24 * 60 * 60 * 1000)
            
            # Fetch all candles
            all_candles = []
            current_since = since
            
            while True:
                try:
                    candles = exchange.fetch_ohlcv(symbol, timeframe, since=current_since, limit=1000)
                    if not candles:
                        break
                    
                    all_candles.extend(candles)
                    
                    # Update since to last candle timestamp + 1
                    current_since = candles[-1][0] + 1
                    
                    # Check if we have enough data
                    if len(all_candles) >= days * 24 * 60:  # Approximate for 1m candles
                        break
                    
                    if len(all_candles) % 10000 == 0:
                        print(f"  📊 Fetched {len(all_candles)} candles so far...")
                    logger.info(f"Fetched {len(all_candles)} candles so far...")
                    
                except Exception as e:
                    logger.warning(f"Error fetching batch: {e}")
                    break
            
            if not all_candles:
                print(f"  ⚠️ No data received from {exchange_id}, trying next exchange...")
                continue
            
            # Convert to DataFrame
            df = pd.DataFrame(
                all_candles,
                columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
            )
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            
            # Remove duplicates and sort
            df = df[~df.index.duplicated(keep='first')]
            df.sort_index(inplace=True)
            
            # Validate data quality
            df = validate_data_quality(df, timeframe)
            
            # Cache the data
            df.to_csv(cache_file)
            logger.info(f"Cached data to {cache_file}")
            print(f"💾 Cached data to {cache_file}")
            
            logger.info(f"Successfully fetched {len(df)} candles from {exchange_id}")
            print(f"✓ Successfully fetched {len(df)} candles from {exchange_id}")
            return df
            
        except Exception as e:
            print(f"  ⚠️ Failed to fetch from {exchange_id}: {e}")
            logger.warning(f"Failed to fetch from {exchange_id}: {e}")
            continue
    
    print(f"❌ Failed to fetch data from all exchanges. Tried: {exchanges_to_try}")
    raise Exception(f"Failed to fetch data from all exchanges. Tried: {exchanges_to_try}")


def validate_data_quality(df: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    """
    Validate and clean the data.
    
    Args:
        df: DataFrame with OHLCV data
        timeframe: Expected timeframe (e.g., "1m")
    
    Returns:
        Cleaned DataFrame
    """
    # Calculate expected interval in minutes
    timeframe_minutes = {
        '1m': 1,
        '5m': 5,
        '15m': 15,
        '1h': 60,
        '1d': 1440
    }.get(timeframe, 1)
    
    # Remove rows with invalid data
    df = df.dropna()
    df = df[(df['high'] >= df['low']) & (df['high'] >= df['open']) & (df['high'] >= df['close'])]
    df = df[(df['low'] <= df['open']) & (df['low'] <= df['close'])]
    
    # Check for gaps > 5 minutes (for 1m data)
    if timeframe == '1m':
        df = df.sort_index()
        time_diffs = df.index.to_series().diff()
        max_gap = time_diffs.max()
        if max_gap > pd.Timedelta(minutes=5):
            logger.warning(f"Found gap of {max_gap} in data. This may affect backtest accuracy.")
    
    logger.info(f"Data validation complete. {len(df)} valid candles remaining.")
    return df


if __name__ == "__main__":
    # Test data fetching
    df = fetch_historical_data("SOL/USDC", "1m", days=30)
    print(f"\nData shape: {df.shape}")
    print(f"\nFirst few rows:\n{df.head()}")
    print(f"\nLast few rows:\n{df.tail()}")
    print(f"\nDate range: {df.index.min()} to {df.index.max()}")


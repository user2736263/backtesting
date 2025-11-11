# Backtesting System

This backtesting system simulates the exact trading logic from `app.py` on historical data and optimizes parameters to find the best settings.

## Quick Start

```bash
# Run full optimization (all 3 stages)
python -m backtest.run_optimization

# Or use the convenience script
python run_backtest.py

# Custom options
python -m backtest.run_optimization --max-combinations 5000 --skip-stage3
```

## Command Line Options

- `--symbol`: Trading pair (default: SOL/USDC)
- `--period`: Data period (default: 1m = 1 month)
- `--timeframe`: Candle timeframe (default: 1m)
- `--capital`: Starting capital (default: 10000)
- `--stages`: Which stages to run: 1, 2, 3, or all (default: all)
- `--max-combinations`: Max random combinations for Stage 1 (default: 10000)
- `--stage2-top-n`: Top N results to refine in Stage 2 (default: 100)
- `--skip-stage3`: Skip Stage 3 exhaustive search
- `--n-jobs`: Number of parallel jobs (default: all CPUs)

## Optimization Stages

1. **Stage 1 - Random Sampling**: Tests 10,000 random parameter combinations (10-20 minutes)
2. **Stage 2 - Refinement**: Fine-tunes top 100 results with smaller steps (20-40 minutes)
3. **Stage 3 - Exhaustive Search**: Exhaustive search around best parameters (10-20 minutes)

**Total time: 40-80 minutes** (with 4-8 CPU cores)

## Parameter Ranges

- **ATR Period**: 1-50 (integer)
- **Multiplier**: 0.5-20.0 (0.5 steps)
- **Stop Loss Long**: 0.01%-2% (0.01% steps)
- **Stop Loss Short**: 0.01%-2% (0.01% steps)
- **Take Profit**: 0.01%-2% (0.01% steps)
- **Cooldown**: 0-3600 seconds (60s steps)
- **Capital Allocation**: Fixed at 99%

## Output Files

Results are saved to `backtest_results/`:

- `all_results.csv`: All tested parameter combinations
- `top_50_results.json`: Top 50 results in JSON format
- `report.html`: HTML report with top 50 results
- `best_equity_curve.png`: Equity curve for best parameters
- `best_trade_distribution.png`: PnL distribution for best parameters

## Metrics Calculated

- Total PnL (absolute and percentage)
- Average earnings per trade (% of capital used)
- Average PnL per trade (absolute)
- Win rate (%)
- Loss rate (%)
- Sharpe ratio
- Max drawdown (%)
- Total trades executed

## How It Works

1. **Data Collection**: Fetches 1 month of 1-minute OHLCV data using CCXT (cached for reuse)
2. **Signal Generation**: Calculates Supertrend indicator and generates buy/sell signals
3. **Simulation**: Runs exact trading logic from `app.py`:
   - 99% capital allocation per trade
   - Taker/Maker fees
   - Break-even price calculation
   - Stop-loss and take-profit monitoring
   - Cooldown enforcement
4. **Optimization**: Tests millions of parameter combinations using multi-stage approach
5. **Analysis**: Generates comprehensive reports and visualizations

## Example Output

```
BEST PARAMETERS
============================================================
ATR Period: 3
Multiplier: 6.0
Stop Loss Long: 0.70%
Stop Loss Short: 0.70%
Take Profit: 0.10%
Cooldown: 600 seconds

Performance Metrics:
  Total PnL: $123.45 (1.23%)
  Total Trades: 68
  Win Rate: 95.59%
  Avg Earnings/Trade: 0.0181%
  Avg PnL/Trade: $1.82
  Sharpe Ratio: 2.3456
  Max Drawdown: 0.15%
============================================================
```


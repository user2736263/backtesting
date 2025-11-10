# Quick Start Guide - Backtesting System

## How to Run in Cursor (or Terminal)

### Option 1: Using the Convenience Script (Easiest)

```bash
python run_backtest.py
```

### Option 2: Using Python Module

```bash
python -m backtest.run_optimization
```

### Option 3: With Custom Options

```bash
# Quick test with fewer combinations (faster)
python run_backtest.py --max-combinations 1000 --skip-stage3

# Full optimization (takes 40-80 minutes)
python run_backtest.py --max-combinations 10000
```

## What You'll See

The output will look like this:

```
============================================================
HYPERLIQUID TRADING BOT - PARAMETER OPTIMIZATION
============================================================
Symbol: SOL/USDC
Period: 1m (interpreted as 1 month)
Timeframe: 1m
Starting Capital: $10,000.00
Parallel Jobs: All CPUs
============================================================

[Step 1] Fetching historical data...
📦 Found cached data: backtest_data_cache/SOL_USDC_1m_30d.csv
✓ Loaded 43200 candles from cache
  Date range: 2024-10-10 00:00:00 to 2024-11-10 23:59:00

[Step 2] Initializing optimizer...

[Step 3] Running optimization...

Stage 1: Random Sampling (10000 combinations)
Testing random parameter combinations across full search space...
Stage 1: Random Sampling: 100%|████████████| 10000/10000 [15:23<00:00, 10.8it/s]

✓ Stage 1 Complete!
  Best Score: 2.3456
  Best PnL: $123.45 (1.23%)
  Best Win Rate: 95.59%

Stage 2: Refinement (top 100 results)
Fine-tuning top 100 parameter sets with smaller steps...
Stage 2: Refinement: 100%|████████████| 2500/2500 [12:45<00:00, 3.2it/s]

✓ Stage 2 Complete!
  Best Score: 2.4567
  Best PnL: $145.67 (1.46%)
  Best Win Rate: 96.12%

Stage 3: Exhaustive Search
Exhaustive search around best parameters...
Stage 3: Exhaustive Search: 100%|████████████| 1331/1331 [08:12<00:00, 2.7it/s]

✓ Stage 3 Complete!
  Best Score: 2.4789
  Best PnL: $156.78 (1.57%)
  Best Win Rate: 96.34%

[Step 4] Generating analysis reports...
Exported 14831 results to backtest_results/all_results.csv
Exported top 50 results to backtest_results/top_50_results.json
Generated HTML report: backtest_results/report.html
Saved equity curve to backtest_results/best_equity_curve.png
Saved trade distribution to backtest_results/best_trade_distribution.png

============================================================
BEST PARAMETERS
============================================================
ATR Period: 3
Multiplier: 6.0
Stop Loss Long: 0.70%
Stop Loss Short: 0.70%
Take Profit: 0.10%
Cooldown: 600 seconds

Performance Metrics:
  Total PnL: $156.78 (1.57%)
  Total Trades: 68
  Win Rate: 96.34%
  Avg Earnings/Trade: 0.0231%
  Avg PnL/Trade: $2.31
  Sharpe Ratio: 2.4789
  Max Drawdown: 0.15%
============================================================

✓ Reports saved to: backtest_results/
  - all_results.csv
  - top_50_results.json
  - report.html
  - best_equity_curve.png
  - best_trade_distribution.png
```

## Progress Indicators

- **Progress bars**: Shows percentage complete and estimated time remaining
- **Stage updates**: Clear messages when each stage completes
- **Best results**: Shows best score, PnL, and win rate after each stage
- **Final summary**: Complete parameter set and performance metrics

## Output Files

All results are saved to `backtest_results/`:

- `all_results.csv` - All tested combinations (can open in Excel)
- `top_50_results.json` - Top 50 in JSON format
- `report.html` - Beautiful HTML report (open in browser)
- `best_equity_curve.png` - Visual equity curve
- `best_trade_distribution.png` - Trade PnL distribution

## Tips

1. **First run**: Will download data (takes 1-2 minutes), then cached for future runs
2. **Quick test**: Use `--max-combinations 1000 --skip-stage3` for a 5-minute test
3. **Full optimization**: Use default settings for complete optimization (40-80 minutes)
4. **Monitor progress**: Progress bars show real-time status and ETA

## Troubleshooting

**If you get import errors:**
```bash
pip install -r requirements.txt
```

**If data fetch fails:**
- Check internet connection
- The system will try multiple exchanges automatically
- Data is cached after first successful fetch

**If it's too slow:**
- Reduce `--max-combinations` (e.g., 1000 instead of 10000)
- Skip stage 3 with `--skip-stage3`
- Use fewer CPU cores with `--n-jobs 4`


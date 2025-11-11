"""
Main entry point for running parameter optimization.
"""

import argparse
import sys
import os
import pandas as pd
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_fetcher import fetch_historical_data
from optimizer import Optimizer
from analyzer import ResultsAnalyzer


def main():
    """Main function to run optimization."""
    parser = argparse.ArgumentParser(description='Backtest and optimize trading bot parameters')
    
    parser.add_argument('--symbol', type=str, default='SOL/USDC', help='Trading pair (default: SOL/USDC)')
    parser.add_argument('--period', type=str, default='1m', help='Data period: 1m = 1 month (default: 1m)')
    parser.add_argument('--timeframe', type=str, default='1m', help='Candle timeframe (default: 1m)')
    parser.add_argument('--capital', type=float, default=10000.0, help='Starting capital (default: 10000)')
    parser.add_argument('--stages', type=str, default='all', choices=['1', '2', '3', 'all'], 
                       help='Which optimization stages to run (default: all)')
    parser.add_argument('--max-combinations', type=int, default=10000, 
                       help='Max random combinations for Stage 1 (default: 10000)')
    parser.add_argument('--stage2-top-n', type=int, default=20,
                       help='Top N results to refine in Stage 2 (default: 20)')
    parser.add_argument('--skip-stage3', action='store_true',
                       help='Skip Stage 3 exhaustive search')
    parser.add_argument('--n-jobs', type=int, default=None,
                       help='Number of parallel jobs (default: all CPUs)')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("HYPERLIQUID TRADING BOT - PARAMETER OPTIMIZATION")
    print("=" * 60)
    print(f"Symbol: {args.symbol}")
    print(f"Period: {args.period} (interpreted as 1 month)")
    print(f"Timeframe: {args.timeframe}")
    print(f"Starting Capital: ${args.capital:,.2f}")
    print(f"Parallel Jobs: {args.n_jobs or 'All CPUs'}")
    print("=" * 60)
    
    # Step 1: Fetch historical data
    print("\n[Step 1] Fetching historical data...")
    try:
        # For now, always fetch 1 month (30 days) regardless of --period flag
        # The --period flag is kept for future extensibility
        df = fetch_historical_data(
            symbol=args.symbol,
            timeframe=args.timeframe,
            days=30  # 1 month
        )
        print(f"✓ Loaded {len(df)} candles")
        print(f"  Date range: {df.index.min()} to {df.index.max()}")
    except Exception as e:
        print(f"✗ Error fetching data: {e}")
        sys.exit(1)
    
    # Step 2: Initialize optimizer
    print("\n[Step 2] Initializing optimizer...")
    optimizer = Optimizer(
        df=df,
        initial_capital=args.capital,
        n_jobs=args.n_jobs
    )
    
    # Step 3: Run optimization stages
    print("\n[Step 3] Running optimization...")
    stage1_results = None
    stage2_results = None
    stage3_results = None
    
    if args.stages in ['1', 'all']:
        print("\n" + "="*60)
        print("STAGE 1: Random Sampling")
        print("="*60)
        print(f"Testing {args.max_combinations} random parameter combinations...")
        print(f"Using {optimizer.n_jobs} CPU cores for parallel processing")
        stage1_results = optimizer.stage1_random_sampling(
            n_combinations=args.max_combinations
        )
        print(f"\n✓ Stage 1 complete: {len(stage1_results)} combinations tested")
        print(f"  Best score: {stage1_results[0].score:.4f}")
        print(f"  Best total PnL: ${stage1_results[0].results.total_pnl:.2f} ({stage1_results[0].results.total_pnl_percent:.2f}%)")
        print(f"  Best win rate: {stage1_results[0].results.win_rate:.2f}%")
    
    if args.stages in ['2', 'all'] and stage1_results:
        print("\n" + "="*60)
        print("STAGE 2: Refinement")
        print("="*60)
        print(f"Fine-tuning top {args.stage2_top_n} results from Stage 1...")
        stage2_results = optimizer.stage2_refinement(
            top_results=stage1_results,
            top_n=args.stage2_top_n
        )
        print(f"\n✓ Stage 2 complete: {len(stage2_results)} combinations tested")
        print(f"  Best score: {stage2_results[0].score:.4f}")
        print(f"  Best total PnL: ${stage2_results[0].results.total_pnl:.2f} ({stage2_results[0].results.total_pnl_percent:.2f}%)")
        print(f"  Best win rate: {stage2_results[0].results.win_rate:.2f}%")
    
    if args.stages in ['3', 'all'] and not args.skip_stage3:
        print("\n" + "="*60)
        print("STAGE 3: Exhaustive Search")
        print("="*60)
        print("Exhaustive search around best parameters...")
        best_for_stage3 = stage2_results[0] if stage2_results else stage1_results[0]
        stage3_results = optimizer.stage3_exhaustive_search(best_for_stage3)
        print(f"\n✓ Stage 3 complete: {len(stage3_results)} combinations tested")
        print(f"  Best score: {stage3_results[0].score:.4f}")
        print(f"  Best total PnL: ${stage3_results[0].results.total_pnl:.2f} ({stage3_results[0].results.total_pnl_percent:.2f}%)")
        print(f"  Best win rate: {stage3_results[0].results.win_rate:.2f}%")
    
    # Step 4: Generate reports
    print("\n[Step 4] Generating analysis reports...")
    analyzer = ResultsAnalyzer()
    
    # Determine which results to use for final report
    final_results = stage3_results if stage3_results else (stage2_results if stage2_results else stage1_results)
    
    if final_results:
        analyzer.generate_full_report(
            stage1_results=stage1_results or [],
            stage2_results=stage2_results or [],
            stage3_results=stage3_results
        )
        
        # Print best parameters
        print("\n" + "=" * 60)
        print("BEST PARAMETERS")
        print("=" * 60)
        best = final_results[0]
        params = best.parameters
        print(f"ATR Period: {params.atr_period}")
        print(f"Multiplier: {params.multiplier}")
        print(f"Stop Loss Long: {params.stop_loss_long * 100:.2f}%")
        print(f"Stop Loss Short: {params.stop_loss_short * 100:.2f}%")
        print(f"Take Profit: {params.take_profit * 100:.2f}%")
        print(f"Cooldown: {params.cooldown} seconds")
        print("\nPerformance Metrics:")
        res = best.results
        print(f"  Total PnL: ${res.total_pnl:.2f} ({res.total_pnl_percent:.2f}%)")
        print(f"  Total Trades: {res.total_trades}")
        print(f"  Win Rate: {res.win_rate:.2f}%")
        print(f"  Avg Earnings/Trade: {res.average_earnings_per_trade_percent:.4f}%")
        print(f"  Avg PnL/Trade: ${res.average_pnl_per_trade:.2f}")
        print(f"  Sharpe Ratio: {res.sharpe_ratio:.4f}")
        print(f"  Max Drawdown: {res.max_drawdown * 100:.2f}%")
        print("=" * 60)
        
        print(f"\n✓ Reports saved to: {analyzer.output_dir}/")
        print("  - all_results.csv")
        print("  - top_50_results.json")
        print("  - report.html")
        print("  - best_equity_curve.png")
        print("  - best_trade_distribution.png")
    else:
        print("✗ No results to analyze")
        sys.exit(1)


if __name__ == "__main__":
    main()


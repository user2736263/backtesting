"""
Results analysis and reporting module.
"""

import pandas as pd
import json
import os
from typing import List, Dict
from datetime import datetime
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
try:
    from .optimizer import OptimizationResult
except ImportError:
    from optimizer import OptimizationResult


class ResultsAnalyzer:
    """Analyze and report optimization results."""
    
    def __init__(self, output_dir: str = "backtest_results"):
        """Initialize analyzer with output directory."""
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
    
    def generate_top_results_table(
        self,
        results: List[OptimizationResult],
        top_n: int = 50
    ) -> pd.DataFrame:
        """Generate a table of top N results."""
        rows = []
        
        for i, result in enumerate(results[:top_n], 1):
            params = result.parameters
            res = result.results
            
            rows.append({
                'Rank': i,
                'Score': round(result.score, 4),
                'ATR': params.atr_period,
                'Multiplier': params.multiplier,
                'Stop Loss Long (%)': round(params.stop_loss_long * 100, 2),
                'Stop Loss Short (%)': round(params.stop_loss_short * 100, 2),
                'Take Profit (%)': round(params.take_profit * 100, 2),
                'Cooldown (s)': params.cooldown,
                'Total PnL': round(res.total_pnl, 2),
                'Total PnL (%)': round(res.total_pnl_percent, 2),
                'Total Trades': res.total_trades,
                'Win Rate (%)': round(res.win_rate, 2),
                'Loss Rate (%)': round(res.loss_rate, 2),
                'Avg Earnings/Trade (%)': round(res.average_earnings_per_trade_percent, 4),
                'Avg PnL/Trade': round(res.average_pnl_per_trade, 2),
                'Sharpe Ratio': round(res.sharpe_ratio, 4),
                'Max Drawdown (%)': round(res.max_drawdown * 100, 2),
                'Final Capital': round(res.final_capital, 2)
            })
        
        return pd.DataFrame(rows)
    
    def export_to_csv(
        self,
        results: List[OptimizationResult],
        filename: str = "optimization_results.csv"
    ):
        """Export all results to CSV."""
        rows = []
        
        for result in results:
            params = result.parameters
            res = result.results
            
            row = {
                'score': result.score,
                'atr_period': params.atr_period,
                'multiplier': params.multiplier,
                'stop_loss_long': params.stop_loss_long,
                'stop_loss_short': params.stop_loss_short,
                'take_profit': params.take_profit,
                'cooldown': params.cooldown,
                'total_pnl': res.total_pnl,
                'total_pnl_percent': res.total_pnl_percent,
                'total_trades': res.total_trades,
                'winning_trades': res.winning_trades,
                'losing_trades': res.losing_trades,
                'win_rate': res.win_rate,
                'loss_rate': res.loss_rate,
                'avg_earnings_per_trade_percent': res.average_earnings_per_trade_percent,
                'avg_pnl_per_trade': res.average_pnl_per_trade,
                'sharpe_ratio': res.sharpe_ratio,
                'max_drawdown': res.max_drawdown,
                'final_capital': res.final_capital
            }
            rows.append(row)
        
        df = pd.DataFrame(rows)
        filepath = os.path.join(self.output_dir, filename)
        df.to_csv(filepath, index=False)
        print(f"Exported {len(results)} results to {filepath}")
    
    def export_top_to_json(
        self,
        results: List[OptimizationResult],
        top_n: int = 50,
        filename: str = "top_results.json"
    ):
        """Export top N results to JSON."""
        top_results = []
        
        for i, result in enumerate(results[:top_n], 1):
            params = result.parameters
            res = result.results
            
            result_dict = {
                'rank': i,
                'score': result.score,
                'parameters': {
                    'atr_period': params.atr_period,
                    'multiplier': params.multiplier,
                    'stop_loss_long': params.stop_loss_long,
                    'stop_loss_short': params.stop_loss_short,
                    'take_profit': params.take_profit,
                    'cooldown': params.cooldown,
                    'taker_fee_rate': params.taker_fee_rate,
                    'maker_fee_rate': params.maker_fee_rate,
                    'capital_allocation': params.capital_allocation
                },
                'results': {
                    'total_pnl': res.total_pnl,
                    'total_pnl_percent': res.total_pnl_percent,
                    'total_trades': res.total_trades,
                    'winning_trades': res.winning_trades,
                    'losing_trades': res.losing_trades,
                    'win_rate': res.win_rate,
                    'loss_rate': res.loss_rate,
                    'average_earnings_per_trade_percent': res.average_earnings_per_trade_percent,
                    'average_pnl_per_trade': res.average_pnl_per_trade,
                    'sharpe_ratio': res.sharpe_ratio,
                    'max_drawdown': res.max_drawdown,
                    'final_capital': res.final_capital
                }
            }
            top_results.append(result_dict)
        
        filepath = os.path.join(self.output_dir, filename)
        with open(filepath, 'w') as f:
            json.dump(top_results, f, indent=2, default=str)
        print(f"Exported top {top_n} results to {filepath}")
    
    def plot_equity_curve(
        self,
        result: OptimizationResult,
        filename: str = "equity_curve.png"
    ):
        """Plot equity curve for a single result."""
        equity = result.results.equity_curve
        
        plt.figure(figsize=(12, 6))
        plt.plot(equity, linewidth=2)
        plt.title(f"Equity Curve\nScore: {result.score:.4f} | Final Capital: ${result.results.final_capital:.2f}")
        plt.xlabel("Time Step")
        plt.ylabel("Capital ($)")
        plt.grid(True, alpha=0.3)
        
        filepath = os.path.join(self.output_dir, filename)
        plt.savefig(filepath, dpi=150, bbox_inches='tight')
        plt.close()
        print(f"Saved equity curve to {filepath}")
    
    def plot_trade_distribution(
        self,
        result: OptimizationResult,
        filename: str = "trade_distribution.png"
    ):
        """Plot PnL distribution of trades."""
        trades = result.results.trades
        if not trades:
            print("No trades to plot")
            return
        
        pnls = [t.pnl for t in trades]
        
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
        
        # Histogram
        ax1.hist(pnls, bins=30, edgecolor='black', alpha=0.7)
        ax1.axvline(0, color='red', linestyle='--', linewidth=2, label='Break Even')
        ax1.set_xlabel('PnL ($)')
        ax1.set_ylabel('Frequency')
        ax1.set_title('PnL Distribution')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # Box plot
        ax2.boxplot(pnls, vert=True)
        ax2.axhline(0, color='red', linestyle='--', linewidth=2)
        ax2.set_ylabel('PnL ($)')
        ax2.set_title('PnL Box Plot')
        ax2.grid(True, alpha=0.3)
        
        plt.tight_layout()
        filepath = os.path.join(self.output_dir, filename)
        plt.savefig(filepath, dpi=150, bbox_inches='tight')
        plt.close()
        print(f"Saved trade distribution to {filepath}")
    
    def generate_html_report(
        self,
        results: List[OptimizationResult],
        top_n: int = 50
    ):
        """Generate HTML report with top results."""
        top_table = self.generate_top_results_table(results, top_n)
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Backtest Optimization Results</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: right; }}
        th {{ background-color: #4CAF50; color: white; }}
        tr:nth-child(even) {{ background-color: #f2f2f2; }}
        .best {{ background-color: #ffeb3b !important; font-weight: bold; }}
        h1 {{ color: #333; }}
        .summary {{ background-color: #e3f2fd; padding: 15px; border-radius: 5px; margin: 20px 0; }}
    </style>
</head>
<body>
    <h1>Backtest Optimization Results</h1>
    <div class="summary">
        <h2>Summary</h2>
        <p><strong>Total Combinations Tested:</strong> {len(results)}</p>
        <p><strong>Best Score:</strong> {results[0].score:.4f}</p>
        <p><strong>Best Total PnL:</strong> ${results[0].results.total_pnl:.2f} ({results[0].results.total_pnl_percent:.2f}%)</p>
        <p><strong>Best Win Rate:</strong> {results[0].results.win_rate:.2f}%</p>
        <p><strong>Best Avg Earnings/Trade:</strong> {results[0].results.average_earnings_per_trade_percent:.4f}%</p>
        <p><strong>Best Sharpe Ratio:</strong> {results[0].results.sharpe_ratio:.4f}</p>
    </div>
    <h2>Top {top_n} Results</h2>
    {top_table.to_html(classes='results-table', index=False, escape=False)}
    <p><em>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</em></p>
</body>
</html>
"""
        
        filepath = os.path.join(self.output_dir, "report.html")
        with open(filepath, 'w') as f:
            f.write(html)
        print(f"Generated HTML report: {filepath}")
    
    def analyze_parameter_sensitivity(
        self,
        results: List[OptimizationResult],
        top_n: int = 1000
    ) -> Dict:
        """Analyze parameter sensitivity from top results."""
        top_results = results[:top_n]
        
        if not top_results:
            return {}
        
        # Calculate averages for top results
        avg_atr = sum(r.parameters.atr_period for r in top_results) / len(top_results)
        avg_multiplier = sum(r.parameters.multiplier for r in top_results) / len(top_results)
        avg_stop_loss_long = sum(r.parameters.stop_loss_long for r in top_results) / len(top_results)
        avg_stop_loss_short = sum(r.parameters.stop_loss_short for r in top_results) / len(top_results)
        avg_take_profit = sum(r.parameters.take_profit for r in top_results) / len(top_results)
        avg_cooldown = sum(r.parameters.cooldown for r in top_results) / len(top_results)
        
        return {
            'average_atr_period': avg_atr,
            'average_multiplier': avg_multiplier,
            'average_stop_loss_long': avg_stop_loss_long,
            'average_stop_loss_short': avg_stop_loss_short,
            'average_take_profit': avg_take_profit,
            'average_cooldown': avg_cooldown,
            'sample_size': len(top_results)
        }
    
    def generate_full_report(
        self,
        stage1_results: List[OptimizationResult],
        stage2_results: List[OptimizationResult],
        stage3_results: List[OptimizationResult] = None
    ):
        """Generate comprehensive report from all stages."""
        print("\n" + "=" * 60)
        print("Generating Analysis Reports")
        print("=" * 60)
        
        # Use best results (stage3 if available, else stage2)
        best_results = stage3_results if stage3_results else stage2_results
        
        # Export CSV
        self.export_to_csv(best_results, "all_results.csv")
        
        # Export top JSON
        self.export_top_to_json(best_results, top_n=50, filename="top_50_results.json")
        
        # Generate HTML report
        self.generate_html_report(best_results, top_n=50)
        
        # Plot best result
        if best_results:
            self.plot_equity_curve(best_results[0], "best_equity_curve.png")
            self.plot_trade_distribution(best_results[0], "best_trade_distribution.png")
        
        # Parameter sensitivity
        sensitivity = self.analyze_parameter_sensitivity(best_results, top_n=100)
        print("\nParameter Sensitivity Analysis (Top 100):")
        for key, value in sensitivity.items():
            if isinstance(value, float):
                print(f"  {key}: {value:.4f}")
            else:
                print(f"  {key}: {value}")
        
        # Print top 10
        print("\n" + "=" * 60)
        print("TOP 10 RESULTS")
        print("=" * 60)
        top_table = self.generate_top_results_table(best_results, top_n=10)
        print(top_table.to_string(index=False))


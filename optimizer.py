"""
Parameter optimization engine with multi-stage optimization strategy.
"""

import random
import multiprocessing as mp
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, asdict
import pandas as pd
from tqdm import tqdm
try:
    from .backtester import BacktestEngine, BacktestResults
except ImportError:
    from backtester import BacktestEngine, BacktestResults


@dataclass
class ParameterSet:
    """Represents a set of parameters to test."""
    atr_period: int
    multiplier: float
    stop_loss_long: float
    stop_loss_short: float
    take_profit: float
    cooldown: int
    taker_fee_rate: float = 0.000432
    maker_fee_rate: float = 0.000144
    capital_allocation: float = 0.99


@dataclass
class OptimizationResult:
    """Result from a single parameter set test."""
    parameters: ParameterSet
    results: BacktestResults
    score: float  # Combined score for ranking


def run_single_backtest(
    df: pd.DataFrame,
    params: ParameterSet,
    initial_capital: float = 10000.0
) -> OptimizationResult:
    """
    Run a single backtest with given parameters.
    This function is designed to be called in parallel.
    """
    engine = BacktestEngine(
        initial_capital=initial_capital,
        capital_allocation_percent=params.capital_allocation,
        taker_fee_rate=params.taker_fee_rate,
        maker_fee_rate=params.maker_fee_rate,
        stop_loss_percent_long=params.stop_loss_long,
        stop_loss_percent_short=params.stop_loss_short,
        target_profit_percent=params.take_profit,
        cooldown_seconds=params.cooldown
    )
    
    results = engine.run(df, atr_period=params.atr_period, multiplier=params.multiplier)
    
    # Calculate combined score (weighted)
    # Primary: average earnings per trade (%)
    # Secondary: total PnL, win rate, Sharpe ratio
    score = (
        results.average_earnings_per_trade_percent * 0.4 +
        (results.total_pnl_percent / 10.0) * 0.2 +  # Normalize
        results.win_rate * 0.2 +
        results.sharpe_ratio * 10.0 * 0.2  # Normalize
    )
    
    return OptimizationResult(
        parameters=params,
        results=results,
        score=score
    )


def generate_random_parameters(
    n: int,
    atr_range: Tuple[int, int] = (1, 50),
    multiplier_range: Tuple[float, float] = (0.5, 20.0),
    stop_loss_range: Tuple[float, float] = (0.0001, 0.02),  # 0.01% to 2%
    take_profit_range: Tuple[float, float] = (0.0001, 0.02),
    cooldown_range: Tuple[int, int] = (0, 3600)
) -> List[ParameterSet]:
    """Generate n random parameter sets."""
    params_list = []
    
    for _ in range(n):
        params = ParameterSet(
            atr_period=random.randint(atr_range[0], atr_range[1]),
            multiplier=round(random.uniform(multiplier_range[0], multiplier_range[1]), 1),
            stop_loss_long=round(random.uniform(stop_loss_range[0], stop_loss_range[1]), 4),
            stop_loss_short=round(random.uniform(stop_loss_range[0], stop_loss_range[1]), 4),
            take_profit=round(random.uniform(take_profit_range[0], take_profit_range[1]), 4),
            cooldown=random.randint(cooldown_range[0] // 60, cooldown_range[1] // 60) * 60  # Round to 60s
        )
        params_list.append(params)
    
    return params_list


def generate_refinement_grid(
    base_params: ParameterSet,
    step_sizes: Dict[str, float],
    grid_size: int = 3
) -> List[ParameterSet]:
    """
    Generate a fine-grained grid around a base parameter set.
    
    Args:
        base_params: Base parameters to refine around
        step_sizes: Step sizes for each parameter
        grid_size: Number of steps in each direction (total points = (2*grid_size+1)^6)
    """
    params_list = []
    
    # Generate grid around base
    for atr_offset in range(-grid_size, grid_size + 1):
        atr = max(1, min(50, base_params.atr_period + atr_offset))
        
        for mult_offset in range(-grid_size, grid_size + 1):
            mult = round(max(0.5, min(20.0, base_params.multiplier + mult_offset * step_sizes.get('multiplier', 0.5))), 1)
            
            for sl_offset in range(-grid_size, grid_size + 1):
                sl = round(max(0.0001, min(0.02, base_params.stop_loss_long + sl_offset * step_sizes.get('stop_loss', 0.0001))), 4)
                sl_short = round(max(0.0001, min(0.02, base_params.stop_loss_short + sl_offset * step_sizes.get('stop_loss', 0.0001))), 4)
                
                for tp_offset in range(-grid_size, grid_size + 1):
                    tp = round(max(0.0001, min(0.02, base_params.take_profit + tp_offset * step_sizes.get('take_profit', 0.0001))), 4)
                    
                    for cd_offset in range(-grid_size, grid_size + 1):
                        cd = max(0, min(3600, base_params.cooldown + cd_offset * step_sizes.get('cooldown', 60)))
                        cd = (cd // 60) * 60  # Round to 60s
                        
                        params = ParameterSet(
                            atr_period=atr,
                            multiplier=mult,
                            stop_loss_long=sl,
                            stop_loss_short=sl_short,
                            take_profit=tp,
                            cooldown=cd,
                            taker_fee_rate=base_params.taker_fee_rate,
                            maker_fee_rate=base_params.maker_fee_rate,
                            capital_allocation=base_params.capital_allocation
                        )
                        params_list.append(params)
    
    return params_list


class Optimizer:
    """Multi-stage parameter optimizer."""
    
    def __init__(
        self,
        df: pd.DataFrame,
        initial_capital: float = 10000.0,
        n_jobs: Optional[int] = None
    ):
        """
        Initialize optimizer.
        
        Args:
            df: Historical price data
            initial_capital: Starting capital
            n_jobs: Number of parallel jobs (None = use all CPUs)
        """
        self.df = df
        self.initial_capital = initial_capital
        self.n_jobs = n_jobs or mp.cpu_count()
    
    def stage1_random_sampling(
        self,
        n_combinations: int = 10000,
        progress: bool = True
    ) -> List[OptimizationResult]:
        """
        Stage 1: Random sampling of parameter space.
        
        Args:
            n_combinations: Number of random combinations to test
            progress: Show progress bar
        
        Returns:
            List of optimization results, sorted by score (best first)
        """
        params_list = generate_random_parameters(n_combinations)
        
        # Run backtests in parallel
        results = self._run_parallel(params_list, progress, desc="Stage 1: Random Sampling")
        
        # Sort by score (best first)
        results.sort(key=lambda x: x.score, reverse=True)
        
        return results
    
    def stage2_refinement(
        self,
        top_results: List[OptimizationResult],
        top_n: int = 100,
        progress: bool = True
    ) -> List[OptimizationResult]:
        """
        Stage 2: Fine-tune top N results.
        
        Args:
            top_results: Results from Stage 1
            top_n: Number of top results to refine
            progress: Show progress bar
        
        Returns:
            List of refined optimization results
        """
        # Adaptive top_n: limit to prevent explosion
        # Limit to max 20 bases, or 10% of Stage 1 results, whichever is smaller
        max_top_n = min(top_n, max(10, min(20, len(top_results) // 10)))
        top_params = [r.parameters for r in top_results[:max_top_n]]
        
        print(f"  📊 Refining top {max_top_n} results (limited from {top_n} to prevent too many tests)")
        
        # Generate refinement grids with smaller grid_size
        step_sizes = {
            'multiplier': 0.1,
            'stop_loss': 0.00005,  # 0.005%
            'take_profit': 0.00005,
            'cooldown': 30
        }
        
        all_params = []
        for base in top_params:
            # Use grid_size=1 (3^6 = 729) instead of 2 (5^6 = 15,625)
            grid = generate_refinement_grid(base, step_sizes, grid_size=1)
            all_params.extend(grid)
        
        # Remove duplicates
        seen = set()
        unique_params = []
        for p in all_params:
            key = (p.atr_period, p.multiplier, p.stop_loss_long, p.stop_loss_short, p.take_profit, p.cooldown)
            if key not in seen:
                seen.add(key)
                unique_params.append(p)
        
        print(f"  📊 Generated {len(unique_params)} unique parameter combinations for Stage 2")
        
        # Run backtests
        results = self._run_parallel(unique_params, progress, desc="Stage 2: Refinement")
        
        # Sort by score
        results.sort(key=lambda x: x.score, reverse=True)
        
        return results
    
    def stage3_exhaustive_search(
        self,
        best_result: OptimizationResult,
        progress: bool = True
    ) -> List[OptimizationResult]:
        """
        Stage 3: Exhaustive search in best region.
        
        Args:
            best_result: Best result from previous stages
            progress: Show progress bar
        
        Returns:
            List of optimization results
        """
        base = best_result.parameters
        
        # Create exhaustive grid with small steps
        step_sizes = {
            'multiplier': 0.05,
            'stop_loss': 0.00001,  # 0.001%
            'take_profit': 0.00001,
            'cooldown': 10
        }
        
        # Use grid_size=2 (5^6 = 15,625) instead of 5 (11^6 = 1,771,561)
        grid = generate_refinement_grid(base, step_sizes, grid_size=2)
        
        print(f"  📊 Generated {len(grid)} combinations for Stage 3")
        
        # Run backtests
        results = self._run_parallel(grid, progress, desc="Stage 3: Exhaustive Search")
        
        # Sort by score
        results.sort(key=lambda x: x.score, reverse=True)
        
        return results
    
    def _run_parallel(
        self,
        params_list: List[ParameterSet],
        progress: bool = True,
        desc: str = "Optimizing"
    ) -> List[OptimizationResult]:
        """Run backtests in parallel."""
        # Prepare arguments for multiprocessing
        args = [(self.df, params, self.initial_capital) for params in params_list]
        
        print(f"  🔄 Starting {len(args)} backtests on {self.n_jobs} CPU cores...")
        
        # Run in parallel with incremental progress
        with mp.Pool(processes=self.n_jobs) as pool:
            if progress:
                # Use starmap but wrap in tqdm for progress tracking
                results = []
                with tqdm(total=len(args), desc=desc, unit="test", ncols=100) as pbar:
                    # Process in chunks to show progress incrementally
                    chunk_size = max(1, len(args) // 100)  # Update progress every 1%
                    for i in range(0, len(args), chunk_size):
                        chunk = args[i:i+chunk_size]
                        chunk_results = pool.starmap(run_single_backtest, chunk)
                        results.extend(chunk_results)
                        pbar.update(len(chunk))
            else:
                results = pool.starmap(run_single_backtest, args)
        
        return results
    
    def optimize_all_stages(
        self,
        stage1_n: int = 10000,
        stage2_top_n: int = 100,
        run_stage3: bool = True
    ) -> Tuple[List[OptimizationResult], List[OptimizationResult], Optional[List[OptimizationResult]]]:
        """
        Run all optimization stages.
        
        Returns:
            Tuple of (stage1_results, stage2_results, stage3_results)
        """
        print("=" * 60)
        print("Starting Multi-Stage Optimization")
        print("=" * 60)
        
        # Stage 1
        print(f"\nStage 1: Random Sampling ({stage1_n} combinations)")
        print(f"Testing random parameter combinations across full search space...")
        stage1_results = self.stage1_random_sampling(stage1_n)
        print(f"\n✓ Stage 1 Complete!")
        print(f"  Best Score: {stage1_results[0].score:.4f}")
        print(f"  Best PnL: ${stage1_results[0].results.total_pnl:.2f} ({stage1_results[0].results.total_pnl_percent:.2f}%)")
        print(f"  Best Win Rate: {stage1_results[0].results.win_rate:.2f}%")
        
        # Stage 2
        print(f"\nStage 2: Refinement (top {stage2_top_n} results)")
        print(f"Fine-tuning top {stage2_top_n} parameter sets with smaller steps...")
        stage2_results = self.stage2_refinement(stage1_results, stage2_top_n)
        print(f"\n✓ Stage 2 Complete!")
        print(f"  Best Score: {stage2_results[0].score:.4f}")
        print(f"  Best PnL: ${stage2_results[0].results.total_pnl:.2f} ({stage2_results[0].results.total_pnl_percent:.2f}%)")
        print(f"  Best Win Rate: {stage2_results[0].results.win_rate:.2f}%")
        
        # Stage 3
        stage3_results = None
        if run_stage3:
            print(f"\nStage 3: Exhaustive Search")
            print(f"Exhaustive search around best parameters...")
            stage3_results = self.stage3_exhaustive_search(stage2_results[0])
            print(f"\n✓ Stage 3 Complete!")
            print(f"  Best Score: {stage3_results[0].score:.4f}")
            print(f"  Best PnL: ${stage3_results[0].results.total_pnl:.2f} ({stage3_results[0].results.total_pnl_percent:.2f}%)")
            print(f"  Best Win Rate: {stage3_results[0].results.win_rate:.2f}%")
        
        return stage1_results, stage2_results, stage3_results


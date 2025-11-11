"""
Core backtesting engine that simulates the exact trading logic from app.py.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
try:
    from .indicators import generate_signals
    from .utils import calculate_sharpe_ratio, calculate_max_drawdown
except ImportError:
    from indicators import generate_signals
    from utils import calculate_sharpe_ratio, calculate_max_drawdown


@dataclass
class Trade:
    """Represents a single trade."""
    entry_time: datetime
    exit_time: Optional[datetime]
    entry_price: float
    exit_price: Optional[float]
    position_side: str  # "long" or "short"
    quantity: float
    pnl: Optional[float]
    pnl_percent: Optional[float]
    exit_reason: Optional[str]  # "profit_target", "stop_loss", "signal"
    duration_seconds: Optional[float]
    highest_price: Optional[float]
    lowest_price: Optional[float]
    break_even_price: float
    target_profit_price: float


@dataclass
class BacktestResults:
    """Results from a backtest run."""
    total_pnl: float
    total_pnl_percent: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    loss_rate: float
    average_earnings_per_trade_percent: float
    average_pnl_per_trade: float
    sharpe_ratio: float
    max_drawdown: float
    trades: List[Trade]
    equity_curve: List[float]
    final_capital: float


class BacktestEngine:
    """
    Core simulation engine that mirrors the exact trading logic from app.py.
    """
    
    def __init__(
        self,
        initial_capital: float = 10000.0,
        capital_allocation_percent: float = 0.99,
        taker_fee_rate: float = 0.000432,
        maker_fee_rate: float = 0.000144,
        stop_loss_percent_long: float = 0.007,
        stop_loss_percent_short: float = 0.007,
        target_profit_percent: float = 0.001,
        cooldown_seconds: int = 600
    ):
        """
        Initialize the backtest engine.
        
        Args:
            initial_capital: Starting capital in USDC
            capital_allocation_percent: Percentage of capital to use per trade (0.99 = 99%)
            taker_fee_rate: Taker fee rate (entry)
            maker_fee_rate: Maker fee rate (exit)
            stop_loss_percent_long: Stop-loss percentage for long positions
            stop_loss_percent_short: Stop-loss percentage for short positions
            target_profit_percent: Target profit percentage above break-even
            cooldown_seconds: Cooldown period between trades
        """
        self.initial_capital = initial_capital
        self.capital_allocation_percent = capital_allocation_percent
        self.taker_fee_rate = taker_fee_rate
        self.maker_fee_rate = maker_fee_rate
        self.stop_loss_percent_long = stop_loss_percent_long
        self.stop_loss_percent_short = stop_loss_percent_short
        self.target_profit_percent = target_profit_percent
        self.cooldown_seconds = cooldown_seconds
        
        # State variables (mirror app.py)
        self.capital = initial_capital
        self.in_position = False
        self.position_side = None
        self.entry_price = None
        self.position_quantity = None
        self.entry_time = None
        self.break_even_price = None
        self.target_profit_price = None
        self.highest_price = None
        self.lowest_price = None
        self.last_trade_timestamp = None
        
        # Track trades and equity
        self.trades: List[Trade] = []
        self.equity_curve: List[float] = [initial_capital]
    
    def calculate_break_even_price(self, entry_price: float, is_long: bool) -> float:
        """Calculate break-even price (mirrors app.py logic)."""
        total_fees = self.taker_fee_rate + self.maker_fee_rate
        if is_long:
            return entry_price * (1 + total_fees)
        else:
            return entry_price * (1 - total_fees)
    
    def calculate_target_profit_price(self, break_even_price: float, is_long: bool) -> float:
        """Calculate target profit price (mirrors app.py logic)."""
        if is_long:
            return break_even_price * (1 + self.target_profit_percent)
        else:
            return break_even_price * (1 - self.target_profit_percent)
    
    def calculate_stop_loss_threshold(self, entry_price: float, is_long: bool) -> float:
        """Calculate stop-loss threshold (mirrors app.py logic)."""
        if is_long:
            stop_loss_pct = self.stop_loss_percent_long
            return entry_price * (1 - stop_loss_pct)
        else:
            stop_loss_pct = self.stop_loss_percent_short
            return entry_price * (1 + stop_loss_pct)
    
    def open_long_position(self, price: float, timestamp: datetime):
        """Open a long position (mirrors execute_buy_order)."""
        capital_to_use = self.capital * self.capital_allocation_percent
        quantity = capital_to_use / price
        
        # Round to 0.001 precision (mirrors app.py)
        quantity = round(quantity, 3)
        
        if quantity <= 0:
            return False
        
        self.in_position = True
        self.position_side = "long"
        self.entry_price = price
        self.position_quantity = quantity
        self.entry_time = timestamp
        self.break_even_price = self.calculate_break_even_price(price, is_long=True)
        self.target_profit_price = self.calculate_target_profit_price(self.break_even_price, is_long=True)
        self.highest_price = price
        self.lowest_price = price
        
        return True
    
    def open_short_position(self, price: float, timestamp: datetime):
        """Open a short position (mirrors execute_short_order)."""
        capital_to_use = self.capital * self.capital_allocation_percent
        quantity = capital_to_use / price
        
        # Round to 0.001 precision
        quantity = round(quantity, 3)
        
        if quantity <= 0:
            return False
        
        self.in_position = True
        self.position_side = "short"
        self.entry_price = price
        self.position_quantity = quantity
        self.entry_time = timestamp
        self.break_even_price = self.calculate_break_even_price(price, is_long=False)
        self.target_profit_price = self.calculate_target_profit_price(self.break_even_price, is_long=False)
        self.highest_price = price
        self.lowest_price = price
        
        return True
    
    def close_position(self, exit_price: float, timestamp: datetime, exit_reason: str) -> Trade:
        """Close the current position and calculate PnL (mirrors execute_sell_order/execute_close_short_order)."""
        if not self.in_position:
            return None
        
        is_long = self.position_side == "long"
        
        # Calculate PnL (mirrors app.py logic)
        if is_long:
            # Long: buy at entry, sell at exit
            buy_cost = self.entry_price * self.position_quantity * (1 + self.taker_fee_rate)
            sell_revenue = exit_price * self.position_quantity * (1 - self.maker_fee_rate)
            pnl = sell_revenue - buy_cost
        else:
            # Short: sell at entry, buy at exit
            sell_revenue = self.entry_price * self.position_quantity * (1 - self.taker_fee_rate)
            buy_cost = exit_price * self.position_quantity * (1 + self.maker_fee_rate)
            pnl = sell_revenue - buy_cost
        
        # Calculate PnL percentage
        notional = self.entry_price * self.position_quantity
        pnl_percent = (pnl / notional) * 100 if notional > 0 else 0.0
        
        # Calculate duration
        duration = (timestamp - self.entry_time).total_seconds() if self.entry_time else None
        
        # Create trade record
        trade = Trade(
            entry_time=self.entry_time,
            exit_time=timestamp,
            entry_price=self.entry_price,
            exit_price=exit_price,
            position_side=self.position_side,
            quantity=self.position_quantity,
            pnl=pnl,
            pnl_percent=pnl_percent,
            exit_reason=exit_reason,
            duration_seconds=duration,
            highest_price=self.highest_price,
            lowest_price=self.lowest_price,
            break_even_price=self.break_even_price,
            target_profit_price=self.target_profit_price
        )
        
        # Update capital
        self.capital += pnl
        self.equity_curve.append(self.capital)
        
        # Reset position state
        self.in_position = False
        self.position_side = None
        self.entry_price = None
        self.position_quantity = None
        self.entry_time = None
        self.break_even_price = None
        self.target_profit_price = None
        self.highest_price = None
        self.lowest_price = None
        self.last_trade_timestamp = timestamp
        
        return trade
    
    def check_stop_loss(self, current_price: float) -> bool:
        """Check if stop-loss should trigger (mirrors monitor_position logic)."""
        if not self.in_position:
            return False
        
        is_long = self.position_side == "long"
        stop_loss_threshold = self.calculate_stop_loss_threshold(self.entry_price, is_long)
        
        if is_long:
            return current_price <= stop_loss_threshold
        else:
            return current_price >= stop_loss_threshold
    
    def check_profit_target(self, current_price: float) -> bool:
        """Check if profit target should trigger (mirrors monitor_position logic)."""
        if not self.in_position or self.target_profit_price is None:
            return False
        
        is_long = self.position_side == "long"
        
        if is_long:
            return current_price >= self.target_profit_price
        else:
            return current_price <= self.target_profit_price
    
    def update_price_tracking(self, current_price: float):
        """Update highest/lowest price tracking (mirrors monitor_position logic)."""
        if not self.in_position:
            return
        
        if self.highest_price is None or current_price > self.highest_price:
            self.highest_price = current_price
        
        if self.lowest_price is None or current_price < self.lowest_price:
            self.lowest_price = current_price
    
    def can_trade(self, timestamp: datetime) -> bool:
        """Check if cooldown period has elapsed (mirrors webhook cooldown logic)."""
        if self.last_trade_timestamp is None:
            return True
        
        time_since_last_trade = (timestamp - self.last_trade_timestamp).total_seconds()
        return time_since_last_trade >= self.cooldown_seconds
    
    def run(
        self,
        df: pd.DataFrame,
        atr_period: int = 3,
        multiplier: float = 6.0
    ) -> BacktestResults:
        """
        Run the backtest on historical data.
        
        Args:
            df: DataFrame with OHLCV data (must have timestamp index)
            atr_period: Supertrend ATR period
            multiplier: Supertrend multiplier
        
        Returns:
            BacktestResults object with all metrics
        """
        # Reset state
        self.capital = self.initial_capital
        self.in_position = False
        self.position_side = None
        self.entry_price = None
        self.position_quantity = None
        self.entry_time = None
        self.break_even_price = None
        self.target_profit_price = None
        self.highest_price = None
        self.lowest_price = None
        self.last_trade_timestamp = None
        self.trades = []
        self.equity_curve = [self.initial_capital]
        
        # Generate signals
        signals = generate_signals(df, atr_period, multiplier)
        
        # Process each candle
        for idx, row in df.iterrows():
            current_price = row['close']
            timestamp = idx if isinstance(idx, datetime) else pd.to_datetime(idx)
            
            # Update price tracking if in position
            if self.in_position:
                self.update_price_tracking(current_price)
                
                # Check stop-loss first (priority)
                if self.check_stop_loss(current_price):
                    trade = self.close_position(current_price, timestamp, "stop_loss")
                    if trade:
                        self.trades.append(trade)
                    continue
                
                # Check profit target
                if self.check_profit_target(current_price):
                    trade = self.close_position(current_price, timestamp, "profit_target")
                    if trade:
                        self.trades.append(trade)
                    continue
            
            # Check for new signals
            signal = signals.loc[idx] if idx in signals.index else 0
            
            if signal != 0 and self.can_trade(timestamp):
                if signal == 1:  # Buy signal
                    if not self.in_position:
                        # Open long position
                        self.open_long_position(current_price, timestamp)
                    elif self.position_side == "short":
                        # Close short and open long (inverted semantics from app.py)
                        trade = self.close_position(current_price, timestamp, "signal")
                        if trade:
                            self.trades.append(trade)
                        self.open_long_position(current_price, timestamp)
                
                elif signal == -1:  # Sell signal
                    if not self.in_position:
                        # Open short position
                        self.open_short_position(current_price, timestamp)
                    elif self.position_side == "long":
                        # Close long and open short (inverted semantics from app.py)
                        trade = self.close_position(current_price, timestamp, "signal")
                        if trade:
                            self.trades.append(trade)
                        self.open_short_position(current_price, timestamp)
            
            # Update equity curve
            if self.in_position:
                # Calculate current equity (unrealized PnL)
                is_long = self.position_side == "long"
                if is_long:
                    buy_cost = self.entry_price * self.position_quantity * (1 + self.taker_fee_rate)
                    current_value = current_price * self.position_quantity * (1 - self.maker_fee_rate)
                    unrealized_pnl = current_value - buy_cost
                else:
                    sell_revenue = self.entry_price * self.position_quantity * (1 - self.taker_fee_rate)
                    current_value = current_price * self.position_quantity * (1 + self.maker_fee_rate)
                    unrealized_pnl = sell_revenue - current_value
                
                current_equity = self.capital + unrealized_pnl
            else:
                current_equity = self.capital
            
            self.equity_curve.append(current_equity)
        
        # Close any open position at the end
        if self.in_position:
            last_price = df.iloc[-1]['close']
            last_timestamp = df.index[-1]
            if isinstance(last_timestamp, datetime):
                timestamp = last_timestamp
            else:
                timestamp = pd.to_datetime(last_timestamp)
            trade = self.close_position(last_price, timestamp, "end_of_data")
            if trade:
                self.trades.append(trade)
        
        # Calculate metrics
        return self._calculate_results()
    
    def _calculate_results(self) -> BacktestResults:
        """Calculate all performance metrics."""
        if not self.trades:
            return BacktestResults(
                total_pnl=0.0,
                total_pnl_percent=0.0,
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                win_rate=0.0,
                loss_rate=0.0,
                average_earnings_per_trade_percent=0.0,
                average_pnl_per_trade=0.0,
                sharpe_ratio=0.0,
                max_drawdown=0.0,
                trades=[],
                equity_curve=self.equity_curve,
                final_capital=self.capital
            )
        
        total_pnl = sum(trade.pnl for trade in self.trades)
        total_pnl_percent = (total_pnl / self.initial_capital) * 100
        
        winning_trades = [t for t in self.trades if t.pnl > 0]
        losing_trades = [t for t in self.trades if t.pnl <= 0]
        
        total_trades = len(self.trades)
        win_rate = (len(winning_trades) / total_trades) * 100 if total_trades > 0 else 0.0
        loss_rate = (len(losing_trades) / total_trades) * 100 if total_trades > 0 else 0.0
        
        # Average earnings per trade (% of capital used)
        capital_used_per_trade = self.initial_capital * self.capital_allocation_percent
        earnings_per_trade_percent = [
            (trade.pnl / capital_used_per_trade) * 100 for trade in self.trades
        ]
        average_earnings_per_trade_percent = np.mean(earnings_per_trade_percent) if earnings_per_trade_percent else 0.0
        
        # Average PnL per trade
        average_pnl_per_trade = total_pnl / total_trades if total_trades > 0 else 0.0
        
        # Sharpe ratio (using periodic returns)
        returns = [trade.pnl / self.initial_capital for trade in self.trades]
        sharpe_ratio = calculate_sharpe_ratio(returns)
        
        # Max drawdown
        max_drawdown = calculate_max_drawdown(self.equity_curve)
        
        return BacktestResults(
            total_pnl=total_pnl,
            total_pnl_percent=total_pnl_percent,
            total_trades=total_trades,
            winning_trades=len(winning_trades),
            losing_trades=len(losing_trades),
            win_rate=win_rate,
            loss_rate=loss_rate,
            average_earnings_per_trade_percent=average_earnings_per_trade_percent,
            average_pnl_per_trade=average_pnl_per_trade,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_drawdown,
            trades=self.trades,
            equity_curve=self.equity_curve,
            final_capital=self.capital
        )


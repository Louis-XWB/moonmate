"""
Backtest engine
Supports historical data backtesting and strategy evaluation
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
import numpy as np

from backend.data.models import Kline, Ticker, Order, OrderStatus, OrderSide, Position, Signal, SignalDirection
from backend.data.provider import MockDataProvider
from backend.strategy.base import BaseStrategy
from backend.strategy.momentum import MomentumStrategy
from backend.core.logger import get_logger

logger = get_logger("backtest")


class Trade(BaseModel):
    """Backtest trade record"""
    timestamp: datetime
    symbol: str
    side: str
    price: float
    size: float
    pnl: float = 0
    fee: float = 0
    reason: str = ""


class BacktestResult(BaseModel):
    """Backtest result"""
    symbol: str
    strategy: str
    start_time: datetime
    end_time: datetime
    initial_balance: float
    final_balance: float
    
    # ProfitIndicator
    total_return: float = 0
    total_return_pct: float = 0
    annualized_return: float = 0
    
    # Risk indicators
    max_drawdown: float = 0
    max_drawdown_pct: float = 0
    sharpe_ratio: float = 0
    sortino_ratio: float = 0
    calmar_ratio: float = 0
    
    # Trade statistics
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0
    avg_win: float = 0
    avg_loss: float = 0
    profit_factor: float = 0
    
    # Other indicators
    total_fees: float = 0
    avg_holding_period: float = 0  # hours
    
    # Detailed data
    trades: List[Trade] = Field(default_factory=list)
    equity_curve: List[float] = Field(default_factory=list)
    drawdown_curve: List[float] = Field(default_factory=list)


class BacktestEngine:
    """Backtest engine"""
    
    def __init__(
        self,
        initial_balance: float = 10000,
        fee_rate: float = 0.001,
        slippage: float = 0.0005
    ):
        self.initial_balance = initial_balance
        self.fee_rate = fee_rate
        self.slippage = slippage
        
        self.balance = initial_balance
        self.position: Optional[Position] = None
        self.trades: List[Trade] = []
        self.equity_curve: List[float] = []
    
    async def run(
        self,
        symbol: str,
        strategy: BaseStrategy,
        klines: List[Kline],
        order_size: float = 100
    ) -> BacktestResult:
        """RunningBacktest"""
        
        logger.info(f"Starting backtest: {symbol} with {strategy.name}")
        logger.info(f"Data range: {klines[0].open_time} to {klines[-1].close_time}")
        logger.info(f"Total bars: {len(klines)}")
        
        # Reset status
        self.balance = self.initial_balance
        self.position = None
        self.trades = []
        self.equity_curve = [self.initial_balance]
        
        # Need sufficient historical data
        lookback = 50
        
        for i in range(lookback, len(klines)):
            # Get historical data
            history = klines[max(0, i-lookback):i+1]
            current_kline = klines[i]
            
            # Create simulated ticker
            ticker = Ticker(
                symbol=symbol,
                last_price=current_kline.close,
                bid_price=current_kline.close * 0.9999,
                ask_price=current_kline.close * 1.0001,
                volume_24h=current_kline.volume * 24,
                change_24h=0,
                high_24h=current_kline.high,
                low_24h=current_kline.low,
                timestamp=current_kline.close_time
            )
            
            # UpdatePositionP&L
            if self.position:
                self.position.update_pnl(current_kline.close)
            
            # Generate signals
            signal = await strategy.run(
                symbol=symbol,
                ticker=ticker,
                klines=history,
                position=self.position
            )
            
            # Execute trades
            if signal.is_actionable:
                self._execute_signal(signal, current_kline, order_size)
            
            # CheckStop-loss / Take-profit
            if self.position:
                self._check_stop_loss_take_profit(current_kline)
            
            # Record equity
            equity = self.balance
            if self.position:
                equity += self.position.unrealized_pnl
            self.equity_curve.append(equity)
        
        # Close position
        if self.position:
            self._close_position(klines[-1], "BacktestEndClose position")
        
        # CalculateResult
        result = self._calculate_result(symbol, strategy.name, klines)
        
        logger.info(f"Backtest completed: Return={result.total_return_pct:.2f}%, "
                   f"MaxDD={result.max_drawdown_pct:.2f}%, "
                   f"Sharpe={result.sharpe_ratio:.2f}, "
                   f"WinRate={result.win_rate:.1%}")
        
        return result
    
    def _execute_signal(self, signal: Signal, kline: Kline, order_size: float):
        """ExecuteSignal"""
        price = kline.close
        
        if signal.direction == SignalDirection.LONG:
            if self.position and self.position.side == OrderSide.SELL:
                # Close short first
                self._close_position(kline, "Reverse position")
            
            if not self.position:
                # Open long
                self._open_position(OrderSide.BUY, price, order_size, kline.close_time, signal)
        
        elif signal.direction == SignalDirection.SHORT:
            if self.position and self.position.side == OrderSide.BUY:
                # Close long first
                self._close_position(kline, "Reverse position")
            
            if not self.position:
                # Open short
                self._open_position(OrderSide.SELL, price, order_size, kline.close_time, signal)
        
        elif signal.direction == SignalDirection.CLOSE:
            if self.position:
                self._close_position(kline, signal.reason)
    
    def _open_position(
        self,
        side: OrderSide,
        price: float,
        size: float,
        timestamp: datetime,
        signal: Signal
    ):
        """Open position"""
        # Calculate actual fill price (including slippage)
        if side == OrderSide.BUY:
            fill_price = price * (1 + self.slippage)
        else:
            fill_price = price * (1 - self.slippage)
        
        # CalculateFee
        fee = size * self.fee_rate
        
        # Calculate available quantity
        actual_size = (size - fee) / fill_price
        
        # CreatePosition
        self.position = Position(
            symbol=signal.symbol,
            side=side,
            size=actual_size,
            entry_price=fill_price,
            current_price=fill_price,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
            opened_at=timestamp
        )
        
        # Deduct balance
        self.balance -= size
        
        # Record trade
        self.trades.append(Trade(
            timestamp=timestamp,
            symbol=signal.symbol,
            side="buy" if side == OrderSide.BUY else "sell",
            price=fill_price,
            size=actual_size,
            fee=fee,
            reason=signal.reason
        ))
        
        logger.debug(f"Opened {side.value} position: {actual_size:.4f} @ {fill_price:.2f}")
    
    def _close_position(self, kline: Kline, reason: str):
        """Close position"""
        if not self.position:
            return
        
        price = kline.close
        
        # Calculate actual fill price (including slippage)
        if self.position.side == OrderSide.BUY:
            fill_price = price * (1 - self.slippage)
        else:
            fill_price = price * (1 + self.slippage)
        
        # CalculateP&L
        if self.position.side == OrderSide.BUY:
            pnl = (fill_price - self.position.entry_price) * self.position.size
        else:
            pnl = (self.position.entry_price - fill_price) * self.position.size
        
        # CalculateFee
        fee = self.position.size * fill_price * self.fee_rate
        pnl -= fee
        
        # UpdateBalance
        self.balance += self.position.size * fill_price - fee
        
        # Record trade
        self.trades.append(Trade(
            timestamp=kline.close_time,
            symbol=self.position.symbol,
            side="sell" if self.position.side == OrderSide.BUY else "buy",
            price=fill_price,
            size=self.position.size,
            pnl=pnl,
            fee=fee,
            reason=reason
        ))
        
        logger.debug(f"Closed position: PnL={pnl:.2f}, Reason={reason}")
        
        self.position = None
    
    def _check_stop_loss_take_profit(self, kline: Kline):
        """CheckStop-loss / Take-profit"""
        if not self.position:
            return
        
        if self.position.side == OrderSide.BUY:
            # Long stop-loss
            if self.position.stop_loss and kline.low <= self.position.stop_loss:
                self._close_position(kline, f"Stop-loss triggered @ {self.position.stop_loss}")
                return
            # Long take-profit
            if self.position.take_profit and kline.high >= self.position.take_profit:
                self._close_position(kline, f"Take-profit triggered @ {self.position.take_profit}")
                return
        else:
            # Short stop-loss
            if self.position.stop_loss and kline.high >= self.position.stop_loss:
                self._close_position(kline, f"Stop-loss triggered @ {self.position.stop_loss}")
                return
            # Short take-profit
            if self.position.take_profit and kline.low <= self.position.take_profit:
                self._close_position(kline, f"Take-profit triggered @ {self.position.take_profit}")
                return
    
    def _calculate_result(
        self,
        symbol: str,
        strategy_name: str,
        klines: List[Kline]
    ) -> BacktestResult:
        """Calculate backtest results"""
        
        equity = np.array(self.equity_curve)
        
        # Basic profit
        total_return = self.balance - self.initial_balance
        total_return_pct = total_return / self.initial_balance * 100
        
        # Annualized return
        days = (klines[-1].close_time - klines[0].open_time).days
        if days > 0:
            annualized_return = (1 + total_return / self.initial_balance) ** (365 / days) - 1
        else:
            annualized_return = 0
        
        # MaximumDrawdown
        peak = np.maximum.accumulate(equity)
        drawdown = (peak - equity) / peak * 100
        max_drawdown_pct = np.max(drawdown)
        max_drawdown = np.max(peak - equity)
        
        # Return rate series
        returns = np.diff(equity) / equity[:-1]
        
        # Sharpe ratio (assuming risk-free rate of 0)
        if len(returns) > 0 and np.std(returns) > 0:
            sharpe_ratio = np.mean(returns) / np.std(returns) * np.sqrt(252)
        else:
            sharpe_ratio = 0
        
        # Sortino ratio
        negative_returns = returns[returns < 0]
        if len(negative_returns) > 0:
            downside_std = np.std(negative_returns)
            if downside_std > 0:
                sortino_ratio = np.mean(returns) / downside_std * np.sqrt(252)
            else:
                sortino_ratio = 0
        else:
            sortino_ratio = sharpe_ratio
        
        # Calmar ratio
        if max_drawdown_pct > 0:
            calmar_ratio = annualized_return * 100 / max_drawdown_pct
        else:
            calmar_ratio = 0
        
        # Trade statistics
        pnl_trades = [t for t in self.trades if t.pnl != 0]
        winning_trades = [t for t in pnl_trades if t.pnl > 0]
        losing_trades = [t for t in pnl_trades if t.pnl < 0]
        
        total_trades = len(pnl_trades)
        win_count = len(winning_trades)
        loss_count = len(losing_trades)
        
        win_rate = win_count / total_trades if total_trades > 0 else 0
        avg_win = np.mean([t.pnl for t in winning_trades]) if winning_trades else 0
        avg_loss = np.mean([t.pnl for t in losing_trades]) if losing_trades else 0
        
        total_win = sum(t.pnl for t in winning_trades)
        total_loss = abs(sum(t.pnl for t in losing_trades))
        profit_factor = total_win / total_loss if total_loss > 0 else 0
        
        total_fees = sum(t.fee for t in self.trades)
        
        return BacktestResult(
            symbol=symbol,
            strategy=strategy_name,
            start_time=klines[0].open_time,
            end_time=klines[-1].close_time,
            initial_balance=self.initial_balance,
            final_balance=self.balance,
            total_return=total_return,
            total_return_pct=total_return_pct,
            annualized_return=annualized_return * 100,
            max_drawdown=max_drawdown,
            max_drawdown_pct=max_drawdown_pct,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            calmar_ratio=calmar_ratio,
            total_trades=total_trades,
            winning_trades=win_count,
            losing_trades=loss_count,
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
            profit_factor=profit_factor,
            total_fees=total_fees,
            trades=self.trades,
            equity_curve=self.equity_curve,
            drawdown_curve=drawdown.tolist()
        )

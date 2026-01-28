"""
回测引擎
支持历史数据回测和策略评估
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
    """回测交易记录"""
    timestamp: datetime
    symbol: str
    side: str
    price: float
    size: float
    pnl: float = 0
    fee: float = 0
    reason: str = ""


class BacktestResult(BaseModel):
    """回测结果"""
    symbol: str
    strategy: str
    start_time: datetime
    end_time: datetime
    initial_balance: float
    final_balance: float
    
    # 收益指标
    total_return: float = 0
    total_return_pct: float = 0
    annualized_return: float = 0
    
    # 风险指标
    max_drawdown: float = 0
    max_drawdown_pct: float = 0
    sharpe_ratio: float = 0
    sortino_ratio: float = 0
    calmar_ratio: float = 0
    
    # 交易统计
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0
    avg_win: float = 0
    avg_loss: float = 0
    profit_factor: float = 0
    
    # 其他指标
    total_fees: float = 0
    avg_holding_period: float = 0  # 小时
    
    # 详细数据
    trades: List[Trade] = Field(default_factory=list)
    equity_curve: List[float] = Field(default_factory=list)
    drawdown_curve: List[float] = Field(default_factory=list)


class BacktestEngine:
    """回测引擎"""
    
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
        """运行回测"""
        
        logger.info(f"Starting backtest: {symbol} with {strategy.name}")
        logger.info(f"Data range: {klines[0].open_time} to {klines[-1].close_time}")
        logger.info(f"Total bars: {len(klines)}")
        
        # 重置状态
        self.balance = self.initial_balance
        self.position = None
        self.trades = []
        self.equity_curve = [self.initial_balance]
        
        # 需要足够的历史数据
        lookback = 50
        
        for i in range(lookback, len(klines)):
            # 获取历史数据
            history = klines[max(0, i-lookback):i+1]
            current_kline = klines[i]
            
            # 创建模拟Ticker
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
            
            # 更新持仓盈亏
            if self.position:
                self.position.update_pnl(current_kline.close)
            
            # 生成信号
            signal = await strategy.run(
                symbol=symbol,
                ticker=ticker,
                klines=history,
                position=self.position
            )
            
            # 执行交易
            if signal.is_actionable:
                self._execute_signal(signal, current_kline, order_size)
            
            # 检查止损止盈
            if self.position:
                self._check_stop_loss_take_profit(current_kline)
            
            # 记录权益
            equity = self.balance
            if self.position:
                equity += self.position.unrealized_pnl
            self.equity_curve.append(equity)
        
        # 平仓
        if self.position:
            self._close_position(klines[-1], "回测结束平仓")
        
        # 计算结果
        result = self._calculate_result(symbol, strategy.name, klines)
        
        logger.info(f"Backtest completed: Return={result.total_return_pct:.2f}%, "
                   f"MaxDD={result.max_drawdown_pct:.2f}%, "
                   f"Sharpe={result.sharpe_ratio:.2f}, "
                   f"WinRate={result.win_rate:.1%}")
        
        return result
    
    def _execute_signal(self, signal: Signal, kline: Kline, order_size: float):
        """执行信号"""
        price = kline.close
        
        if signal.direction == SignalDirection.LONG:
            if self.position and self.position.side == OrderSide.SELL:
                # 先平空
                self._close_position(kline, "反向开仓")
            
            if not self.position:
                # 开多
                self._open_position(OrderSide.BUY, price, order_size, kline.close_time, signal)
        
        elif signal.direction == SignalDirection.SHORT:
            if self.position and self.position.side == OrderSide.BUY:
                # 先平多
                self._close_position(kline, "反向开仓")
            
            if not self.position:
                # 开空
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
        """开仓"""
        # 计算实际成交价（含滑点）
        if side == OrderSide.BUY:
            fill_price = price * (1 + self.slippage)
        else:
            fill_price = price * (1 - self.slippage)
        
        # 计算手续费
        fee = size * self.fee_rate
        
        # 计算可买数量
        actual_size = (size - fee) / fill_price
        
        # 创建持仓
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
        
        # 扣除余额
        self.balance -= size
        
        # 记录交易
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
        """平仓"""
        if not self.position:
            return
        
        price = kline.close
        
        # 计算实际成交价（含滑点）
        if self.position.side == OrderSide.BUY:
            fill_price = price * (1 - self.slippage)
        else:
            fill_price = price * (1 + self.slippage)
        
        # 计算盈亏
        if self.position.side == OrderSide.BUY:
            pnl = (fill_price - self.position.entry_price) * self.position.size
        else:
            pnl = (self.position.entry_price - fill_price) * self.position.size
        
        # 计算手续费
        fee = self.position.size * fill_price * self.fee_rate
        pnl -= fee
        
        # 更新余额
        self.balance += self.position.size * fill_price - fee
        
        # 记录交易
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
        """检查止损止盈"""
        if not self.position:
            return
        
        if self.position.side == OrderSide.BUY:
            # 多头止损
            if self.position.stop_loss and kline.low <= self.position.stop_loss:
                self._close_position(kline, f"止损触发 @ {self.position.stop_loss}")
                return
            # 多头止盈
            if self.position.take_profit and kline.high >= self.position.take_profit:
                self._close_position(kline, f"止盈触发 @ {self.position.take_profit}")
                return
        else:
            # 空头止损
            if self.position.stop_loss and kline.high >= self.position.stop_loss:
                self._close_position(kline, f"止损触发 @ {self.position.stop_loss}")
                return
            # 空头止盈
            if self.position.take_profit and kline.low <= self.position.take_profit:
                self._close_position(kline, f"止盈触发 @ {self.position.take_profit}")
                return
    
    def _calculate_result(
        self,
        symbol: str,
        strategy_name: str,
        klines: List[Kline]
    ) -> BacktestResult:
        """计算回测结果"""
        
        equity = np.array(self.equity_curve)
        
        # 基本收益
        total_return = self.balance - self.initial_balance
        total_return_pct = total_return / self.initial_balance * 100
        
        # 年化收益
        days = (klines[-1].close_time - klines[0].open_time).days
        if days > 0:
            annualized_return = (1 + total_return / self.initial_balance) ** (365 / days) - 1
        else:
            annualized_return = 0
        
        # 最大回撤
        peak = np.maximum.accumulate(equity)
        drawdown = (peak - equity) / peak * 100
        max_drawdown_pct = np.max(drawdown)
        max_drawdown = np.max(peak - equity)
        
        # 收益率序列
        returns = np.diff(equity) / equity[:-1]
        
        # Sharpe比率（假设无风险利率为0）
        if len(returns) > 0 and np.std(returns) > 0:
            sharpe_ratio = np.mean(returns) / np.std(returns) * np.sqrt(252)
        else:
            sharpe_ratio = 0
        
        # Sortino比率
        negative_returns = returns[returns < 0]
        if len(negative_returns) > 0:
            downside_std = np.std(negative_returns)
            if downside_std > 0:
                sortino_ratio = np.mean(returns) / downside_std * np.sqrt(252)
            else:
                sortino_ratio = 0
        else:
            sortino_ratio = sharpe_ratio
        
        # Calmar比率
        if max_drawdown_pct > 0:
            calmar_ratio = annualized_return * 100 / max_drawdown_pct
        else:
            calmar_ratio = 0
        
        # 交易统计
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

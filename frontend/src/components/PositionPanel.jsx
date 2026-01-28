import React from 'react'
import { TrendingUp, TrendingDown, X } from 'lucide-react'

function PositionPanel({ status }) {
  const positions = status?.positions || []
  
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold">持仓管理</h2>
        <div className="text-sm text-slate-400">
          共 {positions.length} 个持仓
        </div>
      </div>

      {positions.length === 0 ? (
        <div className="card text-center py-12">
          <p className="text-slate-400">暂无持仓</p>
          <p className="text-sm text-slate-500 mt-2">当策略产生交易信号时，持仓将显示在这里</p>
        </div>
      ) : (
        <div className="card overflow-hidden">
          <div className="table-container">
            <table className="data-table">
              <thead>
                <tr>
                  <th>交易对</th>
                  <th>方向</th>
                  <th>数量</th>
                  <th>开仓价</th>
                  <th>当前价</th>
                  <th>未实现盈亏</th>
                  <th>盈亏比例</th>
                  <th>止损价</th>
                  <th>止盈价</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {positions.map((pos, index) => (
                  <tr key={index}>
                    <td className="font-medium">{pos.symbol}</td>
                    <td>
                      <span className={`flex items-center space-x-1 ${pos.side === 'buy' ? 'text-emerald-400' : 'text-red-400'}`}>
                        {pos.side === 'buy' ? (
                          <><TrendingUp className="w-4 h-4" /><span>多</span></>
                        ) : (
                          <><TrendingDown className="w-4 h-4" /><span>空</span></>
                        )}
                      </span>
                    </td>
                    <td>{pos.size?.toFixed(4)}</td>
                    <td>${pos.entry_price?.toLocaleString()}</td>
                    <td>${pos.current_price?.toLocaleString()}</td>
                    <td className={pos.unrealized_pnl >= 0 ? 'text-emerald-400' : 'text-red-400'}>
                      ${pos.unrealized_pnl?.toFixed(2)}
                    </td>
                    <td className={pos.pnl_pct >= 0 ? 'text-emerald-400' : 'text-red-400'}>
                      {pos.pnl_pct >= 0 ? '+' : ''}{pos.pnl_pct?.toFixed(2)}%
                    </td>
                    <td className="text-red-400">${pos.stop_loss?.toLocaleString() || '-'}</td>
                    <td className="text-emerald-400">${pos.take_profit?.toLocaleString() || '-'}</td>
                    <td>
                      <button className="p-1 hover:bg-slate-700 rounded">
                        <X className="w-4 h-4 text-slate-400" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* 持仓统计 */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="card">
          <p className="text-slate-400 text-sm">总持仓价值</p>
          <p className="text-2xl font-bold mt-1">
            ${positions.reduce((sum, p) => sum + (p.size * p.current_price), 0).toFixed(2)}
          </p>
        </div>
        <div className="card">
          <p className="text-slate-400 text-sm">未实现盈亏</p>
          <p className={`text-2xl font-bold mt-1 ${
            positions.reduce((sum, p) => sum + p.unrealized_pnl, 0) >= 0 
              ? 'text-emerald-400' 
              : 'text-red-400'
          }`}>
            ${positions.reduce((sum, p) => sum + p.unrealized_pnl, 0).toFixed(2)}
          </p>
        </div>
        <div className="card">
          <p className="text-slate-400 text-sm">已实现盈亏</p>
          <p className={`text-2xl font-bold mt-1 ${
            positions.reduce((sum, p) => sum + p.realized_pnl, 0) >= 0 
              ? 'text-emerald-400' 
              : 'text-red-400'
          }`}>
            ${positions.reduce((sum, p) => sum + p.realized_pnl, 0).toFixed(2)}
          </p>
        </div>
      </div>
    </div>
  )
}

export default PositionPanel

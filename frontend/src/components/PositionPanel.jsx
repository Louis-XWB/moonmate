import React from 'react'
import { TrendingUp, TrendingDown, X } from 'lucide-react'

function PositionPanel({ status }) {
  const positions = status?.positions || []
  
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold">Position Management</h2>
        <div className="text-sm text-slate-400">
          Total {positions.length} positions
        </div>
      </div>

      {positions.length === 0 ? (
        <div className="card text-center py-12">
          <p className="text-slate-400">No positions</p>
          <p className="text-sm text-slate-500 mt-2">When strategy generates a trading signal, positions will appear here</p>
        </div>
      ) : (
        <div className="card overflow-hidden">
          <div className="table-container">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Trading pair</th>
                  <th>Direction</th>
                  <th>Quantity</th>
                  <th>Entry Price</th>
                  <th>Current Price</th>
                  <th>Unrealized P&L</th>
                  <th>Profit Ratio</th>
                  <th>Stop-loss Price</th>
                  <th>Take-profit Price</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {positions.map((pos, index) => (
                  <tr key={index}>
                    <td className="font-medium">{pos.symbol}</td>
                    <td>
                      <span className={`flex items-center space-x-1 ${pos.side === 'buy' ? 'text-emerald-400' : 'text-red-400'}`}>
                        {pos.side === 'buy' ? (
                          <><TrendingUp className="w-4 h-4" /><span>Long</span></>
                        ) : (
                          <><TrendingDown className="w-4 h-4" /><span>Short</span></>
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

      {/* PositionStatistics */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="card">
          <p className="text-slate-400 text-sm">Total Position Value</p>
          <p className="text-2xl font-bold mt-1">
            ${positions.reduce((sum, p) => sum + (p.size * p.current_price), 0).toFixed(2)}
          </p>
        </div>
        <div className="card">
          <p className="text-slate-400 text-sm">Unrealized P&L</p>
          <p className={`text-2xl font-bold mt-1 ${
            positions.reduce((sum, p) => sum + p.unrealized_pnl, 0) >= 0 
              ? 'text-emerald-400' 
              : 'text-red-400'
          }`}>
            ${positions.reduce((sum, p) => sum + p.unrealized_pnl, 0).toFixed(2)}
          </p>
        </div>
        <div className="card">
          <p className="text-slate-400 text-sm">Realized P&L</p>
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

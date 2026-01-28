import React, { useState } from 'react'
import { Play, BarChart3, TrendingUp, TrendingDown, Activity } from 'lucide-react'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, AreaChart, Area } from 'recharts'

const API_BASE = ''

function BacktestPanel() {
  const [config, setConfig] = useState({
    symbol: 'BTC/USDT',
    strategy: 'momentum',
    initial_balance: 10000,
    order_size: 100,
    bars: 500
  })
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const runBacktest = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${API_BASE}/api/backtest`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config)
      })
      if (res.ok) {
        const data = await res.json()
        setResult(data)
      } else {
        throw new Error('Backtest failed')
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  // 准备图表数据
  const equityData = result?.equity_curve?.map((value, index) => ({
    index,
    value: parseFloat(value).toFixed(2)
  })) || []

  const drawdownData = result?.drawdown_curve?.map((value, index) => ({
    index,
    value: parseFloat(value).toFixed(2)
  })) || []

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold">策略回测</h2>
      </div>

      {/* 回测配置 */}
      <div className="card">
        <h3 className="font-medium mb-4">回测配置</h3>
        <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
          <div>
            <label className="block text-slate-400 text-sm mb-1">交易对</label>
            <select
              value={config.symbol}
              onChange={(e) => setConfig({ ...config, symbol: e.target.value })}
              className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2"
            >
              <option value="BTC/USDT">BTC/USDT</option>
              <option value="ETH/USDT">ETH/USDT</option>
              <option value="SOL/USDT">SOL/USDT</option>
            </select>
          </div>
          <div>
            <label className="block text-slate-400 text-sm mb-1">策略</label>
            <select
              value={config.strategy}
              onChange={(e) => setConfig({ ...config, strategy: e.target.value })}
              className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2"
            >
              <option value="momentum">动量策略</option>
              <option value="reversal">反转策略</option>
            </select>
          </div>
          <div>
            <label className="block text-slate-400 text-sm mb-1">初始资金</label>
            <input
              type="number"
              value={config.initial_balance}
              onChange={(e) => setConfig({ ...config, initial_balance: parseFloat(e.target.value) })}
              className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2"
            />
          </div>
          <div>
            <label className="block text-slate-400 text-sm mb-1">单笔金额</label>
            <input
              type="number"
              value={config.order_size}
              onChange={(e) => setConfig({ ...config, order_size: parseFloat(e.target.value) })}
              className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2"
            />
          </div>
          <div>
            <label className="block text-slate-400 text-sm mb-1">K线数量</label>
            <input
              type="number"
              value={config.bars}
              onChange={(e) => setConfig({ ...config, bars: parseInt(e.target.value) })}
              className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2"
            />
          </div>
        </div>
        <div className="mt-4">
          <button
            onClick={runBacktest}
            disabled={loading}
            className="btn btn-primary flex items-center space-x-2"
          >
            <Play className="w-4 h-4" />
            <span>{loading ? '回测中...' : '运行回测'}</span>
          </button>
        </div>
        {error && (
          <div className="mt-4 p-3 bg-red-900/50 border border-red-700 rounded-lg text-red-200">
            {error}
          </div>
        )}
      </div>

      {/* 回测结果 */}
      {result && (
        <>
          {/* 核心指标 */}
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
            <div className="card">
              <p className="text-slate-400 text-sm">总收益</p>
              <p className={`text-xl font-bold ${result.total_return >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                ${result.total_return?.toFixed(2)}
              </p>
              <p className={`text-sm ${result.total_return_pct >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                {result.total_return_pct >= 0 ? '+' : ''}{result.total_return_pct?.toFixed(2)}%
              </p>
            </div>
            <div className="card">
              <p className="text-slate-400 text-sm">年化收益</p>
              <p className={`text-xl font-bold ${result.annualized_return >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                {result.annualized_return?.toFixed(2)}%
              </p>
            </div>
            <div className="card">
              <p className="text-slate-400 text-sm">最大回撤</p>
              <p className="text-xl font-bold text-amber-400">
                {result.max_drawdown_pct?.toFixed(2)}%
              </p>
            </div>
            <div className="card">
              <p className="text-slate-400 text-sm">Sharpe比率</p>
              <p className={`text-xl font-bold ${result.sharpe_ratio >= 1 ? 'text-emerald-400' : 'text-slate-300'}`}>
                {result.sharpe_ratio?.toFixed(2)}
              </p>
            </div>
            <div className="card">
              <p className="text-slate-400 text-sm">胜率</p>
              <p className={`text-xl font-bold ${result.win_rate >= 0.5 ? 'text-emerald-400' : 'text-red-400'}`}>
                {(result.win_rate * 100)?.toFixed(1)}%
              </p>
            </div>
            <div className="card">
              <p className="text-slate-400 text-sm">盈亏比</p>
              <p className={`text-xl font-bold ${result.profit_factor >= 1 ? 'text-emerald-400' : 'text-red-400'}`}>
                {result.profit_factor?.toFixed(2)}
              </p>
            </div>
          </div>

          {/* 收益曲线 */}
          <div className="card">
            <h3 className="font-medium mb-4">收益曲线</h3>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={equityData}>
                  <defs>
                    <linearGradient id="colorEquity" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#10b981" stopOpacity={0.3}/>
                      <stop offset="95%" stopColor="#10b981" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <XAxis 
                    dataKey="index" 
                    stroke="#64748b" 
                    fontSize={12}
                    tickLine={false}
                  />
                  <YAxis 
                    stroke="#64748b" 
                    fontSize={12}
                    tickLine={false}
                    tickFormatter={(value) => `$${(value/1000).toFixed(1)}k`}
                  />
                  <Tooltip 
                    contentStyle={{ 
                      backgroundColor: '#1e293b', 
                      border: '1px solid #334155',
                      borderRadius: '8px'
                    }}
                    formatter={(value) => [`$${parseFloat(value).toLocaleString()}`, '权益']}
                  />
                  <Area 
                    type="monotone" 
                    dataKey="value" 
                    stroke="#10b981" 
                    fillOpacity={1}
                    fill="url(#colorEquity)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* 回撤曲线 */}
          <div className="card">
            <h3 className="font-medium mb-4">回撤曲线</h3>
            <div className="h-48">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={drawdownData}>
                  <defs>
                    <linearGradient id="colorDrawdown" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#ef4444" stopOpacity={0.3}/>
                      <stop offset="95%" stopColor="#ef4444" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <XAxis 
                    dataKey="index" 
                    stroke="#64748b" 
                    fontSize={12}
                    tickLine={false}
                  />
                  <YAxis 
                    stroke="#64748b" 
                    fontSize={12}
                    tickLine={false}
                    tickFormatter={(value) => `${value}%`}
                  />
                  <Tooltip 
                    contentStyle={{ 
                      backgroundColor: '#1e293b', 
                      border: '1px solid #334155',
                      borderRadius: '8px'
                    }}
                    formatter={(value) => [`${parseFloat(value).toFixed(2)}%`, '回撤']}
                  />
                  <Area 
                    type="monotone" 
                    dataKey="value" 
                    stroke="#ef4444" 
                    fillOpacity={1}
                    fill="url(#colorDrawdown)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* 详细统计 */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="card">
              <h3 className="font-medium mb-4">交易统计</h3>
              <div className="space-y-3">
                <div className="flex justify-between">
                  <span className="text-slate-400">总交易次数</span>
                  <span className="font-medium">{result.total_trades}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">盈利交易</span>
                  <span className="font-medium text-emerald-400">{result.winning_trades}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">亏损交易</span>
                  <span className="font-medium text-red-400">{result.losing_trades}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">平均盈利</span>
                  <span className="font-medium text-emerald-400">${result.avg_win?.toFixed(2)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">平均亏损</span>
                  <span className="font-medium text-red-400">${result.avg_loss?.toFixed(2)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">总手续费</span>
                  <span className="font-medium text-amber-400">${result.total_fees?.toFixed(2)}</span>
                </div>
              </div>
            </div>

            <div className="card">
              <h3 className="font-medium mb-4">风险指标</h3>
              <div className="space-y-3">
                <div className="flex justify-between">
                  <span className="text-slate-400">Sharpe比率</span>
                  <span className="font-medium">{result.sharpe_ratio?.toFixed(2)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Sortino比率</span>
                  <span className="font-medium">{result.sortino_ratio?.toFixed(2)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Calmar比率</span>
                  <span className="font-medium">{result.calmar_ratio?.toFixed(2)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">最大回撤金额</span>
                  <span className="font-medium text-red-400">${result.max_drawdown?.toFixed(2)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">初始资金</span>
                  <span className="font-medium">${result.initial_balance?.toLocaleString()}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">最终资金</span>
                  <span className="font-medium">${result.final_balance?.toFixed(2)}</span>
                </div>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  )
}

export default BacktestPanel

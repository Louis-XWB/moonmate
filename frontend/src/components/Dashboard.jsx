import React from 'react'
import {
  TrendingUp, TrendingDown, DollarSign,
  Activity, Target, AlertCircle, CheckCircle
} from 'lucide-react'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, AreaChart, Area } from 'recharts'

function StatCard({ title, value, change, icon: Icon, color = 'primary' }) {
  const colorClasses = {
    primary: 'bg-primary-600',
    success: 'bg-emerald-600',
    danger: 'bg-red-600',
    warning: 'bg-amber-600',
  }

  return (
    <div className="card">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-slate-400 text-sm">{title}</p>
          <p className="text-2xl font-bold mt-1">{value}</p>
          {change !== undefined && (
            <p className={`text-sm mt-1 ${change >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
              {change >= 0 ? '+' : ''}{change}%
            </p>
          )}
        </div>
        <div className={`p-2 rounded-lg ${colorClasses[color]}`}>
          <Icon className="w-5 h-5 text-white" />
        </div>
      </div>
    </div>
  )
}

function SignalIndicator({ signal }) {
  if (!signal) {
    return (
      <div className="card">
        <h3 className="text-slate-400 text-sm mb-2">Current Signal</h3>
        <div className="text-center py-4 text-slate-500">
          No signal available
        </div>
      </div>
    )
  }

  const directionColors = {
    long: 'text-emerald-400 bg-emerald-400/10',
    short: 'text-red-400 bg-red-400/10',
    neutral: 'text-slate-400 bg-slate-400/10',
    close: 'text-amber-400 bg-amber-400/10',
  }

  const directionLabels = {
    long: 'Long',
    short: 'Short',
    neutral: 'Hold',
    close: 'Close',
  }

  return (
    <div className="card">
      <h3 className="text-slate-400 text-sm mb-3">Current Signal</h3>
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-slate-400">Direction</span>
          <span className={`px-3 py-1 rounded-full text-sm font-medium ${directionColors[signal.direction]}`}>
            {directionLabels[signal.direction] || signal.direction}
          </span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-slate-400">Strength</span>
          <div className="flex items-center space-x-2">
            <div className="w-24 h-2 bg-slate-700 rounded-full overflow-hidden">
              <div
                className="h-full bg-primary-500 rounded-full"
                style={{ width: `${signal.strength * 100}%` }}
              />
            </div>
            <span className="text-sm">{(signal.strength * 100).toFixed(0)}%</span>
          </div>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-slate-400">Confidence</span>
          <span className="text-sm">{(signal.confidence * 100).toFixed(0)}%</span>
        </div>
        {signal.reason && (
          <div className="pt-2 border-t border-slate-700">
            <p className="text-xs text-slate-400">{signal.reason}</p>
          </div>
        )}
      </div>
    </div>
  )
}

function Dashboard({ status, ticker, signal, isRunning }) {
  // Simulated equity curve data
  const equityData = React.useMemo(() => {
    const data = []
    let value = 10000
    for (let i = 0; i < 24; i++) {
      value = value * (1 + (Math.random() - 0.48) * 0.02)
      data.push({
        time: `${i}:00`,
        value: value.toFixed(2)
      })
    }
    return data
  }, [])

  const stats = status?.statistics || {}
  const riskState = status?.risk_state || {}

  return (
    <div className="space-y-6">
      {/* Stats cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Account Balance"
          value={`$${(10000 + (stats.total_pnl || 0)).toLocaleString(undefined, {minimumFractionDigits: 2})}`}
          change={((stats.total_pnl || 0) / 100).toFixed(2)}
          icon={DollarSign}
          color="primary"
        />
        <StatCard
          title="Total PnL"
          value={`$${(stats.total_pnl || 0).toFixed(2)}`}
          icon={stats.total_pnl >= 0 ? TrendingUp : TrendingDown}
          color={stats.total_pnl >= 0 ? 'success' : 'danger'}
        />
        <StatCard
          title="Active Positions"
          value={stats.active_positions || 0}
          icon={Activity}
          color="warning"
        />
        <StatCard
          title="Filled Orders"
          value={stats.filled_orders || 0}
          icon={Target}
          color="primary"
        />
      </div>

      {/* Main content area */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Equity curve */}
        <div className="lg:col-span-2 card">
          <h3 className="text-slate-400 text-sm mb-4">Equity Curve</h3>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={equityData}>
                <defs>
                  <linearGradient id="colorValue" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#0ea5e9" stopOpacity={0.3}/>
                    <stop offset="95%" stopColor="#0ea5e9" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <XAxis
                  dataKey="time"
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
                  labelStyle={{ color: '#94a3b8' }}
                />
                <Area
                  type="monotone"
                  dataKey="value"
                  stroke="#0ea5e9"
                  fillOpacity={1}
                  fill="url(#colorValue)"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Signal indicator */}
        <SignalIndicator signal={signal} />
      </div>

      {/* Market data and risk status */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Live market data */}
        <div className="card">
          <h3 className="text-slate-400 text-sm mb-4">Live Market Data</h3>
          {ticker ? (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-2xl font-bold">
                  ${ticker.last_price?.toLocaleString(undefined, {minimumFractionDigits: 2})}
                </span>
                <span className={`text-lg ${ticker.change_24h >= 0 ? 'price-up' : 'price-down'}`}>
                  {ticker.change_24h >= 0 ? '+' : ''}{ticker.change_24h?.toFixed(2)}%
                </span>
              </div>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-slate-400">24h High</span>
                  <p className="font-medium">${ticker.high_24h?.toLocaleString()}</p>
                </div>
                <div>
                  <span className="text-slate-400">24h Low</span>
                  <p className="font-medium">${ticker.low_24h?.toLocaleString()}</p>
                </div>
                <div>
                  <span className="text-slate-400">24h Volume</span>
                  <p className="font-medium">{ticker.volume_24h?.toLocaleString()}</p>
                </div>
                <div>
                  <span className="text-slate-400">Bid-Ask Spread</span>
                  <p className="font-medium">{ticker.spread?.toFixed(4)}%</p>
                </div>
              </div>
            </div>
          ) : (
            <div className="text-center py-8 text-slate-500">
              Waiting for market data...
            </div>
          )}
        </div>

        {/* Risk control status */}
        <div className="card">
          <h3 className="text-slate-400 text-sm mb-4">Risk Control Status</h3>
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-slate-400">Trading Status</span>
              <span className={`flex items-center space-x-1 ${riskState.is_trading_allowed ? 'text-emerald-400' : 'text-red-400'}`}>
                {riskState.is_trading_allowed ? (
                  <><CheckCircle className="w-4 h-4" /><span>Trading Allowed</span></>
                ) : (
                  <><AlertCircle className="w-4 h-4" /><span>Trading Suspended</span></>
                )}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-slate-400">Circuit Breaker</span>
              <span className={riskState.circuit_breaker_active ? 'text-red-400' : 'text-emerald-400'}>
                {riskState.circuit_breaker_active ? 'Triggered' : 'Normal'}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-slate-400">Daily PnL</span>
              <span className={riskState.daily_pnl >= 0 ? 'text-emerald-400' : 'text-red-400'}>
                ${riskState.daily_pnl?.toFixed(2) || '0.00'}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-slate-400">Current Drawdown</span>
              <span className={riskState.current_drawdown > 5 ? 'text-amber-400' : 'text-slate-300'}>
                {riskState.current_drawdown?.toFixed(2) || '0.00'}%
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-slate-400">Consecutive Losses</span>
              <span className={riskState.consecutive_losses > 3 ? 'text-amber-400' : 'text-slate-300'}>
                {riskState.consecutive_losses || 0}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default Dashboard

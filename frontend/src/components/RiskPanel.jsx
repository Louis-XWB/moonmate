import React, { useState, useEffect } from 'react'
import { Shield, AlertTriangle, CheckCircle, XCircle, RefreshCw, RotateCcw } from 'lucide-react'

const API_BASE = ''

function RiskPanel({ status }) {
  const [riskData, setRiskData] = useState(null)
  const [loading, setLoading] = useState(false)

  const fetchRiskStatus = async () => {
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/api/risk`)
      if (res.ok) {
        const data = await res.json()
        setRiskData(data)
      }
    } catch (err) {
      console.error('Failed to fetch risk status:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleResetRisk = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/risk/reset`, { method: 'POST' })
      if (res.ok) {
        fetchRiskStatus()
      }
    } catch (err) {
      console.error('Failed to reset risk:', err)
    }
  }

  useEffect(() => {
    fetchRiskStatus()
    const interval = setInterval(fetchRiskStatus, 10000)
    return () => clearInterval(interval)
  }, [])

  const riskState = riskData?.state || status?.risk_state || {}
  const rules = riskData?.rules || []

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold">Risk controlStatus</h2>
        <div className="flex items-center space-x-2">
          <button 
            onClick={handleResetRisk}
            className="btn btn-secondary flex items-center space-x-2"
          >
            <RotateCcw className="w-4 h-4" />
            <span>Reset Risk Controls</span>
          </button>
          <button 
            onClick={fetchRiskStatus}
            className="btn btn-secondary"
            disabled={loading}
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Risk Control Status Overview */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className={`card border-2 ${riskState.is_trading_allowed ? 'border-emerald-500' : 'border-red-500'}`}>
          <div className="flex items-center space-x-3">
            {riskState.is_trading_allowed ? (
              <CheckCircle className="w-8 h-8 text-emerald-500" />
            ) : (
              <XCircle className="w-8 h-8 text-red-500" />
            )}
            <div>
              <p className="text-slate-400 text-sm">Trading Status</p>
              <p className={`text-lg font-bold ${riskState.is_trading_allowed ? 'text-emerald-400' : 'text-red-400'}`}>
                {riskState.is_trading_allowed ? 'Trading allowed' : 'Trading prohibited'}
              </p>
            </div>
          </div>
        </div>

        <div className={`card border-2 ${!riskState.circuit_breaker_active ? 'border-emerald-500' : 'border-red-500'}`}>
          <div className="flex items-center space-x-3">
            {!riskState.circuit_breaker_active ? (
              <Shield className="w-8 h-8 text-emerald-500" />
            ) : (
              <AlertTriangle className="w-8 h-8 text-red-500" />
            )}
            <div>
              <p className="text-slate-400 text-sm">Circuit breakerStatus</p>
              <p className={`text-lg font-bold ${!riskState.circuit_breaker_active ? 'text-emerald-400' : 'text-red-400'}`}>
                {riskState.circuit_breaker_active ? 'Triggered' : 'Normal'}
              </p>
            </div>
          </div>
        </div>

        <div className="card border-2 border-slate-600">
          <div className="flex items-center space-x-3">
            <Shield className="w-8 h-8 text-primary-500" />
            <div>
              <p className="text-slate-400 text-sm">Cooldown Period</p>
              <p className="text-lg font-bold">
                {riskState.cooldown_until ? 'Cooling Down' : 'None'}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Risk controlIndicator */}
      <div className="card">
        <h3 className="font-medium mb-4">Risk controlIndicator</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <div>
            <p className="text-slate-400 text-sm">Today's P&L</p>
            <p className={`text-2xl font-bold ${riskState.daily_pnl >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
              ${riskState.daily_pnl?.toFixed(2) || '0.00'}
            </p>
            <div className="mt-2">
              <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
                <div 
                  className={`h-full ${riskState.daily_pnl >= 0 ? 'bg-emerald-500' : 'bg-red-500'}`}
                  style={{ width: `${Math.min(100, Math.abs(riskState.daily_pnl || 0))}%` }}
                />
              </div>
              <p className="text-xs text-slate-400 mt-1">Daily loss limit: $100</p>
            </div>
          </div>

          <div>
            <p className="text-slate-400 text-sm">Current drawdown </p>
            <p className={`text-2xl font-bold ${riskState.current_drawdown > 5 ? 'text-amber-400' : 'text-slate-300'}`}>
              {riskState.current_drawdown?.toFixed(2) || '0.00'}%
            </p>
            <div className="mt-2">
              <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
                <div 
                  className={`h-full ${riskState.current_drawdown > 5 ? 'bg-amber-500' : 'bg-primary-500'}`}
                  style={{ width: `${Math.min(100, (riskState.current_drawdown || 0) * 10)}%` }}
                />
              </div>
              <p className="text-xs text-slate-400 mt-1">Maximum drawdown limit: 10%</p>
            </div>
          </div>

          <div>
            <p className="text-slate-400 text-sm">Consecutive losses </p>
            <p className={`text-2xl font-bold ${riskState.consecutive_losses > 3 ? 'text-amber-400' : 'text-slate-300'}`}>
              {riskState.consecutive_losses || 0} times
            </p>
            <div className="mt-2">
              <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
                <div 
                  className={`h-full ${riskState.consecutive_losses > 3 ? 'bg-amber-500' : 'bg-primary-500'}`}
                  style={{ width: `${Math.min(100, (riskState.consecutive_losses || 0) * 20)}%` }}
                />
              </div>
              <p className="text-xs text-slate-400 mt-1">Maximum consecutive losses: 5</p>
            </div>
          </div>

          <div>
            <p className="text-slate-400 text-sm">Peak Balance</p>
            <p className="text-2xl font-bold text-slate-300">
              ${riskState.peak_balance?.toFixed(2) || '10000.00'}
            </p>
            <p className="text-xs text-slate-400 mt-2">Used for drawdown calculation</p>
          </div>
        </div>
      </div>

      {/* Risk controlRuleList */}
      <div className="card">
        <h3 className="font-medium mb-4">Risk controlRule</h3>
        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Rule Name</th>
                <th>Status</th>
                <th>Priority</th>
                <th>Description</th>
              </tr>
            </thead>
            <tbody>
              {rules.length > 0 ? rules.map((rule, index) => (
                <tr key={index}>
                  <td className="font-medium">{rule.name}</td>
                  <td>
                    <span className={`flex items-center space-x-1 ${rule.enabled ? 'text-emerald-400' : 'text-slate-400'}`}>
                      {rule.enabled ? (
                        <><CheckCircle className="w-4 h-4" /><span>Enabled</span></>
                      ) : (
                        <><XCircle className="w-4 h-4" /><span>Disabled</span></>
                      )}
                    </span>
                  </td>
                  <td>{rule.priority}</td>
                  <td className="text-slate-400">
                    {rule.name === 'position_limit' && 'Position size and amount limits'}
                    {rule.name === 'daily_loss' && 'Daily loss limit'}
                    {rule.name === 'drawdown' && 'MaximumDrawdownLimit'}
                    {rule.name === 'consecutive_loss' && 'Consecutive losses Circuit breaker'}
                    {rule.name === 'price_protection' && 'Price protection (slippage/spread)'}
                  </td>
                </tr>
              )) : (
                <tr>
                  <td colSpan="4" className="text-center text-slate-400 py-4">
                    Loading risk control rules...
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Failed checks */}
      {riskState.failed_checks && riskState.failed_checks.length > 0 && (
        <div className="card border-2 border-amber-500">
          <div className="flex items-center space-x-2 mb-4">
            <AlertTriangle className="w-5 h-5 text-amber-500" />
            <h3 className="font-medium text-amber-400">Risk controlWarning</h3>
          </div>
          <ul className="space-y-2">
            {riskState.failed_checks.map((check, index) => (
              <li key={index} className="flex items-center space-x-2 text-amber-300">
                <XCircle className="w-4 h-4" />
                <span>{check}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

export default RiskPanel

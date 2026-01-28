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
        <h2 className="text-xl font-bold">风控状态</h2>
        <div className="flex items-center space-x-2">
          <button 
            onClick={handleResetRisk}
            className="btn btn-secondary flex items-center space-x-2"
          >
            <RotateCcw className="w-4 h-4" />
            <span>重置风控</span>
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

      {/* 风控状态概览 */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className={`card border-2 ${riskState.is_trading_allowed ? 'border-emerald-500' : 'border-red-500'}`}>
          <div className="flex items-center space-x-3">
            {riskState.is_trading_allowed ? (
              <CheckCircle className="w-8 h-8 text-emerald-500" />
            ) : (
              <XCircle className="w-8 h-8 text-red-500" />
            )}
            <div>
              <p className="text-slate-400 text-sm">交易状态</p>
              <p className={`text-lg font-bold ${riskState.is_trading_allowed ? 'text-emerald-400' : 'text-red-400'}`}>
                {riskState.is_trading_allowed ? '允许交易' : '禁止交易'}
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
              <p className="text-slate-400 text-sm">熔断状态</p>
              <p className={`text-lg font-bold ${!riskState.circuit_breaker_active ? 'text-emerald-400' : 'text-red-400'}`}>
                {riskState.circuit_breaker_active ? '已触发' : '正常'}
              </p>
            </div>
          </div>
        </div>

        <div className="card border-2 border-slate-600">
          <div className="flex items-center space-x-3">
            <Shield className="w-8 h-8 text-primary-500" />
            <div>
              <p className="text-slate-400 text-sm">冷却期</p>
              <p className="text-lg font-bold">
                {riskState.cooldown_until ? '冷却中' : '无'}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* 风控指标 */}
      <div className="card">
        <h3 className="font-medium mb-4">风控指标</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <div>
            <p className="text-slate-400 text-sm">今日盈亏</p>
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
              <p className="text-xs text-slate-400 mt-1">日亏损限额: $100</p>
            </div>
          </div>

          <div>
            <p className="text-slate-400 text-sm">当前回撤</p>
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
              <p className="text-xs text-slate-400 mt-1">最大回撤限额: 10%</p>
            </div>
          </div>

          <div>
            <p className="text-slate-400 text-sm">连续亏损</p>
            <p className={`text-2xl font-bold ${riskState.consecutive_losses > 3 ? 'text-amber-400' : 'text-slate-300'}`}>
              {riskState.consecutive_losses || 0} 次
            </p>
            <div className="mt-2">
              <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
                <div 
                  className={`h-full ${riskState.consecutive_losses > 3 ? 'bg-amber-500' : 'bg-primary-500'}`}
                  style={{ width: `${Math.min(100, (riskState.consecutive_losses || 0) * 20)}%` }}
                />
              </div>
              <p className="text-xs text-slate-400 mt-1">最大连续亏损: 5次</p>
            </div>
          </div>

          <div>
            <p className="text-slate-400 text-sm">峰值余额</p>
            <p className="text-2xl font-bold text-slate-300">
              ${riskState.peak_balance?.toFixed(2) || '10000.00'}
            </p>
            <p className="text-xs text-slate-400 mt-2">用于计算回撤</p>
          </div>
        </div>
      </div>

      {/* 风控规则列表 */}
      <div className="card">
        <h3 className="font-medium mb-4">风控规则</h3>
        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>规则名称</th>
                <th>状态</th>
                <th>优先级</th>
                <th>描述</th>
              </tr>
            </thead>
            <tbody>
              {rules.length > 0 ? rules.map((rule, index) => (
                <tr key={index}>
                  <td className="font-medium">{rule.name}</td>
                  <td>
                    <span className={`flex items-center space-x-1 ${rule.enabled ? 'text-emerald-400' : 'text-slate-400'}`}>
                      {rule.enabled ? (
                        <><CheckCircle className="w-4 h-4" /><span>启用</span></>
                      ) : (
                        <><XCircle className="w-4 h-4" /><span>禁用</span></>
                      )}
                    </span>
                  </td>
                  <td>{rule.priority}</td>
                  <td className="text-slate-400">
                    {rule.name === 'position_limit' && '持仓数量和金额限制'}
                    {rule.name === 'daily_loss' && '日亏损限制'}
                    {rule.name === 'drawdown' && '最大回撤限制'}
                    {rule.name === 'consecutive_loss' && '连续亏损熔断'}
                    {rule.name === 'price_protection' && '价格保护（滑点/价差）'}
                  </td>
                </tr>
              )) : (
                <tr>
                  <td colSpan="4" className="text-center text-slate-400 py-4">
                    加载风控规则中...
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* 失败的检查 */}
      {riskState.failed_checks && riskState.failed_checks.length > 0 && (
        <div className="card border-2 border-amber-500">
          <div className="flex items-center space-x-2 mb-4">
            <AlertTriangle className="w-5 h-5 text-amber-500" />
            <h3 className="font-medium text-amber-400">风控警告</h3>
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

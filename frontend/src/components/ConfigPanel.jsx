import React, { useState, useEffect } from 'react'
import { Settings, Save, RefreshCw } from 'lucide-react'

const API_BASE = ''

function ConfigPanel() {
  const [config, setConfig] = useState(null)
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState(null)

  const fetchConfig = async () => {
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/api/config`)
      if (res.ok) {
        const data = await res.json()
        setConfig(data)
      }
    } catch (err) {
      console.error('Failed to fetch config:', err)
    } finally {
      setLoading(false)
    }
  }

  const saveConfig = async () => {
    setSaving(true)
    setMessage(null)
    try {
      const res = await fetch(`${API_BASE}/api/config`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          trading: config.trading,
          risk: config.risk,
          ai: config.ai
        })
      })
      if (res.ok) {
        setMessage({ type: 'success', text: 'Configuration saved successfully' })
      } else {
        throw new Error('Save failed')
      }
    } catch (err) {
      setMessage({ type: 'error', text: 'Save failed: ' + err.message })
    } finally {
      setSaving(false)
    }
  }

  useEffect(() => {
    fetchConfig()
  }, [])

  const updateConfig = (section, key, value) => {
    setConfig(prev => ({
      ...prev,
      [section]: {
        ...prev[section],
        [key]: value
      }
    }))
  }

  if (!config) {
    return (
      <div className="card text-center py-12">
        <RefreshCw className="w-8 h-8 mx-auto mb-4 animate-spin text-slate-400" />
        <p className="text-slate-400">Loading configuration...</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold">System Settings</h2>
        <div className="flex items-center space-x-2">
          <button
            onClick={fetchConfig}
            className="btn btn-secondary"
            disabled={loading}
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
          <button
            onClick={saveConfig}
            className="btn btn-primary flex items-center space-x-2"
            disabled={saving}
          >
            <Save className="w-4 h-4" />
            <span>{saving ? 'Saving...' : 'Save Settings'}</span>
          </button>
        </div>
      </div>

      {message && (
        <div className={`p-3 rounded-lg ${
          message.type === 'success'
            ? 'bg-emerald-900/50 border border-emerald-700 text-emerald-200'
            : 'bg-red-900/50 border border-red-700 text-red-200'
        }`}>
          {message.text}
        </div>
      )}

      {/* Trading configuration */}
      <div className="card">
        <h3 className="font-medium mb-4 flex items-center space-x-2">
          <Settings className="w-5 h-5 text-primary-400" />
          <span>Trading Configuration</span>
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <div>
            <label className="block text-slate-400 text-sm mb-1">Base Currency</label>
            <input
              type="text"
              value={config.trading?.base_currency || 'USDT'}
              onChange={(e) => updateConfig('trading', 'base_currency', e.target.value)}
              className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2"
            />
          </div>
          <div>
            <label className="block text-slate-400 text-sm mb-1">Max Position Size</label>
            <input
              type="number"
              value={config.trading?.max_position_size || 1000}
              onChange={(e) => updateConfig('trading', 'max_position_size', parseFloat(e.target.value))}
              className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2"
            />
          </div>
          <div>
            <label className="block text-slate-400 text-sm mb-1">Max Single Order</label>
            <input
              type="number"
              value={config.trading?.max_single_order || 100}
              onChange={(e) => updateConfig('trading', 'max_single_order', parseFloat(e.target.value))}
              className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2"
            />
          </div>
          <div>
            <label className="block text-slate-400 text-sm mb-1">Leverage</label>
            <input
              type="number"
              value={config.trading?.leverage || 1}
              onChange={(e) => updateConfig('trading', 'leverage', parseInt(e.target.value))}
              className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2"
              min="1"
              max="20"
            />
          </div>
          <div>
            <label className="block text-slate-400 text-sm mb-1">Min Order Interval (sec)</label>
            <input
              type="number"
              value={config.trading?.min_order_interval || 60}
              onChange={(e) => updateConfig('trading', 'min_order_interval', parseInt(e.target.value))}
              className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2"
            />
          </div>
        </div>
      </div>

      {/* Risk control configuration */}
      <div className="card">
        <h3 className="font-medium mb-4 flex items-center space-x-2">
          <Settings className="w-5 h-5 text-amber-400" />
          <span>Risk Control Configuration</span>
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <div>
            <label className="block text-slate-400 text-sm mb-1">Max Daily Loss Amount</label>
            <input
              type="number"
              value={config.risk?.max_daily_loss || 100}
              onChange={(e) => updateConfig('risk', 'max_daily_loss', parseFloat(e.target.value))}
              className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2"
            />
          </div>
          <div>
            <label className="block text-slate-400 text-sm mb-1">Max Daily Loss (%)</label>
            <input
              type="number"
              value={config.risk?.max_daily_loss_pct || 5}
              onChange={(e) => updateConfig('risk', 'max_daily_loss_pct', parseFloat(e.target.value))}
              className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2"
              step="0.1"
            />
          </div>
          <div>
            <label className="block text-slate-400 text-sm mb-1">Max Drawdown (%)</label>
            <input
              type="number"
              value={config.risk?.max_drawdown || 10}
              onChange={(e) => updateConfig('risk', 'max_drawdown', parseFloat(e.target.value))}
              className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2"
              step="0.1"
            />
          </div>
          <div>
            <label className="block text-slate-400 text-sm mb-1">Stop Loss (%)</label>
            <input
              type="number"
              value={config.risk?.stop_loss_pct || 2}
              onChange={(e) => updateConfig('risk', 'stop_loss_pct', parseFloat(e.target.value))}
              className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2"
              step="0.1"
            />
          </div>
          <div>
            <label className="block text-slate-400 text-sm mb-1">Take Profit (%)</label>
            <input
              type="number"
              value={config.risk?.take_profit_pct || 5}
              onChange={(e) => updateConfig('risk', 'take_profit_pct', parseFloat(e.target.value))}
              className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2"
              step="0.1"
            />
          </div>
          <div>
            <label className="block text-slate-400 text-sm mb-1">Max Consecutive Losses</label>
            <input
              type="number"
              value={config.risk?.max_consecutive_losses || 5}
              onChange={(e) => updateConfig('risk', 'max_consecutive_losses', parseInt(e.target.value))}
              className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2"
            />
          </div>
          <div>
            <label className="block text-slate-400 text-sm mb-1">Cooldown Period (sec)</label>
            <input
              type="number"
              value={config.risk?.cooldown_period || 3600}
              onChange={(e) => updateConfig('risk', 'cooldown_period', parseInt(e.target.value))}
              className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2"
            />
          </div>
          <div>
            <label className="block text-slate-400 text-sm mb-1">Max Open Positions</label>
            <input
              type="number"
              value={config.risk?.position_limit || 3}
              onChange={(e) => updateConfig('risk', 'position_limit', parseInt(e.target.value))}
              className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2"
            />
          </div>
        </div>
      </div>

      {/* AI configuration */}
      <div className="card">
        <h3 className="font-medium mb-4 flex items-center space-x-2">
          <Settings className="w-5 h-5 text-emerald-400" />
          <span>AI Configuration</span>
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <div>
            <label className="block text-slate-400 text-sm mb-1">Enable AI Signals</label>
            <select
              value={config.ai?.enabled ? 'true' : 'false'}
              onChange={(e) => updateConfig('ai', 'enabled', e.target.value === 'true')}
              className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2"
            >
              <option value="true">Enabled</option>
              <option value="false">Disabled</option>
            </select>
          </div>
          <div>
            <label className="block text-slate-400 text-sm mb-1">Model</label>
            <select
              value={config.ai?.model || 'gpt-4.1-mini'}
              onChange={(e) => updateConfig('ai', 'model', e.target.value)}
              className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2"
            >
              <option value="gpt-4.1-mini">GPT-4.1 Mini</option>
              <option value="gpt-4.1-nano">GPT-4.1 Nano</option>
              <option value="gemini-2.5-flash">Gemini 2.5 Flash</option>
            </select>
          </div>
          <div>
            <label className="block text-slate-400 text-sm mb-1">Temperature</label>
            <input
              type="number"
              value={config.ai?.temperature || 0.3}
              onChange={(e) => updateConfig('ai', 'temperature', parseFloat(e.target.value))}
              className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2"
              step="0.1"
              min="0"
              max="1"
            />
          </div>
          <div>
            <label className="block text-slate-400 text-sm mb-1">Confidence Threshold</label>
            <input
              type="number"
              value={config.ai?.confidence_threshold || 0.6}
              onChange={(e) => updateConfig('ai', 'confidence_threshold', parseFloat(e.target.value))}
              className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2"
              step="0.1"
              min="0"
              max="1"
            />
          </div>
          <div>
            <label className="block text-slate-400 text-sm mb-1">Signal TTL (sec)</label>
            <input
              type="number"
              value={config.ai?.signal_ttl || 300}
              onChange={(e) => updateConfig('ai', 'signal_ttl', parseInt(e.target.value))}
              className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2"
            />
          </div>
        </div>
      </div>

      {/* Environment info */}
      <div className="card">
        <h3 className="font-medium mb-4">Environment Info</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
          <div>
            <span className="text-slate-400">Environment:</span>
            <span className="ml-2 font-medium">{config.env || 'dev'}</span>
          </div>
          <div>
            <span className="text-slate-400">Debug Mode:</span>
            <span className="ml-2 font-medium">{config.debug ? 'On' : 'Off'}</span>
          </div>
          <div>
            <span className="text-slate-400">API Port:</span>
            <span className="ml-2 font-medium">{config.api_port || 8000}</span>
          </div>
        </div>
      </div>
    </div>
  )
}

export default ConfigPanel

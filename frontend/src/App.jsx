import React, { useState, useEffect, useCallback } from 'react'
import {
  Activity, TrendingUp, TrendingDown, AlertTriangle,
  Play, Square, RefreshCw, Settings, BarChart3,
  Wallet, Shield, Zap, Clock, DollarSign, Download, Newspaper, Users, Waves
} from 'lucide-react'
import Dashboard from './components/Dashboard'
import PositionPanel from './components/PositionPanel'
import OrderPanel from './components/OrderPanel'
import SignalPanel from './components/SignalPanel'
import RiskPanel from './components/RiskPanel'
import BacktestPanel from './components/BacktestPanel'
import ConfigPanel from './components/ConfigPanel'
import ScraperPanel from './components/ScraperPanel'
import NewsPanel from './components/NewsPanel'
import MultiAgentPanel from './components/MultiAgentPanel'
import WhaleTrackerPanel from './components/WhaleTrackerPanel'
import VibeStrategyPanel from './components/VibeStrategyPanel'
import DecisionFlowMatrix from './components/DecisionFlowMatrix'
import TradingPet from './components/TradingPet'

const API_BASE = ''

function App() {
  const [activeTab, setActiveTab] = useState('dashboard')
  const [status, setStatus] = useState(null)
  const [isRunning, setIsRunning] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [ws, setWs] = useState(null)
  const [ticker, setTicker] = useState(null)
  const [signal, setSignal] = useState(null)

  // Fetch system status
  const fetchStatus = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/status`)
      if (res.ok) {
        const data = await res.json()
        setStatus(data)
        setIsRunning(data.is_running)
        if (data.last_ticker) setTicker(data.last_ticker)
        if (data.last_signal) setSignal(data.last_signal)
      }
    } catch (err) {
      console.error('Failed to fetch status:', err)
    }
  }, [])

  // WebSocket connection
  useEffect(() => {
    const connectWs = () => {
      const wsUrl = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws`
      const websocket = new WebSocket(wsUrl)

      websocket.onopen = () => {
        console.log('WebSocket connected')
        setWs(websocket)
      }

      websocket.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data)
          if (message.type === 'ticker') {
            setTicker(message.data)
          } else if (message.type === 'signal') {
            setSignal(message.data)
          }
        } catch (err) {
          console.error('WebSocket message error:', err)
        }
      }

      websocket.onclose = () => {
        console.log('WebSocket disconnected')
        setWs(null)
        // Reconnect
        setTimeout(connectWs, 3000)
      }

      websocket.onerror = (err) => {
        console.error('WebSocket error:', err)
      }
    }

    connectWs()

    return () => {
      if (ws) ws.close()
    }
  }, [])

  // Periodically refresh status
  useEffect(() => {
    fetchStatus()
    const interval = setInterval(fetchStatus, 5000)
    return () => clearInterval(interval)
  }, [fetchStatus])

  // Periodically fetch market data
  useEffect(() => {
    const fetchTicker = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/ticker/BTC-USDT`)
        if (res.ok) {
          const data = await res.json()
          setTicker(data)
        }
      } catch (err) {
        console.error('Failed to fetch ticker:', err)
      }
    }

    fetchTicker()
    const interval = setInterval(fetchTicker, 3000)
    return () => clearInterval(interval)
  }, [])

  // Start Agent
  const handleStart = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${API_BASE}/api/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ symbol: 'BTC/USDT' })
      })
      if (res.ok) {
        setIsRunning(true)
        fetchStatus()
      } else {
        throw new Error('Failed to start')
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  // Stop Agent
  const handleStop = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${API_BASE}/api/stop`, { method: 'POST' })
      if (res.ok) {
        setIsRunning(false)
        fetchStatus()
      } else {
        throw new Error('Failed to stop')
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const tabs = [
    { id: 'dashboard', label: 'Dashboard', icon: Activity },
    { id: 'decision-flow', label: 'Decision Flow', icon: Activity },
    { id: 'multi-agent', label: 'AI Committee', icon: Users },
    { id: 'vibe-strategy', label: 'Vibe Strategy', icon: Zap },
    { id: 'whale-tracker', label: 'Whale Tracker', icon: Waves },
    { id: 'news', label: 'Financial News', icon: Newspaper },
    { id: 'positions', label: 'Positions', icon: Wallet },
    { id: 'orders', label: 'Orders', icon: Clock },
    { id: 'signals', label: 'Signal Analysis', icon: Zap },
    { id: 'risk', label: 'Risk Control', icon: Shield },
    { id: 'backtest', label: 'Backtest', icon: BarChart3 },
    { id: 'scraper', label: 'Data Scraper', icon: Download },
    { id: 'config', label: 'Settings', icon: Settings },
  ]

  return (
    <div className="min-h-screen bg-slate-900">
      {/* Top navigation */}
      <header className="bg-slate-800 border-b border-slate-700">
        <div className="max-w-7xl mx-auto px-4 py-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <div className="flex items-center space-x-2">
                <div className="w-8 h-8 bg-primary-600 rounded-lg flex items-center justify-center">
                  <TrendingUp className="w-5 h-5 text-white" />
                </div>
                <h1 className="text-xl font-bold text-white">MoonMate</h1>
              </div>
              <span className="text-sm text-slate-400">AI Trading Assistant with Gamification</span>
            </div>

            <div className="flex items-center space-x-4">
              {/* Status indicator */}
              <div className="flex items-center space-x-2">
                <div className={`status-dot ${isRunning ? 'online' : 'offline'}`}></div>
                <span className="text-sm text-slate-300">
                  {isRunning ? 'Running' : 'Stopped'}
                </span>
              </div>

              {/* Control buttons */}
              {isRunning ? (
                <button
                  onClick={handleStop}
                  disabled={loading}
                  className="btn btn-danger flex items-center space-x-2"
                >
                  <Square className="w-4 h-4" />
                  <span>Stop</span>
                </button>
              ) : (
                <button
                  onClick={handleStart}
                  disabled={loading}
                  className="btn btn-success flex items-center space-x-2"
                >
                  <Play className="w-4 h-4" />
                  <span>Start</span>
                </button>
              )}

              <button
                onClick={fetchStatus}
                className="btn btn-secondary"
              >
                <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Tab navigation */}
      <nav className="bg-slate-800/50 border-b border-slate-700">
        <div className="max-w-7xl mx-auto px-4">
          <div className="flex flex-wrap gap-1">
            {tabs.map(tab => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center space-x-2 px-4 py-2 text-sm font-medium transition-colors
                  ${activeTab === tab.id
                    ? 'text-primary-400 border-b-2 border-primary-400'
                    : 'text-slate-400 hover:text-slate-200'
                  }`}
              >
                <tab.icon className="w-4 h-4" />
                <span>{tab.label}</span>
              </button>
            ))}
          </div>
        </div>
      </nav>

      {/* Error alert */}
      {error && (
        <div className="max-w-7xl mx-auto px-4 py-2">
          <div className="bg-red-900/50 border border-red-700 rounded-lg p-3 flex items-center space-x-2">
            <AlertTriangle className="w-5 h-5 text-red-400" />
            <span className="text-red-200">{error}</span>
          </div>
        </div>
      )}

      {/* Main content area */}
      <main className="max-w-7xl mx-auto px-4 py-6">
        {activeTab === 'dashboard' && (
          <Dashboard
            status={status}
            ticker={ticker}
            signal={signal}
            isRunning={isRunning}
          />
        )}
        {activeTab === 'multi-agent' && <MultiAgentPanel />}
        {activeTab === 'decision-flow' && <DecisionFlowMatrix />}
        {activeTab === 'vibe-strategy' && <VibeStrategyPanel />}
        {activeTab === 'whale-tracker' && <WhaleTrackerPanel />}
        {activeTab === 'news' && <NewsPanel />}
        {activeTab === 'positions' && <PositionPanel status={status} />}
        {activeTab === 'orders' && <OrderPanel />}
        {activeTab === 'signals' && <SignalPanel signal={signal} ticker={ticker} />}
        {activeTab === 'risk' && <RiskPanel status={status} />}
        {activeTab === 'backtest' && <BacktestPanel />}
        {activeTab === 'scraper' && <ScraperPanel />}
        {activeTab === 'config' && <ConfigPanel />}
      </main>

      {/* AI Trading Assistant Pet */}
      <TradingPet
        stats={status || {}}
        isRunning={isRunning}
        ticker={ticker}
        onStart={handleStart}
        onStop={handleStop}
      />

      {/* Bottom status bar */}
      <footer className="fixed bottom-0 left-0 right-0 bg-slate-800 border-t border-slate-700 py-2">
        <div className="max-w-7xl mx-auto px-4">
          <div className="flex items-center justify-between text-sm text-slate-400">
            <div className="flex items-center space-x-4">
              <span>WebSocket: {ws ? 'Connected' : 'Disconnected'}</span>
              {ticker && (
                <span>
                  BTC/USDT:
                  <span className={ticker.change_24h >= 0 ? 'price-up' : 'price-down'}>
                    {' '}${ticker.last_price?.toLocaleString(undefined, {minimumFractionDigits: 2})}
                  </span>
                </span>
              )}
            </div>
            <div>
              <span>© 2026 Auto Trading Agent</span>
            </div>
          </div>
        </div>
      </footer>
    </div>
  )
}

export default App

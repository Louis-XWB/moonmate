import React, { useState, useEffect } from 'react'
import { Zap, TrendingUp, TrendingDown, Minus, RefreshCw, Brain } from 'lucide-react'

const API_BASE = ''

function SignalPanel({ signal, ticker }) {
  const [sentiment, setSentiment] = useState(null)
  const [loading, setLoading] = useState(false)
  const [selectedSymbol, setSelectedSymbol] = useState('BTC-USDT')

  const fetchSentiment = async () => {
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/api/sentiment/${selectedSymbol}`)
      if (res.ok) {
        const data = await res.json()
        setSentiment(data)
      }
    } catch (err) {
      console.error('Failed to fetch sentiment:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchSentiment()
  }, [selectedSymbol])

  const directionConfig = {
    long: { icon: TrendingUp, color: 'bg-emerald-500', label: 'Long', textColor: 'text-emerald-400' },
    short: { icon: TrendingDown, color: 'bg-red-500', label: 'Short', textColor: 'text-red-400' },
    neutral: { icon: Minus, color: 'bg-slate-500', label: 'Hold', textColor: 'text-slate-400' },
    close: { icon: Minus, color: 'bg-amber-500', label: 'Close position', textColor: 'text-amber-400' },
  }

  const config = signal ? directionConfig[signal.direction] || directionConfig.neutral : directionConfig.neutral
  const DirectionIcon = config.icon

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold">SignalAnalysis</h2>
        <div className="flex items-center space-x-4">
          <select
            value={selectedSymbol}
            onChange={(e) => setSelectedSymbol(e.target.value)}
            className="bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-sm"
          >
            <option value="BTC-USDT">BTC/USDT</option>
            <option value="ETH-USDT">ETH/USDT</option>
            <option value="SOL-USDT">SOL/USDT</option>
          </select>
          <button 
            onClick={fetchSentiment}
            className="btn btn-secondary"
            disabled={loading}
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* CurrentSignal */}
        <div className="card">
          <div className="flex items-center space-x-2 mb-4">
            <Zap className="w-5 h-5 text-primary-400" />
            <h3 className="font-medium">CurrentTrading signal</h3>
          </div>
          
          {signal ? (
            <div className="space-y-4">
              {/* Signal direction */}
              <div className="flex items-center justify-center py-6">
                <div className={`w-24 h-24 rounded-full ${config.color} flex items-center justify-center`}>
                  <DirectionIcon className="w-12 h-12 text-white" />
                </div>
              </div>
              <div className="text-center">
                <p className={`text-2xl font-bold ${config.textColor}`}>{config.label}</p>
                <p className="text-slate-400 text-sm mt-1">{signal.symbol}</p>
              </div>

              {/* Signal Details */}
              <div className="space-y-3 pt-4 border-t border-slate-700">
                <div className="flex items-center justify-between">
                  <span className="text-slate-400">Signal Strength</span>
                  <div className="flex items-center space-x-2">
                    <div className="w-32 h-2 bg-slate-700 rounded-full overflow-hidden">
                      <div 
                        className={`h-full rounded-full ${config.color}`}
                        style={{ width: `${signal.strength * 100}%` }}
                      />
                    </div>
                    <span className="text-sm font-medium">{(signal.strength * 100).toFixed(0)}%</span>
                  </div>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-slate-400">Confidence</span>
                  <span className="font-medium">{(signal.confidence * 100).toFixed(0)}%</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-slate-400">Signal source</span>
                  <span className="font-medium">{signal.source || 'fusion'}</span>
                </div>
                {signal.entry_price && (
                  <div className="flex items-center justify-between">
                    <span className="text-slate-400">Suggested entry price</span>
                    <span className="font-medium">${signal.entry_price?.toLocaleString()}</span>
                  </div>
                )}
                {signal.stop_loss && (
                  <div className="flex items-center justify-between">
                    <span className="text-slate-400">Stop-loss Price</span>
                    <span className="font-medium text-red-400">${signal.stop_loss?.toLocaleString()}</span>
                  </div>
                )}
                {signal.take_profit && (
                  <div className="flex items-center justify-between">
                    <span className="text-slate-400">Take-profit Price</span>
                    <span className="font-medium text-emerald-400">${signal.take_profit?.toLocaleString()}</span>
                  </div>
                )}
              </div>

              {/* Signal reason */}
              {signal.reason && (
                <div className="pt-4 border-t border-slate-700">
                  <p className="text-slate-400 text-sm mb-2">Signal reason</p>
                  <p className="text-sm">{signal.reason}</p>
                </div>
              )}

              {/* Evidence list */}
              {signal.evidence && signal.evidence.length > 0 && (
                <div className="pt-4 border-t border-slate-700">
                  <p className="text-slate-400 text-sm mb-2">Supporting Evidence</p>
                  <ul className="space-y-1">
                    {signal.evidence.map((e, i) => (
                      <li key={i} className="text-sm text-slate-300">• {e}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          ) : (
            <div className="text-center py-12 text-slate-400">
              <Zap className="w-12 h-12 mx-auto mb-4 opacity-50" />
              <p>No trading signals available</p>
              <p className="text-sm mt-2">Signals will be generated after starting the agent</p>
            </div>
          )}
        </div>

        {/* Market Sentiment */}
        <div className="card">
          <div className="flex items-center space-x-2 mb-4">
            <Brain className="w-5 h-5 text-primary-400" />
            <h3 className="font-medium">Market SentimentAnalysis</h3>
          </div>
          
          {sentiment ? (
            <div className="space-y-6">
              {/* Fear & Greed Index */}
              <div>
                <p className="text-slate-400 text-sm mb-2">Fear & Greed Index</p>
                <div className="relative h-8 bg-gradient-to-r from-red-500 via-yellow-500 to-emerald-500 rounded-full overflow-hidden">
                  <div 
                    className="absolute top-0 bottom-0 w-1 bg-white"
                    style={{ left: `${sentiment.fear_greed_index?.value || 50}%` }}
                  />
                </div>
                <div className="flex justify-between text-xs text-slate-400 mt-1">
                  <span>Extreme Fear</span>
                  <span>neutral</span>
                  <span>Extreme Greed</span>
                </div>
                <div className="text-center mt-2">
                  <span className="text-2xl font-bold">{sentiment.fear_greed_index?.value || 50}</span>
                  <span className="text-slate-400 ml-2">{sentiment.fear_greed_index?.classification}</span>
                </div>
              </div>

              {/* SentimentAnalysis */}
              <div className="pt-4 border-t border-slate-700">
                <p className="text-slate-400 text-sm mb-3">SentimentAnalysis</p>
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-slate-400">Sentiment Tendency</span>
                    <span className={`font-medium ${
                      sentiment.sentiment?.sentiment === 'bullish' ? 'text-emerald-400' :
                      sentiment.sentiment?.sentiment === 'bearish' ? 'text-red-400' :
                      'text-slate-400'
                    }`}>
                      {sentiment.sentiment?.sentiment === 'bullish' ? 'Bullish' :
                       sentiment.sentiment?.sentiment === 'bearish' ? 'Bearish' : 'neutral'}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-slate-400">Sentiment Score</span>
                    <span className="font-medium">
                      {((sentiment.sentiment?.score || 0) * 100).toFixed(0)}%
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-slate-400">Confidence</span>
                    <span className="font-medium">
                      {((sentiment.sentiment?.confidence || 0) * 100).toFixed(0)}%
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-slate-400">Number of data sources</span>
                    <span className="font-medium">{sentiment.sentiment?.sources_count || 0}</span>
                  </div>
                </div>
              </div>

              {/* Keywords */}
              {sentiment.sentiment?.keywords && sentiment.sentiment.keywords.length > 0 && (
                <div className="pt-4 border-t border-slate-700">
                  <p className="text-slate-400 text-sm mb-2">Trending Keywords</p>
                  <div className="flex flex-wrap gap-2">
                    {sentiment.sentiment.keywords.map((keyword, i) => (
                      <span 
                        key={i}
                        className="px-2 py-1 bg-slate-700 rounded text-sm"
                      >
                        {keyword}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="text-center py-12 text-slate-400">
              <Brain className="w-12 h-12 mx-auto mb-4 opacity-50" />
              <p>Loading sentiment data...</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default SignalPanel

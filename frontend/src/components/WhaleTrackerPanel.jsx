import React, { useState, useEffect } from 'react';
import { RefreshCw, AlertTriangle, TrendingUp, TrendingDown, DollarSign, Target, Activity } from 'lucide-react';

const WhaleTrackerPanel = () => {
  const [analysis, setAnalysis] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [autoRefresh, setAutoRefresh] = useState(false);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      // Get analysis data
      const analysisResponse = await fetch('https://8000-igyitwrl655jpdhlmwvph-a31b4228.sg1.manus.computer/api/whale/analysis?symbol=BTC/USDT');
      const analysisResult = await analysisResponse.json();
      
      // Get alerts
      const alertsResponse = await fetch('https://8000-igyitwrl655jpdhlmwvph-a31b4228.sg1.manus.computer/api/whale/alerts?symbol=BTC/USDT');
      const alertsResult = await alertsResponse.json();
      
      if (analysisResult.success) {
        setAnalysis(analysisResult.data);
      }
      
      if (alertsResult.success) {
        setAlerts(alertsResult.data);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  useEffect(() => {
    if (autoRefresh) {
      const interval = setInterval(fetchData, 60000);
      return () => clearInterval(interval);
    }
  }, [autoRefresh]);

  const formatNumber = (num) => {
    if (num >= 1000000) {
      return `$${(num / 1000000).toFixed(2)}M`;
    } else if (num >= 1000) {
      return `$${(num / 1000).toFixed(2)}K`;
    }
    return `$${num.toFixed(2)}`;
  };

  const getSentimentColor = (sentiment) => {
    switch (sentiment) {
      case 'bullish':
        return 'text-green-400 bg-green-900/30 border-green-500/50';
      case 'bearish':
        return 'text-red-400 bg-red-900/30 border-red-500/50';
      default:
        return 'text-gray-400 bg-gray-900/30 border-gray-500/50';
    }
  };

  const getSentimentText = (sentiment) => {
    const map = {
      'bullish': 'Bullish',
      'bearish': 'Bearish',
      'neutral': 'neutral'
    };
    return map[sentiment] || sentiment;
  };

  const getSentimentIcon = (sentiment) => {
    switch (sentiment) {
      case 'bullish':
        return <TrendingUp className="w-5 h-5" />;
      case 'bearish':
        return <TrendingDown className="w-5 h-5" />;
      default:
        return <Activity className="w-5 h-5" />;
    }
  };

  const getSeverityColor = (severity) => {
    switch (severity) {
      case 'high':
        return 'border-red-500 bg-red-900/20';
      case 'medium':
        return 'border-yellow-500 bg-yellow-900/20';
      default:
        return 'border-blue-500 bg-blue-900/20';
    }
  };

  return (
    <div className="space-y-6">
      {/* Title and Controls */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-3xl">🐋</span>
          <h2 className="text-2xl font-bold text-white">Whale Tracker</h2>
          <span className="px-3 py-1 text-xs font-semibold text-blue-300 bg-blue-900/30 border border-blue-500/50 rounded-full">
            On-Chain Data
          </span>
        </div>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-sm text-gray-300 cursor-pointer">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
              className="w-4 h-4 text-blue-600 bg-gray-700 border-gray-600 rounded focus:ring-blue-500"
            />
            Auto Refresh
          </label>
          <button
            onClick={fetchData}
            disabled={loading}
            className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
      </div>

      {/* Error Message */}
      {error && (
        <div className="flex items-center gap-2 p-4 text-red-300 bg-red-900/20 border border-red-500/50 rounded-lg">
          <AlertTriangle className="w-5 h-5" />
          <span>{error}</span>
        </div>
      )}

      {/* Loading Status */}
      {loading && !analysis && (
        <div className="flex items-center justify-center p-12">
          <div className="flex flex-col items-center gap-3">
            <RefreshCw className="w-8 h-8 text-blue-400 animate-spin" />
            <p className="text-gray-400">Tracking whales...</p>
          </div>
        </div>
      )}

      {/* Alerts */}
      {alerts && alerts.length > 0 && (
        <div className="space-y-3">
          <h3 className="text-lg font-semibold text-white flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 text-yellow-400" />
            Whale Alerts
          </h3>
          {alerts.map((alert, index) => (
            <div
              key={index}
              className={`p-4 border-l-4 rounded-lg ${getSeverityColor(alert.severity)}`}
            >
              <p className="font-semibold text-white mb-2">{alert.message}</p>
              {alert.details && (
                <div className="text-sm text-gray-400 space-y-1">
                  {alert.details.address && (
                    <p>Address: {alert.details.address.slice(0, 10)}...{alert.details.address.slice(-8)}</p>
                  )}
                  {alert.details.size && (
                    <p>Position: {formatNumber(alert.details.size)}</p>
                  )}
                  {alert.details.net_flow && (
                    <p>Net Flow: {formatNumber(Math.abs(alert.details.net_flow))}</p>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Analysis Overview */}
      {analysis && (
        <div className="space-y-6">
          {/* Stats Cards */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="p-4 bg-gradient-to-br from-blue-900/40 to-purple-900/40 border border-blue-500/50 rounded-lg">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm text-gray-400">Whale Count</span>
                <span className="text-2xl">🐋</span>
              </div>
              <p className="text-2xl font-bold text-white">{analysis.whale_count}</p>
            </div>

            <div className="p-4 bg-gradient-to-br from-green-900/40 to-blue-900/40 border border-green-500/50 rounded-lg">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm text-gray-400">Long positions </span>
                <TrendingUp className="w-5 h-5 text-green-400" />
              </div>
              <p className="text-2xl font-bold text-green-400">{formatNumber(analysis.total_long_size)}</p>
            </div>

            <div className="p-4 bg-gradient-to-br from-red-900/40 to-purple-900/40 border border-red-500/50 rounded-lg">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm text-gray-400">Short positions </span>
                <TrendingDown className="w-5 h-5 text-red-400" />
              </div>
              <p className="text-2xl font-bold text-red-400">{formatNumber(analysis.total_short_size)}</p>
            </div>

            <div className="p-4 bg-gradient-to-br from-yellow-900/40 to-orange-900/40 border border-yellow-500/50 rounded-lg">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm text-gray-400">Net Flow</span>
                <DollarSign className="w-5 h-5 text-yellow-400" />
              </div>
              <p className={`text-2xl font-bold ${analysis.net_flow > 0 ? 'text-green-400' : analysis.net_flow < 0 ? 'text-red-400' : 'text-gray-400'}`}>
                {analysis.net_flow > 0 ? '+' : ''}{formatNumber(analysis.net_flow)}
              </p>
            </div>
          </div>

          {/* Market Sentiment */}
          <div className="p-6 bg-gray-800/50 border border-gray-700 rounded-xl">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-white">Market Sentiment</h3>
              <div className={`flex items-center gap-2 px-4 py-2 border rounded-lg ${getSentimentColor(analysis.sentiment)}`}>
                {getSentimentIcon(analysis.sentiment)}
                <span className="font-semibold">{getSentimentText(analysis.sentiment)}</span>
              </div>
            </div>
            
            <div className="flex items-center gap-2 mb-4">
              <span className="text-sm text-gray-400">Confidence:</span>
              <div className="flex items-center gap-2 flex-1">
                <div className="flex-1 h-2 bg-gray-700 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-blue-500 to-purple-500 transition-all duration-500"
                    style={{ width: `${analysis.confidence * 100}%` }}
                  />
                </div>
                <span className="text-sm font-semibold text-white">{(analysis.confidence * 100).toFixed(0)}%</span>
              </div>
            </div>

            <div className="p-4 bg-black/30 rounded-lg">
              <p className="text-sm text-gray-300">{analysis.summary}</p>
            </div>
          </div>

          {/* Top 10 Whales */}
          <div className="space-y-3">
            <h3 className="text-lg font-semibold text-white">🏆 Top 10 Whales</h3>
            <div className="space-y-2">
              {analysis.top_whales.map((whale, index) => (
                <div
                  key={index}
                  className="p-4 bg-gray-800/50 border border-gray-700 rounded-lg hover:border-blue-500/50 transition-colors"
                >
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-3">
                      <span className="text-xl">#{index + 1}</span>
                      <div>
                        <p className="text-sm font-mono text-gray-400">
                          {whale.address.slice(0, 10)}...{whale.address.slice(-8)}
                        </p>
                        <div className="flex items-center gap-2 mt-1">
                          <span className={`px-2 py-0.5 text-xs font-semibold rounded ${whale.side === 'long' ? 'text-green-300 bg-green-900/30' : 'text-red-300 bg-red-900/30'}`}>
                            {whale.side === 'long' ? 'Long' : 'Short'}
                          </span>
                          <span className="text-xs text-gray-500">{whale.leverage.toFixed(1)}x</span>
                        </div>
                      </div>
                    </div>
                    <div className="text-right">
                      <p className="text-lg font-bold text-white">{formatNumber(whale.size)}</p>
                      <p className={`text-sm font-semibold ${whale.pnl > 0 ? 'text-green-400' : whale.pnl < 0 ? 'text-red-400' : 'text-gray-400'}`}>
                        {whale.pnl > 0 ? '+' : ''}{formatNumber(whale.pnl)} ({whale.pnl_percent > 0 ? '+' : ''}{(whale.pnl_percent * 100).toFixed(2)}%)
                      </p>
                    </div>
                  </div>

                  <div className="grid grid-cols-3 gap-4 text-sm">
                    <div>
                      <p className="text-gray-400">Entry Price</p>
                      <p className="font-semibold text-white">${whale.entry_price.toFixed(2)}</p>
                    </div>
                    <div>
                      <p className="text-gray-400">Current Price</p>
                      <p className="font-semibold text-white">${whale.current_price.toFixed(2)}</p>
                    </div>
                    <div>
                      <p className="text-gray-400">Liquidation Price</p>
                      <p className="font-semibold text-yellow-400">
                        {whale.liquidation_price ? `$${whale.liquidation_price.toFixed(2)}` : 'N/A'}
                      </p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Recent Activity */}
          {analysis.recent_activities && analysis.recent_activities.length > 0 && (
            <div className="space-y-3">
              <h3 className="text-lg font-semibold text-white">📊 Recent Activity</h3>
              <div className="space-y-2">
                {analysis.recent_activities.map((activity, index) => (
                  <div
                    key={index}
                    className="flex items-center justify-between p-3 bg-gray-800/30 border border-gray-700 rounded-lg"
                  >
                    <div className="flex items-center gap-3">
                      <span className="text-sm font-mono text-gray-400">
                        {activity.address.slice(0, 8)}...
                      </span>
                      <span className={`px-2 py-0.5 text-xs font-semibold rounded ${
                        activity.action.includes('long') ? 'text-green-300 bg-green-900/30' :
                        activity.action.includes('short') ? 'text-red-300 bg-red-900/30' :
                        'text-gray-300 bg-gray-900/30'
                      }`}>
                        {activity.action.replace('_', ' ')}
                      </span>
                      <span className="text-sm text-white font-semibold">{formatNumber(activity.size)}</span>
                      <span className="text-sm text-gray-400">@ ${activity.price.toFixed(2)}</span>
                    </div>
                    <span className="text-xs text-gray-500">
                      {new Date(activity.timestamp).toLocaleTimeString('en-US')}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default WhaleTrackerPanel;

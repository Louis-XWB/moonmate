import React, { useState, useEffect } from 'react'
import { Newspaper, Star, TrendingUp, TrendingDown, Minus, RefreshCw, Filter, ExternalLink } from 'lucide-react'

const API_BASE = ''

function NewsPanel() {
  const [news, setNews] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [minStars, setMinStars] = useState(3)
  const [limit, setLimit] = useState(10)
  const [autoRefresh, setAutoRefresh] = useState(false)

  // Fetch AI-analyzed news
  const fetchNews = async () => {
    setLoading(true)
    setError(null)
    try {
      console.log('Fetching news...')
      const res = await fetch(`${API_BASE}/api/news/analyzed?min_stars=${minStars}&limit=${limit}`)
      if (res.ok) {
        const data = await res.json()
        console.log(`Successfully fetched ${data.news?.length || 0} news articles`)
        setNews(data.news || [])
      } else {
        const errorText = await res.text()
        console.error('News API error:', res.status, errorText)
        throw new Error(`Failed to load news (${res.status}): ${errorText}`)
      }
    } catch (err) {
      setError(err.message)
      console.error('News fetch error:', err)
    } finally {
      setLoading(false)
    }
  }

  // Initial load
  useEffect(() => {
    fetchNews()
  }, [minStars, limit])

  // Auto refresh
  useEffect(() => {
    if (!autoRefresh) return

    const interval = setInterval(fetchNews, 60000) // Refresh every minute
    return () => clearInterval(interval)
  }, [autoRefresh, minStars, limit])

  // Impact direction icon
  const getDirectionIcon = (direction) => {
    switch (direction) {
      case 'bullish':
        return <TrendingUp className="w-4 h-4 text-green-400" />
      case 'bearish':
        return <TrendingDown className="w-4 h-4 text-red-400" />
      default:
        return <Minus className="w-4 h-4 text-slate-400" />
    }
  }

  // Impact direction text
  const getDirectionText = (direction) => {
    switch (direction) {
      case 'bullish':
        return 'Bullish'
      case 'bearish':
        return 'Bearish'
      default:
        return 'Neutral'
    }
  }

  // Impact level color
  const getImpactColor = (level) => {
    switch (level) {
      case 'critical':
        return 'text-red-400 bg-red-900/30 border-red-700'
      case 'high':
        return 'text-orange-400 bg-orange-900/30 border-orange-700'
      case 'medium':
        return 'text-yellow-400 bg-yellow-900/30 border-yellow-700'
      case 'low':
        return 'text-blue-400 bg-blue-900/30 border-blue-700'
      default:
        return 'text-slate-400 bg-slate-900/30 border-slate-700'
    }
  }

  // Impact level text
  const getImpactText = (level) => {
    switch (level) {
      case 'critical':
        return 'Critical'
      case 'high':
        return 'High'
      case 'medium':
        return 'Medium'
      case 'low':
        return 'Low'
      default:
        return 'None'
    }
  }

  // Format time
  const formatTime = (timestamp) => {
    const date = new Date(timestamp)
    const now = new Date()
    const diff = Math.floor((now - date) / 1000 / 60) // Difference in minutes

    if (diff < 60) {
      return `${diff}m ago`
    } else if (diff < 1440) {
      return `${Math.floor(diff / 60)}h ago`
    } else {
      return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
    }
  }

  return (
    <div className="space-y-4">
      {/* Title and controls */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <Newspaper className="w-6 h-6 text-primary-400" />
          <h2 className="text-xl font-bold text-white">Financial News</h2>
          <span className="text-sm text-slate-400">AI Analysis + Star Rating</span>
        </div>

        <div className="flex items-center space-x-3">
          {/* Star rating filter */}
          <div className="flex items-center space-x-2">
            <Filter className="w-4 h-4 text-slate-400" />
            <select
              value={minStars}
              onChange={(e) => setMinStars(Number(e.target.value))}
              className="bg-slate-800 border border-slate-700 rounded px-2 py-1 text-sm text-white"
            >
              <option value={1}>1+ Stars</option>
              <option value={2}>2+ Stars</option>
              <option value={3}>3+ Stars</option>
              <option value={4}>4+ Stars</option>
              <option value={5}>5 Stars Only</option>
            </select>
          </div>

          {/* Quantity limit */}
          <select
            value={limit}
            onChange={(e) => setLimit(Number(e.target.value))}
            className="bg-slate-800 border border-slate-700 rounded px-2 py-1 text-sm text-white"
          >
            <option value={5}>Show 5</option>
            <option value={10}>Show 10</option>
            <option value={20}>Show 20</option>
          </select>

          {/* Auto refresh */}
          <label className="flex items-center space-x-2 text-sm text-slate-300 cursor-pointer">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
              className="rounded"
            />
            <span>Auto Refresh</span>
          </label>

          {/* Refresh button */}
          <button
            onClick={fetchNews}
            disabled={loading}
            className="btn btn-secondary flex items-center space-x-2"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Error alert */}
      {error && (
        <div className="bg-red-900/50 border border-red-700 rounded-lg p-3 text-red-200">
          {error}
        </div>
      )}

      {/* Loading state */}
      {loading && (
        <div className="text-center py-12 text-slate-400">
          <RefreshCw className="w-8 h-8 animate-spin mx-auto mb-3" />
          <p className="text-lg font-medium mb-2">Fetching financial news...</p>
          <p className="text-sm text-slate-500">Scraping the latest news from CoinDesk and CoinTelegraph</p>
          <p className="text-sm text-slate-500 mt-1">AI analysis in progress, please wait...</p>
        </div>
      )}

      {/* News list */}
      {!loading && news.length === 0 && (
        <div className="text-center py-12 text-slate-400">
          <Newspaper className="w-12 h-12 mx-auto mb-2 opacity-50" />
          <p>No news available</p>
          <p className="text-sm mt-1">Try lowering the star rating filter</p>
        </div>
      )}

      <div className="space-y-3">
        {news.map((item, index) => (
          <div
            key={index}
            className="card hover:border-slate-600 transition-colors"
          >
            {/* News header */}
            <div className="flex items-start justify-between mb-3">
              <div className="flex-1">
                <div className="flex items-center space-x-2 mb-2">
                  {/* Star rating */}
                  <div className="flex items-center space-x-1">
                    {[...Array(item.importance_stars)].map((_, i) => (
                      <Star key={i} className="w-4 h-4 text-yellow-400 fill-yellow-400" />
                    ))}
                  </div>

                  {/* Impact direction */}
                  <div className="flex items-center space-x-1">
                    {getDirectionIcon(item.impact_direction)}
                    <span className={`text-xs font-medium ${
                      item.impact_direction === 'bullish' ? 'text-green-400' :
                      item.impact_direction === 'bearish' ? 'text-red-400' :
                      'text-slate-400'
                    }`}>
                      {getDirectionText(item.impact_direction)}
                    </span>
                  </div>

                  {/* Impact level */}
                  <span className={`text-xs px-2 py-0.5 rounded border ${getImpactColor(item.impact_level)}`}>
                    {getImpactText(item.impact_level)}
                  </span>

                  {/* Source and time */}
                  <span className="text-xs text-slate-500">
                    {item.source} · {formatTime(item.published_at)}
                  </span>
                </div>

                {/* Title */}
                <h3 className="text-white font-medium mb-2 leading-snug">
                  {item.title}
                </h3>

                {/* Summary */}
                {item.summary && (
                  <p className="text-sm text-slate-400 mb-2 line-clamp-2">
                    {item.summary}
                  </p>
                )}

                {/* AI Analysis */}
                <div className="bg-slate-800/50 rounded p-2 mb-2">
                  <div className="flex items-start space-x-2">
                    <span className="text-xs text-primary-400 font-medium">AI Analysis:</span>
                    <p className="text-xs text-slate-300 flex-1">{item.reasoning}</p>
                  </div>

                  {/* Impact score and confidence */}
                  <div className="flex items-center space-x-4 mt-2 text-xs">
                    <div className="flex items-center space-x-1">
                      <span className="text-slate-500">Impact Score:</span>
                      <span className={`font-medium ${
                        item.impact_score > 0 ? 'text-green-400' :
                        item.impact_score < 0 ? 'text-red-400' :
                        'text-slate-400'
                      }`}>
                        {item.impact_score > 0 ? '+' : ''}{item.impact_score.toFixed(2)}
                      </span>
                    </div>
                    <div className="flex items-center space-x-1">
                      <span className="text-slate-500">Confidence:</span>
                      <span className="text-slate-300 font-medium">
                        {(item.confidence * 100).toFixed(0)}%
                      </span>
                    </div>
                  </div>
                </div>

                {/* Key takeaways */}
                {item.key_points && item.key_points.length > 0 && (
                  <div className="space-y-1">
                    {item.key_points.map((point, i) => (
                      <div key={i} className="flex items-start space-x-2 text-xs">
                        <span className="text-primary-400">•</span>
                        <span className="text-slate-400">{point}</span>
                      </div>
                    ))}
                  </div>
                )}

                {/* Affected symbols */}
                {item.affected_symbols && item.affected_symbols.length > 0 && (
                  <div className="flex items-center space-x-2 mt-2">
                    <span className="text-xs text-slate-500">Affected Symbols:</span>
                    <div className="flex flex-wrap gap-1">
                      {item.affected_symbols.map((symbol, i) => (
                        <span
                          key={i}
                          className="text-xs px-2 py-0.5 bg-slate-800 rounded text-slate-300"
                        >
                          {symbol}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* View original article link */}
              <a
                href={item.url}
                target="_blank"
                rel="noopener noreferrer"
                className="ml-4 text-primary-400 hover:text-primary-300 transition-colors"
                title="View Original"
              >
                <ExternalLink className="w-5 h-5" />
              </a>
            </div>
          </div>
        ))}
      </div>

      {/* Statistics */}
      {news.length > 0 && (
        <div className="text-center text-sm text-slate-500">
          Showing {news.length} articles · Min {minStars} stars
        </div>
      )}
    </div>
  )
}

export default NewsPanel

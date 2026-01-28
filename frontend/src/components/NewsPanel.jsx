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

  // 获取AI分析后的新闻
  const fetchNews = async () => {
    setLoading(true)
    setError(null)
    try {
      console.log('开始抓取新闻...')
      const res = await fetch(`${API_BASE}/api/news/analyzed?min_stars=${minStars}&limit=${limit}`)
      if (res.ok) {
        const data = await res.json()
        console.log(`成功获取 ${data.news?.length || 0} 条新闻`)
        setNews(data.news || [])
      } else {
        const errorText = await res.text()
        console.error('新闻 API 错误:', res.status, errorText)
        throw new Error(`新闻加载失败 (${res.status}): ${errorText}`)
      }
    } catch (err) {
      setError(err.message)
      console.error('News fetch error:', err)
    } finally {
      setLoading(false)
    }
  }

  // 初始加载
  useEffect(() => {
    fetchNews()
  }, [minStars, limit])

  // 自动刷新
  useEffect(() => {
    if (!autoRefresh) return
    
    const interval = setInterval(fetchNews, 60000) // 每分钟刷新
    return () => clearInterval(interval)
  }, [autoRefresh, minStars, limit])

  // 影响方向图标
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

  // 影响方向文本
  const getDirectionText = (direction) => {
    switch (direction) {
      case 'bullish':
        return '利好'
      case 'bearish':
        return '利空'
      default:
        return '中性'
    }
  }

  // 影响等级颜色
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

  // 影响等级文本
  const getImpactText = (level) => {
    switch (level) {
      case 'critical':
        return '重大'
      case 'high':
        return '高'
      case 'medium':
        return '中等'
      case 'low':
        return '低'
      default:
        return '无'
    }
  }

  // 格式化时间
  const formatTime = (timestamp) => {
    const date = new Date(timestamp)
    const now = new Date()
    const diff = Math.floor((now - date) / 1000 / 60) // 分钟差

    if (diff < 60) {
      return `${diff}分钟前`
    } else if (diff < 1440) {
      return `${Math.floor(diff / 60)}小时前`
    } else {
      return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
    }
  }

  return (
    <div className="space-y-4">
      {/* 标题和控制 */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <Newspaper className="w-6 h-6 text-primary-400" />
          <h2 className="text-xl font-bold text-white">财经新闻</h2>
          <span className="text-sm text-slate-400">AI分析 + 星级评分</span>
        </div>
        
        <div className="flex items-center space-x-3">
          {/* 星级过滤 */}
          <div className="flex items-center space-x-2">
            <Filter className="w-4 h-4 text-slate-400" />
            <select
              value={minStars}
              onChange={(e) => setMinStars(Number(e.target.value))}
              className="bg-slate-800 border border-slate-700 rounded px-2 py-1 text-sm text-white"
            >
              <option value={1}>1星以上</option>
              <option value={2}>2星以上</option>
              <option value={3}>3星以上</option>
              <option value={4}>4星以上</option>
              <option value={5}>仅5星</option>
            </select>
          </div>

          {/* 数量限制 */}
          <select
            value={limit}
            onChange={(e) => setLimit(Number(e.target.value))}
            className="bg-slate-800 border border-slate-700 rounded px-2 py-1 text-sm text-white"
          >
            <option value={5}>显示5条</option>
            <option value={10}>显示10条</option>
            <option value={20}>显示20条</option>
          </select>

          {/* 自动刷新 */}
          <label className="flex items-center space-x-2 text-sm text-slate-300 cursor-pointer">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
              className="rounded"
            />
            <span>自动刷新</span>
          </label>

          {/* 刷新按钮 */}
          <button
            onClick={fetchNews}
            disabled={loading}
            className="btn btn-secondary flex items-center space-x-2"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            <span>刷新</span>
          </button>
        </div>
      </div>

      {/* 错误提示 */}
      {error && (
        <div className="bg-red-900/50 border border-red-700 rounded-lg p-3 text-red-200">
          {error}
        </div>
      )}

      {/* 加载状态 */}
      {loading && (
        <div className="text-center py-12 text-slate-400">
          <RefreshCw className="w-8 h-8 animate-spin mx-auto mb-3" />
          <p className="text-lg font-medium mb-2">正在抓取财经新闻...</p>
          <p className="text-sm text-slate-500">正在从 CoinDesk 和 CoinTelegraph 抓取最新新闻</p>
          <p className="text-sm text-slate-500 mt-1">AI 分析中，请稍候...</p>
        </div>
      )}

      {/* 新闻列表 */}
      {!loading && news.length === 0 && (
        <div className="text-center py-12 text-slate-400">
          <Newspaper className="w-12 h-12 mx-auto mb-2 opacity-50" />
          <p>暂无新闻</p>
          <p className="text-sm mt-1">尝试降低星级过滤条件</p>
        </div>
      )}

      <div className="space-y-3">
        {news.map((item, index) => (
          <div
            key={index}
            className="card hover:border-slate-600 transition-colors"
          >
            {/* 新闻头部 */}
            <div className="flex items-start justify-between mb-3">
              <div className="flex-1">
                <div className="flex items-center space-x-2 mb-2">
                  {/* 星级 */}
                  <div className="flex items-center space-x-1">
                    {[...Array(item.importance_stars)].map((_, i) => (
                      <Star key={i} className="w-4 h-4 text-yellow-400 fill-yellow-400" />
                    ))}
                  </div>

                  {/* 影响方向 */}
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

                  {/* 影响等级 */}
                  <span className={`text-xs px-2 py-0.5 rounded border ${getImpactColor(item.impact_level)}`}>
                    {getImpactText(item.impact_level)}
                  </span>

                  {/* 来源和时间 */}
                  <span className="text-xs text-slate-500">
                    {item.source} · {formatTime(item.published_at)}
                  </span>
                </div>

                {/* 标题 */}
                <h3 className="text-white font-medium mb-2 leading-snug">
                  {item.title}
                </h3>

                {/* 摘要 */}
                {item.summary && (
                  <p className="text-sm text-slate-400 mb-2 line-clamp-2">
                    {item.summary}
                  </p>
                )}

                {/* AI分析 */}
                <div className="bg-slate-800/50 rounded p-2 mb-2">
                  <div className="flex items-start space-x-2">
                    <span className="text-xs text-primary-400 font-medium">AI分析:</span>
                    <p className="text-xs text-slate-300 flex-1">{item.reasoning}</p>
                  </div>
                  
                  {/* 影响分数和置信度 */}
                  <div className="flex items-center space-x-4 mt-2 text-xs">
                    <div className="flex items-center space-x-1">
                      <span className="text-slate-500">影响分数:</span>
                      <span className={`font-medium ${
                        item.impact_score > 0 ? 'text-green-400' :
                        item.impact_score < 0 ? 'text-red-400' :
                        'text-slate-400'
                      }`}>
                        {item.impact_score > 0 ? '+' : ''}{item.impact_score.toFixed(2)}
                      </span>
                    </div>
                    <div className="flex items-center space-x-1">
                      <span className="text-slate-500">置信度:</span>
                      <span className="text-slate-300 font-medium">
                        {(item.confidence * 100).toFixed(0)}%
                      </span>
                    </div>
                  </div>
                </div>

                {/* 关键要点 */}
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

                {/* 受影响币种 */}
                {item.affected_symbols && item.affected_symbols.length > 0 && (
                  <div className="flex items-center space-x-2 mt-2">
                    <span className="text-xs text-slate-500">影响币种:</span>
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

              {/* 查看原文链接 */}
              <a
                href={item.url}
                target="_blank"
                rel="noopener noreferrer"
                className="ml-4 text-primary-400 hover:text-primary-300 transition-colors"
                title="查看原文"
              >
                <ExternalLink className="w-5 h-5" />
              </a>
            </div>
          </div>
        ))}
      </div>

      {/* 统计信息 */}
      {news.length > 0 && (
        <div className="text-center text-sm text-slate-500">
          共显示 {news.length} 条新闻 · 最低{minStars}星
        </div>
      )}
    </div>
  )
}

export default NewsPanel

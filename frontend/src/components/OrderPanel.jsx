import React, { useState, useEffect } from 'react'
import { Clock, CheckCircle, XCircle, AlertCircle, RefreshCw } from 'lucide-react'

const API_BASE = ''

function OrderPanel() {
  const [orders, setOrders] = useState([])
  const [loading, setLoading] = useState(false)
  const [filter, setFilter] = useState('all')

  const fetchOrders = async () => {
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/api/orders`)
      if (res.ok) {
        const data = await res.json()
        setOrders(data)
      }
    } catch (err) {
      console.error('Failed to fetch orders:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchOrders()
    const interval = setInterval(fetchOrders, 10000)
    return () => clearInterval(interval)
  }, [])

  const filteredOrders = orders.filter(order => {
    if (filter === 'all') return true
    if (filter === 'active') return ['pending', 'submitted', 'partial_filled'].includes(order.status)
    if (filter === 'filled') return order.status === 'filled'
    if (filter === 'cancelled') return ['cancelled', 'rejected'].includes(order.status)
    return true
  })

  const statusConfig = {
    pending: { icon: Clock, color: 'text-slate-400', label: '待提交' },
    submitted: { icon: Clock, color: 'text-amber-400', label: '已提交' },
    partial_filled: { icon: AlertCircle, color: 'text-amber-400', label: '部分成交' },
    filled: { icon: CheckCircle, color: 'text-emerald-400', label: '已成交' },
    cancelled: { icon: XCircle, color: 'text-slate-400', label: '已取消' },
    rejected: { icon: XCircle, color: 'text-red-400', label: '被拒绝' },
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold">订单记录</h2>
        <div className="flex items-center space-x-4">
          <div className="flex space-x-2">
            {['all', 'active', 'filled', 'cancelled'].map(f => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`px-3 py-1 text-sm rounded-lg transition-colors ${
                  filter === f 
                    ? 'bg-primary-600 text-white' 
                    : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                }`}
              >
                {f === 'all' ? '全部' : f === 'active' ? '活跃' : f === 'filled' ? '已成交' : '已取消'}
              </button>
            ))}
          </div>
          <button 
            onClick={fetchOrders}
            className="btn btn-secondary"
            disabled={loading}
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {filteredOrders.length === 0 ? (
        <div className="card text-center py-12">
          <p className="text-slate-400">暂无订单记录</p>
          <p className="text-sm text-slate-500 mt-2">当策略执行交易时，订单将显示在这里</p>
        </div>
      ) : (
        <div className="card overflow-hidden">
          <div className="table-container">
            <table className="data-table">
              <thead>
                <tr>
                  <th>订单ID</th>
                  <th>交易对</th>
                  <th>方向</th>
                  <th>类型</th>
                  <th>价格</th>
                  <th>数量</th>
                  <th>成交量</th>
                  <th>状态</th>
                  <th>手续费</th>
                  <th>创建时间</th>
                </tr>
              </thead>
              <tbody>
                {filteredOrders.map((order) => {
                  const status = statusConfig[order.status] || statusConfig.pending
                  const StatusIcon = status.icon
                  
                  return (
                    <tr key={order.id}>
                      <td className="font-mono text-xs">{order.id?.slice(0, 8)}...</td>
                      <td className="font-medium">{order.symbol}</td>
                      <td>
                        <span className={order.side === 'buy' ? 'text-emerald-400' : 'text-red-400'}>
                          {order.side === 'buy' ? '买入' : '卖出'}
                        </span>
                      </td>
                      <td className="text-slate-400">
                        {order.type === 'limit' ? '限价' : order.type === 'market' ? '市价' : order.type}
                      </td>
                      <td>${order.price?.toLocaleString()}</td>
                      <td>{order.size?.toFixed(4)}</td>
                      <td>{order.filled_size?.toFixed(4)}</td>
                      <td>
                        <span className={`flex items-center space-x-1 ${status.color}`}>
                          <StatusIcon className="w-4 h-4" />
                          <span>{status.label}</span>
                        </span>
                      </td>
                      <td className="text-slate-400">${order.fee?.toFixed(4) || '0'}</td>
                      <td className="text-slate-400 text-sm">
                        {new Date(order.created_at).toLocaleString()}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* 订单统计 */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="card">
          <p className="text-slate-400 text-sm">总订单数</p>
          <p className="text-2xl font-bold mt-1">{orders.length}</p>
        </div>
        <div className="card">
          <p className="text-slate-400 text-sm">已成交</p>
          <p className="text-2xl font-bold mt-1 text-emerald-400">
            {orders.filter(o => o.status === 'filled').length}
          </p>
        </div>
        <div className="card">
          <p className="text-slate-400 text-sm">成交率</p>
          <p className="text-2xl font-bold mt-1">
            {orders.length > 0 
              ? ((orders.filter(o => o.status === 'filled').length / orders.length) * 100).toFixed(1)
              : 0}%
          </p>
        </div>
        <div className="card">
          <p className="text-slate-400 text-sm">总手续费</p>
          <p className="text-2xl font-bold mt-1 text-amber-400">
            ${orders.reduce((sum, o) => sum + (o.fee || 0), 0).toFixed(4)}
          </p>
        </div>
      </div>
    </div>
  )
}

export default OrderPanel

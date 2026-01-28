import React, { useState, useEffect, useRef } from 'react';
import './DecisionFlowMatrix.css';

const DecisionFlowMatrix = () => {
  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [zoom, setZoom] = useState(0.8);  // 缩放比例，默认0.8 (80%)
  const canvasRef = useRef(null);

  // 节点定义 - 横向布局
  const layers = [
    {
      id: 'dataLayer',
      title: 'DATA',
      subtitle: '数据层',
      nodes: [
        { id: 'marketData', label: '行情', icon: '📊', expandable: true },
        { id: 'newsData', label: '新闻', icon: '📰', expandable: true },
        { id: 'socialMedia', label: '社交', icon: '💬', expandable: true },
        { id: 'onchainData', label: '链上', icon: '⛓️', expandable: true },
        { id: 'technicalIndicators', label: '指标', icon: '📈', expandable: true }
      ]
    },
    {
      id: 'aiLayer',
      title: 'AI',
      subtitle: 'AI分析',
      nodes: [
        { id: 'sentimentAnalysis', label: '情绪', icon: '😊' },
        { id: 'multiAgent', label: 'Agent', icon: '🤖', expandable: true },
        { id: 'newsAnalysis', label: '分析', icon: '📋' },
        { id: 'whaleTracking', label: '鲸鱼', icon: '🐋' }
      ]
    },
    {
      id: 'rulesLayer',
      title: 'RULES',
      subtitle: '规则',
      nodes: [
        { id: 'vibeRules', label: 'Vibe', icon: '⚡', expandable: true }
      ]
    },
    {
      id: 'riskLayer',
      title: 'RISK',
      subtitle: '风控',
      nodes: [
        { id: 'riskControl', label: '风控', icon: '🛡️', expandable: true }
      ]
    },
    {
      id: 'executeLayer',
      title: 'EXEC',
      subtitle: '执行',
      nodes: [
        { id: 'executeTrade', label: '交易', icon: '⚙️' }
      ]
    }
  ];

  // 加载配置
  useEffect(() => {
    fetchConfig();
    syncVibeRules();
  }, []);

  // 动画效果
  useEffect(() => {
    if (!canvasRef.current) return;
    
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    
    // 设置canvas尺寸
    const resizeCanvas = () => {
      canvas.width = canvas.offsetWidth;
      canvas.height = canvas.offsetHeight;
    };
    resizeCanvas();
    window.addEventListener('resize', resizeCanvas);

    // 粒子系统
    const particles = [];
    const particleCount = 30;
    
    for (let i = 0; i < particleCount; i++) {
      particles.push({
        x: Math.random() * canvas.width,
        y: Math.random() * canvas.height,
        vx: 0.5 + Math.random() * 1,
        vy: (Math.random() - 0.5) * 0.5,
        size: 1 + Math.random() * 2,
        opacity: 0.3 + Math.random() * 0.7
      });
    }

    // 动画循环
    let animationId;
    const animate = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      // 绘制扫描线
      const scanLineY = (Date.now() / 20) % canvas.height;
      const gradient = ctx.createLinearGradient(0, scanLineY - 50, 0, scanLineY + 50);
      gradient.addColorStop(0, 'rgba(0, 255, 255, 0)');
      gradient.addColorStop(0.5, 'rgba(0, 255, 255, 0.1)');
      gradient.addColorStop(1, 'rgba(0, 255, 255, 0)');
      ctx.fillStyle = gradient;
      ctx.fillRect(0, scanLineY - 50, canvas.width, 100);

      // 更新和绘制粒子
      particles.forEach(particle => {
        particle.x += particle.vx;
        particle.y += particle.vy;

        if (particle.x > canvas.width) particle.x = 0;
        if (particle.y < 0) particle.y = canvas.height;
        if (particle.y > canvas.height) particle.y = 0;

        ctx.beginPath();
        ctx.arc(particle.x, particle.y, particle.size, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(0, 255, 255, ${particle.opacity})`;
        ctx.fill();

        // 绘制粒子轨迹
        ctx.beginPath();
        ctx.moveTo(particle.x, particle.y);
        ctx.lineTo(particle.x - particle.vx * 10, particle.y - particle.vy * 10);
        ctx.strokeStyle = `rgba(0, 255, 255, ${particle.opacity * 0.3})`;
        ctx.lineWidth = particle.size * 0.5;
        ctx.stroke();
      });

      animationId = requestAnimationFrame(animate);
    };
    animate();

    return () => {
      window.removeEventListener('resize', resizeCanvas);
      cancelAnimationFrame(animationId);
    };
  }, []);

  const fetchConfig = async () => {
    try {
      setLoading(true);
      const response = await fetch('/api/decision-flow/config');
      const data = await response.json();
      if (data.success) {
        setConfig(data.config);
      }
    } catch (error) {
      console.error('Failed to fetch config:', error);
    } finally {
      setLoading(false);
    }
  };

  const syncVibeRules = async () => {
    try {
      await fetch('/api/decision-flow/sync-vibe-rules', { method: 'POST' });
      // 同步后重新加载配置
      setTimeout(fetchConfig, 500);
    } catch (error) {
      console.error('Failed to sync vibe rules:', error);
    }
  };

  const toggleMasterSwitch = async () => {
    try {
      setSaving(true);
      const newValue = !config.master_switch;
      const response = await fetch('/api/decision-flow/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ master_switch: newValue })
      });
      const data = await response.json();
      if (data.success) {
        setConfig(data.config);
      }
    } finally {
      setSaving(false);
    }
  };

  const toggleNode = async (nodeId) => {
    try {
      const response = await fetch(`/api/decision-flow/toggle/${nodeId}`, {
        method: 'POST'
      });
      const data = await response.json();
      if (data.success) {
        await fetchConfig();
      }
    } catch (error) {
      console.error('Failed to toggle node:', error);
    }
  };

  const toggleSubNode = async (nodeId, subNodeId) => {
    try {
      const response = await fetch(`/api/decision-flow/toggle/${nodeId}/${subNodeId}`, {
        method: 'POST'
      });
      const data = await response.json();
      if (data.success) {
        await fetchConfig();
      }
    } catch (error) {
      console.error('Failed to toggle sub node:', error);
    }
  };

  const resetConfig = async () => {
    if (!confirm('确定要重置为默认配置吗？')) return;
    
    try {
      setSaving(true);
      const response = await fetch('/api/decision-flow/reset', {
        method: 'POST'
      });
      const data = await response.json();
      if (data.success) {
        setConfig(data.config);
      }
    } finally {
      setSaving(false);
    }
  };

  const renderNode = (node, layerIndex) => {
    if (!config) return null;

    const nodeConfig = config.nodes[node.id];
    if (!nodeConfig) return null;

    const isEnabled = config.master_switch ? nodeConfig.enabled : true;
    const hasSubNodes = nodeConfig.sub_nodes && nodeConfig.sub_nodes.length > 0;

    return (
      <div key={node.id} className="h-node-wrapper">
        <div
          className={`h-node ${isEnabled ? 'enabled' : 'disabled'} ${!config.master_switch ? 'always-enabled' : ''}`}
          onClick={() => config.master_switch && toggleNode(node.id)}
          style={{ cursor: config.master_switch ? 'pointer' : 'default' }}
        >
          <div className="h-node-icon">{node.icon}</div>
          <div className="h-node-label">{node.label}</div>
          <div className="h-node-status">{isEnabled ? '●' : '○'}</div>
          {isEnabled && <div className="h-node-pulse"></div>}
        </div>

        {/* 子节点 - 在右侧显示 */}
        {hasSubNodes && (
          <div className="h-sub-nodes">
            {nodeConfig.sub_nodes.map((subNode, idx) => (
              <div
                key={subNode.id}
                className={`h-sub-node ${subNode.enabled && isEnabled ? 'enabled' : 'disabled'} ${!config.master_switch ? 'always-enabled' : ''}`}
                onClick={(e) => {
                  e.stopPropagation();
                  if (config.master_switch && isEnabled) {
                    toggleSubNode(node.id, subNode.id);
                  }
                }}
                style={{ 
                  animationDelay: `${idx * 0.05}s`,
                  cursor: config.master_switch && isEnabled ? 'pointer' : 'default'
                }}
              >
                <div className="h-sub-node-dot">{subNode.enabled && isEnabled ? '●' : '○'}</div>
                <div 
                  className="h-sub-node-name" 
                  title={subNode.name}  /* 鼠标悬停显示完整内容 */
                >
                  {subNode.name.length > 8 ? subNode.name.substring(0, 8) + '...' : subNode.name}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  };

  const renderLayer = (layer, index) => {
    return (
      <div key={layer.id} className="h-layer" style={{ animationDelay: `${index * 0.1}s` }}>
        <div className="h-layer-header">
          <div className="h-layer-title">{layer.title}</div>
          <div className="h-layer-subtitle">{layer.subtitle}</div>
        </div>
        <div className="h-layer-nodes">
          {layer.nodes.map(node => renderNode(node, index))}
        </div>
      </div>
    );
  };

  if (loading) {
    return (
      <div className="decision-flow-matrix horizontal">
        <div className="loading-spinner">
          <div className="spinner"></div>
          <div>Loading Decision Flow...</div>
        </div>
      </div>
    );
  }

  if (!config) {
    return (
      <div className="decision-flow-matrix horizontal">
        <div className="error">Failed to load configuration</div>
      </div>
    );
  }

  const enabledCount = Object.values(config.nodes).filter(n => n.enabled).length;
  const totalCount = Object.keys(config.nodes).length;

  return (
    <div className="decision-flow-matrix horizontal">
      {/* 动画画布 */}
      <canvas ref={canvasRef} className="flow-canvas-bg"></canvas>

      {/* 顶部控制栏 */}
      <div className="h-header">
        <div className="h-header-left">
          <div className="h-title">DECISION FLOW MATRIX</div>
          <div className="h-subtitle">
            {config.master_switch ? '⚡ CUSTOM MODE ACTIVE' : '💤 DEFAULT MODE'}
          </div>
        </div>
        <div className="h-header-right">
          <div className="h-stats">
            <div className="h-stat">
              <span className="h-stat-label">MODULES</span>
              <span className="h-stat-value">{enabledCount}/{totalCount}</span>
            </div>
          </div>
          <div
            className={`h-master-switch ${config.master_switch ? 'on' : 'off'}`}
            onClick={toggleMasterSwitch}
          >
            <div className="h-switch-slider"></div>
            <div className="h-switch-text">{config.master_switch ? 'ON' : 'OFF'}</div>
          </div>
          <button className="h-reset-btn" onClick={resetConfig} disabled={saving}>
            <span>⟲</span>
          </button>
        </div>
      </div>

      {/* 横向流程 */}
      <div 
        className="h-flow-container"
        style={{
          transform: `scale(${zoom})`,
          transformOrigin: 'top left',
          width: `${100 / zoom}%`,  /* 调整容器宽度以适应缩放 */
          height: `${100 / zoom}%`  /* 调整容器高度以适应缩放 */
        }}
      >
        {layers.map((layer, index) => (
          <React.Fragment key={layer.id}>
            {renderLayer(layer, index)}
            {index < layers.length - 1 && (
              <div className="h-connector">
                <div className="h-connector-line"></div>
                <div className="h-connector-arrow">▶</div>
                <div className="h-connector-flow"></div>
              </div>
            )}
          </React.Fragment>
        ))}
      </div>

      {/* 缩放控制按钮 */}
      <div className="h-zoom-controls">
        <button 
          className="h-zoom-btn"
          onClick={() => setZoom(Math.min(zoom + 0.1, 2.0))}
          title="放大"
        >
          +
        </button>
        <div className="h-zoom-level">{Math.round(zoom * 100)}%</div>
        <button 
          className="h-zoom-btn"
          onClick={() => setZoom(Math.max(zoom - 0.1, 0.5))}
          title="缩小"
        >
          −
        </button>
        <button 
          className="h-zoom-btn h-zoom-reset"
          onClick={() => setZoom(1.0)}
          title="重置缩放"
        >
          ↺
        </button>
      </div>

    </div>
  );
};

export default DecisionFlowMatrix;

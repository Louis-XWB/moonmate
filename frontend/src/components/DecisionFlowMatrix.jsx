import React, { useState, useEffect, useRef } from 'react';
import './DecisionFlowMatrix.css';

const DecisionFlowMatrix = () => {
  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [zoom, setZoom] = useState(0.8);  // Zoom ratio, default 0.8 (80%)
  const canvasRef = useRef(null);

  // Node definitions - horizontal layout
  const layers = [
    {
      id: 'dataLayer',
      title: 'DATA',
      subtitle: 'Data Layer',
      nodes: [
        { id: 'marketData', label: 'Market', icon: '📊', expandable: true },
        { id: 'newsData', label: 'News', icon: '📰', expandable: true },
        { id: 'socialMedia', label: 'Social', icon: '💬', expandable: true },
        { id: 'onchainData', label: 'On-chain', icon: '⛓️', expandable: true },
        { id: 'technicalIndicators', label: 'Indicators', icon: '📈', expandable: true }
      ]
    },
    {
      id: 'aiLayer',
      title: 'AI',
      subtitle: 'AI Analysis',
      nodes: [
        { id: 'sentimentAnalysis', label: 'Sentiment', icon: '😊' },
        { id: 'multiAgent', label: 'Agent', icon: '🤖', expandable: true },
        { id: 'newsAnalysis', label: 'Analysis', icon: '📋' },
        { id: 'whaleTracking', label: 'Whale', icon: '🐋' }
      ]
    },
    {
      id: 'rulesLayer',
      title: 'RULES',
      subtitle: 'Rules',
      nodes: [
        { id: 'vibeRules', label: 'Vibe', icon: '⚡', expandable: true }
      ]
    },
    {
      id: 'riskLayer',
      title: 'RISK',
      subtitle: 'Risk Control',
      nodes: [
        { id: 'riskControl', label: 'Risk', icon: '🛡️', expandable: true }
      ]
    },
    {
      id: 'executeLayer',
      title: 'EXEC',
      subtitle: 'Execution',
      nodes: [
        { id: 'executeTrade', label: 'Trade', icon: '⚙️' }
      ]
    }
  ];

  // Load configuration
  useEffect(() => {
    fetchConfig();
    syncVibeRules();
  }, []);

  // Animation effects
  useEffect(() => {
    if (!canvasRef.current) return;

    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');

    // Set canvas dimensions
    const resizeCanvas = () => {
      canvas.width = canvas.offsetWidth;
      canvas.height = canvas.offsetHeight;
    };
    resizeCanvas();
    window.addEventListener('resize', resizeCanvas);

    // Particle system
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

    // Animation loop
    let animationId;
    const animate = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      // Draw scan line
      const scanLineY = (Date.now() / 20) % canvas.height;
      const gradient = ctx.createLinearGradient(0, scanLineY - 50, 0, scanLineY + 50);
      gradient.addColorStop(0, 'rgba(0, 255, 255, 0)');
      gradient.addColorStop(0.5, 'rgba(0, 255, 255, 0.1)');
      gradient.addColorStop(1, 'rgba(0, 255, 255, 0)');
      ctx.fillStyle = gradient;
      ctx.fillRect(0, scanLineY - 50, canvas.width, 100);

      // Update and draw particles
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

        // Draw particle trails
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
      // Reload configuration after sync
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
    if (!confirm('Are you sure you want to reset to default configuration?')) return;

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

        {/* Sub-nodes - displayed on the right */}
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
                  title={subNode.name}  /* Show full content on hover */
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
      {/* Animation canvas */}
      <canvas ref={canvasRef} className="flow-canvas-bg"></canvas>

      {/* Top control bar */}
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

      {/* Horizontal flow */}
      <div
        className="h-flow-container"
        style={{
          transform: `scale(${zoom})`,
          transformOrigin: 'top left',
          width: `${100 / zoom}%`,  /* Adjust container width to fit zoom */
          height: `${100 / zoom}%`  /* Adjust container height to fit zoom */
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

      {/* Zoom control buttons */}
      <div className="h-zoom-controls">
        <button
          className="h-zoom-btn"
          onClick={() => setZoom(Math.min(zoom + 0.1, 2.0))}
          title="Zoom In"
        >
          +
        </button>
        <div className="h-zoom-level">{Math.round(zoom * 100)}%</div>
        <button
          className="h-zoom-btn"
          onClick={() => setZoom(Math.max(zoom - 0.1, 0.5))}
          title="Zoom Out"
        >
          −
        </button>
        <button
          className="h-zoom-btn h-zoom-reset"
          onClick={() => setZoom(1.0)}
          title="Reset Zoom"
        >
          ↺
        </button>
      </div>

    </div>
  );
};

export default DecisionFlowMatrix;

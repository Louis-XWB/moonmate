import React, { useState, useEffect } from 'react';
import { RefreshCw, Users, TrendingUp, TrendingDown, Minus, AlertCircle, CheckCircle } from 'lucide-react';

const MultiAgentPanel = () => {
  const [consensus, setConsensus] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [autoRefresh, setAutoRefresh] = useState(false);

  const fetchConsensus = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch('http://localhost:8000/api/multi-agent/deliberate?symbol=BTC/USDT');
      const result = await response.json();
      if (result.success) {
        setConsensus(result.data);
      } else {
        setError('Failed to fetch consensus');
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchConsensus();
  }, []);

  useEffect(() => {
    if (autoRefresh) {
      const interval = setInterval(fetchConsensus, 60000); // Refresh every minute
      return () => clearInterval(interval);
    }
  }, [autoRefresh]);

  const getDecisionIcon = (decision) => {
    switch (decision) {
      case 'strong_long':
      case 'long':
        return <TrendingUp className="w-5 h-5 text-green-400" />;
      case 'strong_short':
      case 'short':
        return <TrendingDown className="w-5 h-5 text-red-400" />;
      default:
        return <Minus className="w-5 h-5 text-gray-400" />;
    }
  };

  const getDecisionColor = (decision) => {
    switch (decision) {
      case 'strong_long':
        return 'text-green-400 bg-green-900/30 border-green-500/50';
      case 'long':
        return 'text-green-300 bg-green-900/20 border-green-500/30';
      case 'strong_short':
        return 'text-red-400 bg-red-900/30 border-red-500/50';
      case 'short':
        return 'text-red-300 bg-red-900/20 border-red-500/30';
      default:
        return 'text-gray-400 bg-gray-900/30 border-gray-500/50';
    }
  };

  const getDecisionText = (decision) => {
    const map = {
      'strong_long': 'Strong Long',
      'long': 'Long',
      'hold': 'Hold',
      'short': 'Short',
      'strong_short': 'Strong Short'
    };
    return map[decision] || decision;
  };

  const getAgentEmoji = (role) => {
    const map = {
      'news_analyst': '📰',
      'technical_analyst': '📊',
      'onchain_analyst': '🔗',
      'risk_manager': '🛡️',
      'decision_maker': '🎯'
    };
    return map[role] || '🤖';
  };

  return (
    <div className="space-y-6">
      {/* Title and controls */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Users className="w-6 h-6 text-purple-400" />
          <h2 className="text-2xl font-bold text-white">AI Committee</h2>
          <span className="px-3 py-1 text-xs font-semibold text-purple-300 bg-purple-900/30 border border-purple-500/50 rounded-full">
            Experimental
          </span>
        </div>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-sm text-gray-300 cursor-pointer">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
              className="w-4 h-4 text-purple-600 bg-gray-700 border-gray-600 rounded focus:ring-purple-500"
            />
            Auto Refresh
          </label>
          <button
            onClick={fetchConsensus}
            disabled={loading}
            className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-purple-600 rounded-lg hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
      </div>

      {/* Error alert */}
      {error && (
        <div className="flex items-center gap-2 p-4 text-red-300 bg-red-900/20 border border-red-500/50 rounded-lg">
          <AlertCircle className="w-5 h-5" />
          <span>{error}</span>
        </div>
      )}

      {/* Loading state */}
      {loading && !consensus && (
        <div className="flex items-center justify-center p-12">
          <div className="flex flex-col items-center gap-3">
            <RefreshCw className="w-8 h-8 text-purple-400 animate-spin" />
            <p className="text-gray-400">AI Committee is deliberating...</p>
          </div>
        </div>
      )}

      {/* Consensus results */}
      {consensus && (
        <div className="space-y-6">
          {/* Final decision card */}
          <div className="p-6 bg-gradient-to-br from-purple-900/40 to-blue-900/40 border border-purple-500/50 rounded-xl">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-white">🎯 Final Decision</h3>
              <div className="flex items-center gap-2">
                <CheckCircle className="w-5 h-5 text-green-400" />
                <span className="text-sm text-gray-300">
                  {new Date(consensus.timestamp).toLocaleString('en-US')}
                </span>
              </div>
            </div>

            <div className="flex items-center gap-4 mb-4">
              <div className={`flex items-center gap-2 px-4 py-2 border rounded-lg ${getDecisionColor(consensus.final_decision)}`}>
                {getDecisionIcon(consensus.final_decision)}
                <span className="text-lg font-bold">{getDecisionText(consensus.final_decision)}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-sm text-gray-400">Confidence:</span>
                <div className="flex items-center gap-2">
                  <div className="w-32 h-2 bg-gray-700 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-purple-500 to-blue-500 transition-all duration-500"
                      style={{ width: `${consensus.confidence * 100}%` }}
                    />
                  </div>
                  <span className="text-sm font-semibold text-white">{(consensus.confidence * 100).toFixed(0)}%</span>
                </div>
              </div>
            </div>

            <div className="p-4 bg-black/30 rounded-lg">
              <p className="text-sm text-gray-300">{consensus.debate_summary}</p>
            </div>

            {/* Vote distribution */}
            <div className="mt-4 flex items-center gap-4">
              <span className="text-sm text-gray-400">Vote Distribution:</span>
              <div className="flex items-center gap-2">
                {Object.entries(consensus.vote_distribution).map(([decision, count]) => (
                  <div key={decision} className="flex items-center gap-1 px-2 py-1 bg-gray-800/50 rounded">
                    <span className="text-xs text-gray-400">{getDecisionText(decision)}:</span>
                    <span className="text-xs font-semibold text-white">{count}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Agent opinions list */}
          <div className="space-y-3">
            <h3 className="text-lg font-semibold text-white">🗳️ Agent Opinions</h3>
            {consensus.agent_opinions.map((opinion, index) => (
              <div
                key={index}
                className="p-4 bg-gray-800/50 border border-gray-700 rounded-lg hover:border-purple-500/50 transition-colors"
              >
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center gap-3">
                    <span className="text-2xl">{getAgentEmoji(opinion.agent_role)}</span>
                    <div>
                      <h4 className="font-semibold text-white">{opinion.agent_name}</h4>
                      <p className="text-xs text-gray-400">{opinion.agent_role}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className={`flex items-center gap-2 px-3 py-1 border rounded-lg ${getDecisionColor(opinion.decision)}`}>
                      {getDecisionIcon(opinion.decision)}
                      <span className="text-sm font-semibold">{getDecisionText(opinion.decision)}</span>
                    </div>
                    <div className="text-right">
                      <p className="text-xs text-gray-400">Confidence</p>
                      <p className="text-sm font-semibold text-white">{(opinion.confidence * 100).toFixed(0)}%</p>
                    </div>
                  </div>
                </div>

                <div className="mb-3 p-3 bg-black/30 rounded">
                  <p className="text-sm text-gray-300">{opinion.reasoning}</p>
                </div>

                {opinion.key_points && opinion.key_points.length > 0 && (
                  <div className="space-y-1">
                    {opinion.key_points.map((point, idx) => (
                      <div key={idx} className="flex items-start gap-2">
                        <span className="text-purple-400 mt-1">•</span>
                        <p className="text-sm text-gray-400">{point}</p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default MultiAgentPanel;

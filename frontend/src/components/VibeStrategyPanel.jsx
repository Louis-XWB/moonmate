import React, { useState, useEffect } from 'react';

const VibeStrategyPanel = () => {
  const [rules, setRules] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [newRuleContent, setNewRuleContent] = useState('');
  const [editingRule, setEditingRule] = useState(null);
  const [editContent, setEditContent] = useState('');

  // Get all rules
  const fetchRules = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch('http://localhost:8000/api/vibe/rules');
      const data = await response.json();
      if (data.success) {
        setRules(data.rules);
      } else {
        setError('GetRuleFailed');
      }
    } catch (err) {
      setError(`GetRuleFailed: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  // Add new rule
  const addRule = async () => {
    if (!newRuleContent.trim()) {
      alert('Please enter rule content');
      return;
    }

    try {
      const response = await fetch('http://localhost:8000/api/vibe/rules', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ content: newRuleContent }),
      });
      const data = await response.json();
      if (data.success) {
        setNewRuleContent('');
        fetchRules();
      } else {
        alert('Failed to add rule');
      }
    } catch (err) {
      alert(`Failed to add rule: ${err.message}`);
    }
  };

  // Update rule
  const updateRule = async (ruleId, content, enabled) => {
    try {
      const response = await fetch(`http://localhost:8000/api/vibe/rules/${ruleId}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ content, enabled }),
      });
      const data = await response.json();
      if (data.success) {
        setEditingRule(null);
        setEditContent('');
        fetchRules();
      } else {
        alert('Update ruleFailed');
      }
    } catch (err) {
      alert(`Update ruleFailed: ${err.message}`);
    }
  };

  // Delete rule
  const deleteRule = async (ruleId) => {
    if (!confirm('Are you sure you want to delete this rule?')) {
      return;
    }

    try {
      const response = await fetch(`http://localhost:8000/api/vibe/rules/${ruleId}`, {
        method: 'DELETE',
      });
      const data = await response.json();
      if (data.success) {
        fetchRules();
      } else {
        alert('Delete ruleFailed');
      }
    } catch (err) {
      alert(`Delete ruleFailed: ${err.message}`);
    }
  };

  // ToggleEnabled/Disabled
  const toggleEnabled = async (rule) => {
    await updateRule(rule.id, rule.content, !rule.enabled);
  };

  // Start editing
  const startEdit = (rule) => {
    setEditingRule(rule.id);
    setEditContent(rule.content);
  };

  // SaveEdit
  const saveEdit = async (rule) => {
    await updateRule(rule.id, editContent, rule.enabled);
  };

  // Cancel edit
  const cancelEdit = () => {
    setEditingRule(null);
    setEditContent('');
  };

  useEffect(() => {
    fetchRules();
  }, []);

  return (
    <div className="p-6 space-y-6">
      {/* Title and Description */}
      <div className="bg-gradient-to-r from-purple-900/50 to-pink-900/50 rounded-lg p-6 border border-purple-500/30">
        <h2 className="text-2xl font-bold text-white mb-2">🎯 Vibe Strategy Preferences</h2>
        <p className="text-gray-300 text-sm">
          Customize your trading strategy preferences. The AI will strictly follow these rules when generating trading signals.
          You can add any trading ideas, preferences, or constraint conditions you want.
        </p>
      </div>

      {/* Add new rule */}
      <div className="bg-gray-800/50 rounded-lg p-6 border border-gray-700">
        <h3 className="text-lg font-semibold text-white mb-4">➕ Add new rule</h3>
        <div className="flex gap-3">
          <input
            type="text"
            value={newRuleContent}
            onChange={(e) => setNewRuleContent(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && addRule()}
            placeholder="e.g., I prefer going long, avoid shorting"
            className="flex-1 bg-gray-900 text-white px-4 py-3 rounded-lg border border-gray-600 focus:border-purple-500 focus:outline-none"
          />
          <button
            onClick={addRule}
            className="bg-purple-600 hover:bg-purple-700 text-white px-6 py-3 rounded-lg font-medium transition-colors"
          >
            Add
          </button>
        </div>
      </div>

      {/* RuleList */}
      <div className="bg-gray-800/50 rounded-lg p-6 border border-gray-700">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-white">📋 My Strategy Rules</h3>
          <button
            onClick={fetchRules}
            className="text-gray-400 hover:text-white transition-colors"
          >
            🔄 Refresh
          </button>
        </div>

        {loading && (
          <div className="text-center py-8 text-gray-400">
            <div className="animate-spin inline-block w-8 h-8 border-4 border-purple-500 border-t-transparent rounded-full"></div>
            <p className="mt-2">Loading...</p>
          </div>
        )}

        {error && (
          <div className="bg-red-900/30 border border-red-500 text-red-300 px-4 py-3 rounded-lg">
            {error}
          </div>
        )}

        {!loading && !error && rules.length === 0 && (
          <div className="text-center py-8 text-gray-400">
            <p>No rules added yet</p>
            <p className="text-sm mt-2">Click "Add New Rule" above to start creating your strategy preferences</p>
          </div>
        )}

        {!loading && !error && rules.length > 0 && (
          <div className="space-y-3">
            {rules.map((rule, index) => (
              <div
                key={rule.id}
                className={`bg-gray-900/50 rounded-lg p-4 border ${
                  rule.enabled ? 'border-purple-500/50' : 'border-gray-600'
                } transition-all`}
              >
                <div className="flex items-start gap-3">
                  {/* Enable/disable toggle */}
                  <button
                    onClick={() => toggleEnabled(rule)}
                    className={`mt-1 w-12 h-6 rounded-full transition-colors ${
                      rule.enabled ? 'bg-purple-600' : 'bg-gray-600'
                    }`}
                  >
                    <div
                      className={`w-5 h-5 bg-white rounded-full transition-transform ${
                        rule.enabled ? 'translate-x-6' : 'translate-x-1'
                      }`}
                    ></div>
                  </button>

                  {/* Rule content */}
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="text-purple-400 font-mono text-sm">#{index + 1}</span>
                      <span
                        className={`px-2 py-1 rounded text-xs ${
                          rule.enabled
                            ? 'bg-green-900/50 text-green-300'
                            : 'bg-gray-700 text-gray-400'
                        }`}
                      >
                        {rule.enabled ? '✓ Enabled' : '✗ Disabled'}
                      </span>
                    </div>

                    {editingRule === rule.id ? (
                      <div className="space-y-2">
                        <textarea
                          value={editContent}
                          onChange={(e) => setEditContent(e.target.value)}
                          className="w-full bg-gray-800 text-white px-3 py-2 rounded border border-gray-600 focus:border-purple-500 focus:outline-none"
                          rows="2"
                        />
                        <div className="flex gap-2">
                          <button
                            onClick={() => saveEdit(rule)}
                            className="bg-green-600 hover:bg-green-700 text-white px-3 py-1 rounded text-sm"
                          >
                            Save
                          </button>
                          <button
                            onClick={cancelEdit}
                            className="bg-gray-600 hover:bg-gray-700 text-white px-3 py-1 rounded text-sm"
                          >
                            Cancel
                          </button>
                        </div>
                      </div>
                    ) : (
                      <p className={`${rule.enabled ? 'text-white' : 'text-gray-500'}`}>
                        {rule.content}
                      </p>
                    )}

                    <div className="flex items-center gap-4 mt-2 text-xs text-gray-500">
                      <span>Created: {new Date(rule.created_at).toLocaleString('en-US')}</span>
                      {rule.updated_at !== rule.created_at && (
                        <span>Updated: {new Date(rule.updated_at).toLocaleString('en-US')}</span>
                      )}
                    </div>
                  </div>

                  {/* Action buttons */}
                  {editingRule !== rule.id && (
                    <div className="flex gap-2">
                      <button
                        onClick={() => startEdit(rule)}
                        className="text-blue-400 hover:text-blue-300 transition-colors"
                        title="Edit"
                      >
                        ✏️
                      </button>
                      <button
                        onClick={() => deleteRule(rule.id)}
                        className="text-red-400 hover:text-red-300 transition-colors"
                        title="Delete"
                      >
                        🗑️
                      </button>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* StatisticsInfo */}
      {rules.length > 0 && (
        <div className="bg-gray-800/50 rounded-lg p-4 border border-gray-700">
          <div className="flex items-center justify-between text-sm">
            <span className="text-gray-400">Total rules: {rules.length}</span>
            <span className="text-gray-400">
              Enabled: {rules.filter((r) => r.enabled).length}
            </span>
            <span className="text-gray-400">
              Disabled: {rules.filter((r) => !r.enabled).length}
            </span>
          </div>
        </div>
      )}

      {/* Usage Instructions */}
      <div className="bg-blue-900/20 border border-blue-500/30 rounded-lg p-4">
        <h4 className="text-blue-300 font-semibold mb-2">💡 Usage Tips</h4>
        <ul className="text-blue-200 text-sm space-y-1 list-disc list-inside">
          <li>Rules can be any strategy preference described in natural language</li>
          <li>AI will strictly follow these rules with higher priority than other analysis</li>
          <li>You can add, edit, delete, or disable rules at any time</li>
          <li>Disabled rules won't be sent to AI but will remain in the list</li>
          <li>ExampleRule: 
            <ul className="ml-6 mt-1 space-y-1">
              <li>"I prefer going long, avoid shorting"</li>
              <li>"Only trade during US market hours"</li>
              <li>"Don't go long when RSI &gt; 70"</li>
              <li>"Avoid trading on weekends"</li>
            </ul>
          </li>
        </ul>
      </div>
    </div>
  );
};

export default VibeStrategyPanel;

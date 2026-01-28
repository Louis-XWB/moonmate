import React, { useState, useEffect } from 'react';

const VibeStrategyPanel = () => {
  const [rules, setRules] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [newRuleContent, setNewRuleContent] = useState('');
  const [editingRule, setEditingRule] = useState(null);
  const [editContent, setEditContent] = useState('');

  // 获取所有规则
  const fetchRules = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch('https://8000-igyitwrl655jpdhlmwvph-a31b4228.sg1.manus.computer/api/vibe/rules');
      const data = await response.json();
      if (data.success) {
        setRules(data.rules);
      } else {
        setError('获取规则失败');
      }
    } catch (err) {
      setError(`获取规则失败: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  // 添加新规则
  const addRule = async () => {
    if (!newRuleContent.trim()) {
      alert('请输入规则内容');
      return;
    }

    try {
      const response = await fetch('https://8000-igyitwrl655jpdhlmwvph-a31b4228.sg1.manus.computer/api/vibe/rules', {
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
        alert('添加规则失败');
      }
    } catch (err) {
      alert(`添加规则失败: ${err.message}`);
    }
  };

  // 更新规则
  const updateRule = async (ruleId, content, enabled) => {
    try {
      const response = await fetch(`https://8000-igyitwrl655jpdhlmwvph-a31b4228.sg1.manus.computer/api/vibe/rules/${ruleId}`, {
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
        alert('更新规则失败');
      }
    } catch (err) {
      alert(`更新规则失败: ${err.message}`);
    }
  };

  // 删除规则
  const deleteRule = async (ruleId) => {
    if (!confirm('确定要删除这条规则吗？')) {
      return;
    }

    try {
      const response = await fetch(`https://8000-igyitwrl655jpdhlmwvph-a31b4228.sg1.manus.computer/api/vibe/rules/${ruleId}`, {
        method: 'DELETE',
      });
      const data = await response.json();
      if (data.success) {
        fetchRules();
      } else {
        alert('删除规则失败');
      }
    } catch (err) {
      alert(`删除规则失败: ${err.message}`);
    }
  };

  // 切换启用/禁用
  const toggleEnabled = async (rule) => {
    await updateRule(rule.id, rule.content, !rule.enabled);
  };

  // 开始编辑
  const startEdit = (rule) => {
    setEditingRule(rule.id);
    setEditContent(rule.content);
  };

  // 保存编辑
  const saveEdit = async (rule) => {
    await updateRule(rule.id, editContent, rule.enabled);
  };

  // 取消编辑
  const cancelEdit = () => {
    setEditingRule(null);
    setEditContent('');
  };

  useEffect(() => {
    fetchRules();
  }, []);

  return (
    <div className="p-6 space-y-6">
      {/* 标题和说明 */}
      <div className="bg-gradient-to-r from-purple-900/50 to-pink-900/50 rounded-lg p-6 border border-purple-500/30">
        <h2 className="text-2xl font-bold text-white mb-2">🎯 Vibe 策略偏好</h2>
        <p className="text-gray-300 text-sm">
          自定义你的交易策略偏好，AI 会在生成交易信号时严格遵守这些规则。
          你可以添加任何你想要的交易理念、偏好或约束条件。
        </p>
      </div>

      {/* 添加新规则 */}
      <div className="bg-gray-800/50 rounded-lg p-6 border border-gray-700">
        <h3 className="text-lg font-semibold text-white mb-4">➕ 添加新规则</h3>
        <div className="flex gap-3">
          <input
            type="text"
            value={newRuleContent}
            onChange={(e) => setNewRuleContent(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && addRule()}
            placeholder="例如：我偏好做多，不喜欢做空"
            className="flex-1 bg-gray-900 text-white px-4 py-3 rounded-lg border border-gray-600 focus:border-purple-500 focus:outline-none"
          />
          <button
            onClick={addRule}
            className="bg-purple-600 hover:bg-purple-700 text-white px-6 py-3 rounded-lg font-medium transition-colors"
          >
            添加
          </button>
        </div>
      </div>

      {/* 规则列表 */}
      <div className="bg-gray-800/50 rounded-lg p-6 border border-gray-700">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-white">📋 我的策略规则</h3>
          <button
            onClick={fetchRules}
            className="text-gray-400 hover:text-white transition-colors"
          >
            🔄 刷新
          </button>
        </div>

        {loading && (
          <div className="text-center py-8 text-gray-400">
            <div className="animate-spin inline-block w-8 h-8 border-4 border-purple-500 border-t-transparent rounded-full"></div>
            <p className="mt-2">加载中...</p>
          </div>
        )}

        {error && (
          <div className="bg-red-900/30 border border-red-500 text-red-300 px-4 py-3 rounded-lg">
            {error}
          </div>
        )}

        {!loading && !error && rules.length === 0 && (
          <div className="text-center py-8 text-gray-400">
            <p>还没有添加任何规则</p>
            <p className="text-sm mt-2">点击上方"添加新规则"开始创建你的策略偏好</p>
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
                  {/* 启用/禁用开关 */}
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

                  {/* 规则内容 */}
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
                        {rule.enabled ? '✓ 已启用' : '✗ 已禁用'}
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
                            保存
                          </button>
                          <button
                            onClick={cancelEdit}
                            className="bg-gray-600 hover:bg-gray-700 text-white px-3 py-1 rounded text-sm"
                          >
                            取消
                          </button>
                        </div>
                      </div>
                    ) : (
                      <p className={`${rule.enabled ? 'text-white' : 'text-gray-500'}`}>
                        {rule.content}
                      </p>
                    )}

                    <div className="flex items-center gap-4 mt-2 text-xs text-gray-500">
                      <span>创建于: {new Date(rule.created_at).toLocaleString('zh-CN')}</span>
                      {rule.updated_at !== rule.created_at && (
                        <span>更新于: {new Date(rule.updated_at).toLocaleString('zh-CN')}</span>
                      )}
                    </div>
                  </div>

                  {/* 操作按钮 */}
                  {editingRule !== rule.id && (
                    <div className="flex gap-2">
                      <button
                        onClick={() => startEdit(rule)}
                        className="text-blue-400 hover:text-blue-300 transition-colors"
                        title="编辑"
                      >
                        ✏️
                      </button>
                      <button
                        onClick={() => deleteRule(rule.id)}
                        className="text-red-400 hover:text-red-300 transition-colors"
                        title="删除"
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

      {/* 统计信息 */}
      {rules.length > 0 && (
        <div className="bg-gray-800/50 rounded-lg p-4 border border-gray-700">
          <div className="flex items-center justify-between text-sm">
            <span className="text-gray-400">总规则数: {rules.length}</span>
            <span className="text-gray-400">
              已启用: {rules.filter((r) => r.enabled).length}
            </span>
            <span className="text-gray-400">
              已禁用: {rules.filter((r) => !r.enabled).length}
            </span>
          </div>
        </div>
      )}

      {/* 使用说明 */}
      <div className="bg-blue-900/20 border border-blue-500/30 rounded-lg p-4">
        <h4 className="text-blue-300 font-semibold mb-2">💡 使用提示</h4>
        <ul className="text-blue-200 text-sm space-y-1 list-disc list-inside">
          <li>规则可以是任何自然语言描述的策略偏好</li>
          <li>AI 会严格遵守这些规则，优先级高于其他分析</li>
          <li>可以随时添加、编辑、删除或禁用规则</li>
          <li>禁用的规则不会传递给 AI，但会保留在列表中</li>
          <li>示例规则：
            <ul className="ml-6 mt-1 space-y-1">
              <li>"我偏好做多，不喜欢做空"</li>
              <li>"只在美股开盘时间交易"</li>
              <li>"当 RSI &gt; 70 时不做多"</li>
              <li>"避免在周末交易"</li>
            </ul>
          </li>
        </ul>
      </div>
    </div>
  );
};

export default VibeStrategyPanel;

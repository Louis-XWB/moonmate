/**
 * AI交易助手宠物 - 数据结构和状态管理
 */

// 宠物状态枚举
export const PetStatus = {
  IDLE: 'idle',           // 空闲（系统未启动）
  HAPPY: 'happy',         // 开心（盈利中）
  SAD: 'sad',             // 难过（亏损中）
  THINKING: 'thinking',   // 思考（观望中）
  EXCITED: 'excited',     // 兴奋（大幅盈利）
  WORRIED: 'worried',     // 担忧（大幅亏损）
  SLEEPING: 'sleeping'    // 睡觉（长时间无交易）
}

// 宠物等级配置
export const PetLevels = [
  { level: 1, name: '新手交易员', minProfit: 0, color: '#94a3b8' },
  { level: 2, name: '初级交易员', minProfit: 100, color: '#60a5fa' },
  { level: 3, name: '中级交易员', minProfit: 500, color: '#34d399' },
  { level: 4, name: '高级交易员', minProfit: 1000, color: '#fbbf24' },
  { level: 5, name: '专家交易员', minProfit: 2000, color: '#f97316' },
  { level: 6, name: '大师交易员', minProfit: 5000, color: '#ec4899' },
  { level: 7, name: '传奇交易员', minProfit: 10000, color: '#a855f7' }
]

// 成就配置
export const Achievements = [
  {
    id: 'first_profit',
    name: '首次盈利',
    description: '完成第一笔盈利交易',
    icon: '💰',
    condition: (stats) => stats.total_pnl > 0
  },
  {
    id: 'win_streak_5',
    name: '连赢5单',
    description: '连续5笔交易盈利',
    icon: '🔥',
    condition: (stats) => stats.win_streak >= 5
  },
  {
    id: 'profit_100',
    name: '百元大关',
    description: '累计盈利达到$100',
    icon: '💵',
    condition: (stats) => stats.total_pnl >= 100
  },
  {
    id: 'profit_1000',
    name: '千元富翁',
    description: '累计盈利达到$1000',
    icon: '💎',
    condition: (stats) => stats.total_pnl >= 1000
  },
  {
    id: 'trade_100',
    name: '百战老兵',
    description: '完成100笔交易',
    icon: '⚔️',
    condition: (stats) => stats.total_orders >= 100
  },
  {
    id: 'win_rate_80',
    name: '神枪手',
    description: '胜率达到80%',
    icon: '🎯',
    condition: (stats) => stats.fill_rate >= 0.8 && stats.total_orders >= 10
  },
  {
    id: 'dodge_crash',
    name: '躲过暴跌',
    description: '在市场暴跌时保持盈利',
    icon: '🛡️',
    condition: (stats, market) => market.change_24h < -5 && stats.today_pnl > 0
  },
  {
    id: 'catch_pump',
    name: '抓住暴涨',
    description: '在市场暴涨时获利',
    icon: '🚀',
    condition: (stats, market) => market.change_24h > 5 && stats.today_pnl > 50
  }
]

// 宠物消息模板
export const PetMessages = {
  // 启动消息
  startup: [
    '主人，系统已启动！让我们一起赚钱吧！💪',
    '准备好了！我会帮你盯着市场的！👀',
    '开工啦！今天一定要盈利哦！✨'
  ],
  
  // 停止消息
  shutdown: [
    '辛苦了主人，休息一下吧～😴',
    '今天的工作结束啦！明天继续加油！💤',
    '系统已停止，我去睡觉啦～Zzz...'
  ],
  
  // 盈利消息
  profit: [
    '太棒了！我们赚钱了！🎉',
    '哇！这波操作很稳！💰',
    '继续保持，胜利在望！🏆'
  ],
  
  // 亏损消息
  loss: [
    '别灰心，下次一定能赢回来！💪',
    '失败是成功之母，继续努力！📈',
    '冷静分析，找到问题所在！🤔'
  ],
  
  // 风险警告
  risk_warning: [
    '⚠️ 警告：当前回撤过大，建议暂停交易！',
    '⚠️ 注意：连续亏损中，需要调整策略！',
    '⚠️ 风险：市场波动剧烈，谨慎操作！'
  ],
  
  // 机会提示
  opportunity: [
    '💡 发现机会：多Agent一致看多！',
    '💡 好时机：技术指标显示超卖！',
    '💡 注意：鲸鱼正在大量买入！'
  ],
  
  // 升级消息
  level_up: (level) => `🎊 恭喜升级！现在是 ${PetLevels[level - 1].name} 了！`,
  
  // 成就解锁
  achievement: (achievement) => `🏅 解锁成就：${achievement.name}！${achievement.description}`
}

// 根据统计数据计算宠物状态
export function calculatePetStatus(stats, isRunning) {
  if (!isRunning) {
    return PetStatus.SLEEPING
  }
  
  const pnl = stats.total_pnl || 0
  const todayPnl = stats.today_pnl || 0
  
  // 根据盈亏情况决定状态
  if (pnl > 100) {
    return PetStatus.EXCITED  // 大幅盈利
  } else if (pnl > 0) {
    return PetStatus.HAPPY    // 盈利
  } else if (pnl < -100) {
    return PetStatus.WORRIED  // 大幅亏损
  } else if (pnl < 0) {
    return PetStatus.SAD      // 亏损
  } else {
    return PetStatus.THINKING // 观望
  }
}

// 根据总盈利计算等级
export function calculateLevel(totalProfit) {
  for (let i = PetLevels.length - 1; i >= 0; i--) {
    if (totalProfit >= PetLevels[i].minProfit) {
      return PetLevels[i]
    }
  }
  return PetLevels[0]
}

// 计算当前等级的经验进度
export function calculateLevelProgress(totalProfit) {
  const currentLevel = calculateLevel(totalProfit)
  const currentLevelIndex = PetLevels.findIndex(l => l.level === currentLevel.level)
  
  if (currentLevelIndex === PetLevels.length - 1) {
    return 100 // 已满级
  }
  
  const nextLevel = PetLevels[currentLevelIndex + 1]
  const currentLevelProfit = currentLevel.minProfit
  const nextLevelProfit = nextLevel.minProfit
  
  const progress = ((totalProfit - currentLevelProfit) / (nextLevelProfit - currentLevelProfit)) * 100
  return Math.min(100, Math.max(0, progress))
}

// 检查新解锁的成就
export function checkAchievements(stats, market, unlockedAchievements = []) {
  const newAchievements = []
  
  for (const achievement of Achievements) {
    // 如果已解锁，跳过
    if (unlockedAchievements.includes(achievement.id)) {
      continue
    }
    
    // 检查条件
    if (achievement.condition(stats, market)) {
      newAchievements.push(achievement)
    }
  }
  
  return newAchievements
}

// 获取随机消息
export function getRandomMessage(messageType) {
  const messages = PetMessages[messageType]
  if (!messages || messages.length === 0) {
    return ''
  }
  return messages[Math.floor(Math.random() * messages.length)]
}

// 宠物状态对应的颜色
export const PetStatusColors = {
  [PetStatus.IDLE]: '#94a3b8',      // 灰色
  [PetStatus.HAPPY]: '#34d399',     // 绿色
  [PetStatus.SAD]: '#ef4444',       // 红色
  [PetStatus.THINKING]: '#fbbf24',  // 黄色
  [PetStatus.EXCITED]: '#10b981',   // 亮绿色
  [PetStatus.WORRIED]: '#dc2626',   // 深红色
  [PetStatus.SLEEPING]: '#6b7280'   // 深灰色
}

// 宠物状态对应的表情
export const PetStatusEmojis = {
  [PetStatus.IDLE]: '😐',
  [PetStatus.HAPPY]: '😊',
  [PetStatus.SAD]: '😢',
  [PetStatus.THINKING]: '🤔',
  [PetStatus.EXCITED]: '🤩',
  [PetStatus.WORRIED]: '😰',
  [PetStatus.SLEEPING]: '😴'
}

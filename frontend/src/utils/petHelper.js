/**
 * AI Trading Pet - Data Structures and Status Management
 */

// Pet Status Enum
export const PetStatus = {
  IDLE: 'idle',           // Idle (system not started)
  HAPPY: 'happy',         // Happy (in profit)
  SAD: 'sad',             // Sad (in loss)
  THINKING: 'thinking',   // Thinking (holding)
  EXCITED: 'excited',     // Excited (large profit)
  WORRIED: 'worried',     // Worried (large loss)
  SLEEPING: 'sleeping'    // Sleeping (no trades for a long time)
}

// Pet Level Configuration
export const PetLevels = [
  { level: 1, name: 'Rookie Trader', minProfit: 0, color: '#94a3b8' },
  { level: 2, name: 'Junior Trader', minProfit: 100, color: '#60a5fa' },
  { level: 3, name: 'Mid-Level Trader', minProfit: 500, color: '#34d399' },
  { level: 4, name: 'Senior Trader', minProfit: 1000, color: '#fbbf24' },
  { level: 5, name: 'Expert Trader', minProfit: 2000, color: '#f97316' },
  { level: 6, name: 'Master Trader', minProfit: 5000, color: '#ec4899' },
  { level: 7, name: 'Legendary Trader', minProfit: 10000, color: '#a855f7' }
]

// Achievement Configuration
export const Achievements = [
  {
    id: 'first_profit',
    name: 'First Profit',
    description: 'Complete your first winning trade',
    icon: '💰',
    condition: (stats) => stats.total_pnl > 0
  },
  {
    id: 'win_streak_5',
    name: '5-Win Streak',
    description: '5 consecutive winning trades',
    icon: '🔥',
    condition: (stats) => stats.win_streak >= 5
  },
  {
    id: 'profit_100',
    name: '$100 Milestone',
    description: 'Cumulative profit reaches $100',
    icon: '💵',
    condition: (stats) => stats.total_pnl >= 100
  },
  {
    id: 'profit_1000',
    name: '$1000 Milestone',
    description: 'Cumulative profit reaches $1000',
    icon: '💎',
    condition: (stats) => stats.total_pnl >= 1000
  },
  {
    id: 'trade_100',
    name: 'Battle Veteran',
    description: 'Complete 100 trades',
    icon: '⚔️',
    condition: (stats) => stats.total_orders >= 100
  },
  {
    id: 'win_rate_80',
    name: 'Sharpshooter',
    description: 'Win rate reaches 80%',
    icon: '🎯',
    condition: (stats) => stats.fill_rate >= 0.8 && stats.total_orders >= 10
  },
  {
    id: 'dodge_crash',
    name: 'Crash Dodger',
    description: 'Stay profitable during a market crash',
    icon: '🛡️',
    condition: (stats, market) => market.change_24h < -5 && stats.today_pnl > 0
  },
  {
    id: 'catch_pump',
    name: 'Pump Catcher',
    description: 'Profit from a market pump',
    icon: '🚀',
    condition: (stats, market) => market.change_24h > 5 && stats.today_pnl > 50
  }
]

// Pet Message Templates
export const PetMessages = {
  // Start messages
  startup: [
    "System started! Let's make some money! 💪",
    "Ready! I'll keep an eye on the market for you! 👀",
    "Let's go! Today we're gonna profit! ✨"
  ],

  // Stop messages
  shutdown: [
    'Good work, time for a rest~ 😴',
    "Work's done for today! Let's keep it up tomorrow! 💤",
    'System stopped, time for sleep~ Zzz...'
  ],

  // Profit messages
  profit: [
    'Awesome! We made money! 🎉',
    'Wow! That was a solid trade! 💰',
    'Keep it up, victory is near! 🏆'
  ],

  // Loss messages
  loss: [
    "Don't give up, we'll win it back next time! 💪",
    'Failure is the mother of success, keep going! 📈',
    'Stay calm, analyze, and find the issue! 🤔'
  ],
  
  // Risk warnings
  risk_warning: [
    '⚠️ Warning: Current drawdown is too large, consider pausing trading!',
    '⚠️ Caution: On a losing streak, strategy adjustment needed!',
    '⚠️ Risk: High market volatility, trade with caution!'
  ],
  
  // Opportunity tips
  opportunity: [
    '💡 Opportunity: Multiple agents agree on bullish!',
    '💡 Good timing: Technical indicators show oversold!',
    '💡 Notice: Whales are buying in large volumes!'
  ],
  
  // Level up messages
  level_up: (level) => `🎊 Congratulations on leveling up! Now a ${PetLevels[level - 1].name}!`,
  
  // Achievement unlocked
  achievement: (achievement) => `🏅 Achievement unlocked: ${achievement.name}!${achievement.description}`
}

// Calculate pet status based on statistics
export function calculatePetStatus(stats, isRunning) {
  if (!isRunning) {
    return PetStatus.SLEEPING
  }
  
  const pnl = stats.total_pnl || 0
  const todayPnl = stats.today_pnl || 0
  
  // Determine status based on P&L
  if (pnl > 100) {
    return PetStatus.EXCITED  // Large profit
  } else if (pnl > 0) {
    return PetStatus.HAPPY    // Profit
  } else if (pnl < -100) {
    return PetStatus.WORRIED  // Large loss
  } else if (pnl < 0) {
    return PetStatus.SAD      // Loss
  } else {
    return PetStatus.THINKING // Hold
  }
}

// Calculate level based on total profit
export function calculateLevel(totalProfit) {
  for (let i = PetLevels.length - 1; i >= 0; i--) {
    if (totalProfit >= PetLevels[i].minProfit) {
      return PetLevels[i]
    }
  }
  return PetLevels[0]
}

// Calculate experience progress for current level
export function calculateLevelProgress(totalProfit) {
  const currentLevel = calculateLevel(totalProfit)
  const currentLevelIndex = PetLevels.findIndex(l => l.level === currentLevel.level)
  
  if (currentLevelIndex === PetLevels.length - 1) {
    return 100 // Max level reached
  }
  
  const nextLevel = PetLevels[currentLevelIndex + 1]
  const currentLevelProfit = currentLevel.minProfit
  const nextLevelProfit = nextLevel.minProfit
  
  const progress = ((totalProfit - currentLevelProfit) / (nextLevelProfit - currentLevelProfit)) * 100
  return Math.min(100, Math.max(0, progress))
}

// Check newly unlocked achievements
export function checkAchievements(stats, market, unlockedAchievements = []) {
  const newAchievements = []
  
  for (const achievement of Achievements) {
    // If already unlocked, skip
    if (unlockedAchievements.includes(achievement.id)) {
      continue
    }
    
    // Check condition
    if (achievement.condition(stats, market)) {
      newAchievements.push(achievement)
    }
  }
  
  return newAchievements
}

// Get random message
export function getRandomMessage(messageType) {
  const messages = PetMessages[messageType]
  if (!messages || messages.length === 0) {
    return ''
  }
  return messages[Math.floor(Math.random() * messages.length)]
}

// Pet status colors
export const PetStatusColors = {
  [PetStatus.IDLE]: '#94a3b8',      // Gray
  [PetStatus.HAPPY]: '#34d399',     // Green
  [PetStatus.SAD]: '#ef4444',       // Red
  [PetStatus.THINKING]: '#fbbf24',  // Yellow
  [PetStatus.EXCITED]: '#10b981',   // Light green
  [PetStatus.WORRIED]: '#dc2626',   // Dark red
  [PetStatus.SLEEPING]: '#6b7280'   // Dark gray
}

// Pet status expressions
export const PetStatusEmojis = {
  [PetStatus.IDLE]: '😐',
  [PetStatus.HAPPY]: '😊',
  [PetStatus.SAD]: '😢',
  [PetStatus.THINKING]: '🤔',
  [PetStatus.EXCITED]: '🤩',
  [PetStatus.WORRIED]: '😰',
  [PetStatus.SLEEPING]: '😴'
}

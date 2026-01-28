import { useState, useEffect, useRef } from 'react'
import Draggable from 'react-draggable'
import {
  PetStatus,
  PetStatusColors,
  PetStatusEmojis,
  calculatePetStatus,
  calculateLevel,
  calculateLevelProgress,
  checkAchievements,
  getRandomMessage,
  PetMessages
} from '../utils/petHelper'
import './TradingPet.css'

export default function TradingPet({ stats, isRunning, ticker, onStart, onStop }) {
  // 宠物状态
  const [petStatus, setPetStatus] = useState(PetStatus.IDLE)
  const [level, setLevel] = useState(null)
  const [levelProgress, setLevelProgress] = useState(0)
  const [unlockedAchievements, setUnlockedAchievements] = useState([])
  
  // UI状态
  const [showTooltip, setShowTooltip] = useState(false)
  const [showMessage, setShowMessage] = useState(false)
  const [currentMessage, setCurrentMessage] = useState('')
  const [showMenu, setShowMenu] = useState(false)
  const [showAchievements, setShowAchievements] = useState(false)
  
  // 动画状态
  const [isJumping, setIsJumping] = useState(false)
  const [isBouncing, setIsBouncing] = useState(false)
  
  // 引用
  const messageTimeoutRef = useRef(null)
  const lastPnlRef = useRef(0)
  
  // 更新宠物状态
  useEffect(() => {
    const newStatus = calculatePetStatus(stats, isRunning)
    setPetStatus(newStatus)
    
    const totalProfit = stats.total_pnl || 0
    const newLevel = calculateLevel(totalProfit)
    const progress = calculateLevelProgress(totalProfit)
    
    setLevel(newLevel)
    setLevelProgress(progress)
    
    // 检查升级
    if (level && newLevel.level > level.level) {
      showPetMessage(PetMessages.level_up(newLevel.level))
    }
    
    // 检查成就
    const market = ticker ? { change_24h: ticker.change_24h } : {}
    const newAchievements = checkAchievements(stats, market, unlockedAchievements)
    if (newAchievements.length > 0) {
      newAchievements.forEach(achievement => {
        showPetMessage(PetMessages.achievement(achievement))
        setUnlockedAchievements(prev => [...prev, achievement.id])
      })
    }
    
    // 检测盈亏变化
    const currentPnl = stats.total_pnl || 0
    if (currentPnl > lastPnlRef.current) {
      // 盈利，跳跃动画
      triggerJump()
    } else if (currentPnl < lastPnlRef.current) {
      // 亏损，弹跳动画
      triggerBounce()
    }
    lastPnlRef.current = currentPnl
  }, [stats, isRunning, ticker])
  
  // 显示消息
  const showPetMessage = (message) => {
    setCurrentMessage(message)
    setShowMessage(true)
    
    if (messageTimeoutRef.current) {
      clearTimeout(messageTimeoutRef.current)
    }
    
    messageTimeoutRef.current = setTimeout(() => {
      setShowMessage(false)
    }, 5000)
  }
  
  // 触发跳跃动画
  const triggerJump = () => {
    setIsJumping(true)
    setTimeout(() => setIsJumping(false), 600)
  }
  
  // 触发弹跳动画
  const triggerBounce = () => {
    setIsBouncing(true)
    setTimeout(() => setIsBouncing(false), 600)
  }
  
  // 点击宠物
  const handlePetClick = () => {
    // 根据状态显示不同消息
    if (!isRunning) {
      showPetMessage('主人，快启动系统吧！我已经准备好了！💪')
    } else if (petStatus === PetStatus.HAPPY || petStatus === PetStatus.EXCITED) {
      showPetMessage(getRandomMessage('profit'))
    } else if (petStatus === PetStatus.SAD || petStatus === PetStatus.WORRIED) {
      showPetMessage(getRandomMessage('loss'))
    } else {
      showPetMessage('让我们一起分析市场，寻找机会！🔍')
    }
  }
  
  // 右键菜单
  const handleContextMenu = (e) => {
    e.preventDefault()
    setShowMenu(!showMenu)
  }
  
  // 快捷操作
  const handleQuickAction = (action) => {
    setShowMenu(false)
    
    switch (action) {
      case 'start':
        onStart()
        showPetMessage(getRandomMessage('startup'))
        break
      case 'stop':
        onStop()
        showPetMessage(getRandomMessage('shutdown'))
        break
      case 'achievements':
        setShowAchievements(true)
        break
      default:
        break
    }
  }
  
  // 获取宠物颜色
  const petColor = PetStatusColors[petStatus]
  const petEmoji = PetStatusEmojis[petStatus]
  
  return (
    <>
      <Draggable
        defaultPosition={{ x: 0, y: 0 }}
        bounds="body"
      >
        <div className="trading-pet-container">
          {/* 宠物主体 */}
          <div
            className={`trading-pet ${isJumping ? 'jumping' : ''} ${isBouncing ? 'bouncing' : ''}`}
            style={{ borderColor: petColor, boxShadow: `0 0 20px ${petColor}40` }}
            onClick={handlePetClick}
            onContextMenu={handleContextMenu}
            onMouseEnter={() => setShowTooltip(true)}
            onMouseLeave={() => setShowTooltip(false)}
          >
            {/* 宠物表情 */}
            <div className="pet-emoji" style={{ fontSize: '48px' }}>
              {petEmoji}
            </div>
            
            {/* 等级指示器 */}
            {level && (
              <div className="pet-level" style={{ backgroundColor: level.color }}>
                Lv.{level.level}
              </div>
            )}
            
            {/* 经验条 */}
            <div className="pet-exp-bar">
              <div
                className="pet-exp-fill"
                style={{ width: `${levelProgress}%`, backgroundColor: petColor }}
              />
            </div>
          </div>
          
          {/* 悬停提示 */}
          {showTooltip && level && (
            <div className="pet-tooltip">
              <div className="tooltip-title">{level.name}</div>
              <div className="tooltip-stats">
                <div>💰 总盈亏: ${(stats.total_pnl || 0).toFixed(2)}</div>
                <div>📊 胜率: {((stats.fill_rate || 0) * 100).toFixed(1)}%</div>
                <div>🏆 成就: {unlockedAchievements.length}/8</div>
              </div>
              <div className="tooltip-hint">
                左键点击查看消息 • 右键打开菜单
              </div>
            </div>
          )}
          
          {/* 消息气泡 */}
          {showMessage && (
            <div className="pet-message-bubble">
              {currentMessage}
            </div>
          )}
          
          {/* 右键菜单 */}
          {showMenu && (
            <div className="pet-context-menu">
              {!isRunning ? (
                <div className="menu-item" onClick={() => handleQuickAction('start')}>
                  ▶️ 启动系统
                </div>
              ) : (
                <div className="menu-item" onClick={() => handleQuickAction('stop')}>
                  ⏸️ 停止系统
                </div>
              )}
              <div className="menu-item" onClick={() => handleQuickAction('achievements')}>
                🏆 查看成就
              </div>
              <div className="menu-item" onClick={() => setShowMenu(false)}>
                ❌ 关闭菜单
              </div>
            </div>
          )}
        </div>
      </Draggable>
      
      {/* 成就面板 */}
      {showAchievements && (
        <div className="pet-achievements-modal" onClick={() => setShowAchievements(false)}>
          <div className="achievements-panel" onClick={(e) => e.stopPropagation()}>
            <div className="achievements-header">
              <h3>🏆 成就系统</h3>
              <button onClick={() => setShowAchievements(false)}>✕</button>
            </div>
            <div className="achievements-list">
              {[
                { id: 'first_profit', name: '首次盈利', icon: '💰' },
                { id: 'win_streak_5', name: '连赢5单', icon: '🔥' },
                { id: 'profit_100', name: '百元大关', icon: '💵' },
                { id: 'profit_1000', name: '千元富翁', icon: '💎' },
                { id: 'trade_100', name: '百战老兵', icon: '⚔️' },
                { id: 'win_rate_80', name: '神枪手', icon: '🎯' },
                { id: 'dodge_crash', name: '躲过暴跌', icon: '🛡️' },
                { id: 'catch_pump', name: '抓住暴涨', icon: '🚀' }
              ].map(achievement => {
                const unlocked = unlockedAchievements.includes(achievement.id)
                return (
                  <div
                    key={achievement.id}
                    className={`achievement-item ${unlocked ? 'unlocked' : 'locked'}`}
                  >
                    <div className="achievement-icon">{achievement.icon}</div>
                    <div className="achievement-name">{achievement.name}</div>
                    {unlocked && <div className="achievement-badge">✓</div>}
                  </div>
                )
              })}
            </div>
            <div className="achievements-progress">
              已解锁: {unlockedAchievements.length} / 8
            </div>
          </div>
        </div>
      )}
    </>
  )
}

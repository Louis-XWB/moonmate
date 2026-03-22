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
  // Pet status
  const [petStatus, setPetStatus] = useState(PetStatus.IDLE)
  const [level, setLevel] = useState(null)
  const [levelProgress, setLevelProgress] = useState(0)
  const [unlockedAchievements, setUnlockedAchievements] = useState([])
  
  // UIStatus
  const [showTooltip, setShowTooltip] = useState(false)
  const [showMessage, setShowMessage] = useState(false)
  const [currentMessage, setCurrentMessage] = useState('')
  const [showMenu, setShowMenu] = useState(false)
  const [showAchievements, setShowAchievements] = useState(false)
  
  // Animation status
  const [isJumping, setIsJumping] = useState(false)
  const [isBouncing, setIsBouncing] = useState(false)
  
  // Refs
  const messageTimeoutRef = useRef(null)
  const lastPnlRef = useRef(0)
  
  // UpdatePet status
  useEffect(() => {
    const newStatus = calculatePetStatus(stats, isRunning)
    setPetStatus(newStatus)
    
    const totalProfit = stats.total_pnl || 0
    const newLevel = calculateLevel(totalProfit)
    const progress = calculateLevelProgress(totalProfit)
    
    setLevel(newLevel)
    setLevelProgress(progress)
    
    // Check for level up
    if (level && newLevel.level > level.level) {
      showPetMessage(PetMessages.level_up(newLevel.level))
    }
    
    // Check achievements
    const market = ticker ? { change_24h: ticker.change_24h } : {}
    const newAchievements = checkAchievements(stats, market, unlockedAchievements)
    if (newAchievements.length > 0) {
      newAchievements.forEach(achievement => {
        showPetMessage(PetMessages.achievement(achievement))
        setUnlockedAchievements(prev => [...prev, achievement.id])
      })
    }
    
    // Detect P&L changes
    const currentPnl = stats.total_pnl || 0
    if (currentPnl > lastPnlRef.current) {
      // Profit, Jump animation
      triggerJump()
    } else if (currentPnl < lastPnlRef.current) {
      // Loss, Bounce animation
      triggerBounce()
    }
    lastPnlRef.current = currentPnl
  }, [stats, isRunning, ticker])
  
  // Show message
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
  
  // TriggerJump animation
  const triggerJump = () => {
    setIsJumping(true)
    setTimeout(() => setIsJumping(false), 600)
  }
  
  // TriggerBounce animation
  const triggerBounce = () => {
    setIsBouncing(true)
    setTimeout(() => setIsBouncing(false), 600)
  }
  
  // Click on pet
  const handlePetClick = () => {
    // Show different messages based on status
    if (!isRunning) {
      showPetMessage('Hey! Start the system! I'm ready to go! 💪')
    } else if (petStatus === PetStatus.HAPPY || petStatus === PetStatus.EXCITED) {
      showPetMessage(getRandomMessage('profit'))
    } else if (petStatus === PetStatus.SAD || petStatus === PetStatus.WORRIED) {
      showPetMessage(getRandomMessage('loss'))
    } else {
      showPetMessage('Let's analyze the market together and find opportunities! 🔍')
    }
  }
  
  // Right-click menu
  const handleContextMenu = (e) => {
    e.preventDefault()
    setShowMenu(!showMenu)
  }
  
  // Quick actions
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
  
  // Get pet color
  const petColor = PetStatusColors[petStatus]
  const petEmoji = PetStatusEmojis[petStatus]
  
  return (
    <>
      <Draggable
        defaultPosition={{ x: 0, y: 0 }}
        bounds="body"
      >
        <div className="trading-pet-container">
          {/* Pet body */}
          <div
            className={`trading-pet ${isJumping ? 'jumping' : ''} ${isBouncing ? 'bouncing' : ''}`}
            style={{ borderColor: petColor, boxShadow: `0 0 20px ${petColor}40` }}
            onClick={handlePetClick}
            onContextMenu={handleContextMenu}
            onMouseEnter={() => setShowTooltip(true)}
            onMouseLeave={() => setShowTooltip(false)}
          >
            {/* Pet expressions */}
            <div className="pet-emoji" style={{ fontSize: '48px' }}>
              {petEmoji}
            </div>
            
            {/* Level indicator */}
            {level && (
              <div className="pet-level" style={{ backgroundColor: level.color }}>
                Lv.{level.level}
              </div>
            )}
            
            {/* Experience bar */}
            <div className="pet-exp-bar">
              <div
                className="pet-exp-fill"
                style={{ width: `${levelProgress}%`, backgroundColor: petColor }}
              />
            </div>
          </div>
          
          {/* Hover tooltip */}
          {showTooltip && level && (
            <div className="pet-tooltip">
              <div className="tooltip-title">{level.name}</div>
              <div className="tooltip-stats">
                <div>💰 Total P&L: ${(stats.total_pnl || 0).toFixed(2)}</div>
                <div>📊 Win rate: {((stats.fill_rate || 0) * 100).toFixed(1)}%</div>
                <div>🏆 Achievements: {unlockedAchievements.length}/8</div>
              </div>
              <div className="tooltip-hint">
                Left-click for messages • Right-click for menu
              </div>
            </div>
          )}
          
          {/* Message bubble */}
          {showMessage && (
            <div className="pet-message-bubble">
              {currentMessage}
            </div>
          )}
          
          {/* Right-click menu */}
          {showMenu && (
            <div className="pet-context-menu">
              {!isRunning ? (
                <div className="menu-item" onClick={() => handleQuickAction('start')}>
                  ▶️ Start System
                </div>
              ) : (
                <div className="menu-item" onClick={() => handleQuickAction('stop')}>
                  ⏸️ Stop System
                </div>
              )}
              <div className="menu-item" onClick={() => handleQuickAction('achievements')}>
                🏆 View Achievements
              </div>
              <div className="menu-item" onClick={() => setShowMenu(false)}>
                ❌ Close Menu
              </div>
            </div>
          )}
        </div>
      </Draggable>
      
      {/* Achievement panel */}
      {showAchievements && (
        <div className="pet-achievements-modal" onClick={() => setShowAchievements(false)}>
          <div className="achievements-panel" onClick={(e) => e.stopPropagation()}>
            <div className="achievements-header">
              <h3>🏆 Achievement System</h3>
              <button onClick={() => setShowAchievements(false)}>✕</button>
            </div>
            <div className="achievements-list">
              {[
                { id: 'first_profit', name: 'First Profit', icon: '💰' },
                { id: 'win_streak_5', name: '5-Win Streak', icon: '🔥' },
                { id: 'profit_100', name: '$100 Milestone', icon: '💵' },
                { id: 'profit_1000', name: '$1000 Milestone', icon: '💎' },
                { id: 'trade_100', name: 'Battle Veteran', icon: '⚔️' },
                { id: 'win_rate_80', name: 'Sharpshooter', icon: '🎯' },
                { id: 'dodge_crash', name: 'Crash Dodger', icon: '🛡️' },
                { id: 'catch_pump', name: 'Pump Catcher', icon: '🚀' }
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
              Unlocked: {unlockedAchievements.length} / 8
            </div>
          </div>
        </div>
      )}
    </>
  )
}

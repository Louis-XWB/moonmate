# MoonMate - AI Trading Assistant with Gamification

> **重要提示**：本项目持续开发中，部分已接入真实交易 API。在切换到实盘模式前，请务必充分了解相关风险，并从极小资金开始测试。开发者对任何实盘交易造成的损失不承担任何责任。

MoonMate 是一个创新的 Web3 AI 自动交易系统，它将复杂的量化交易策略与一个名为“MoonMate”的AI宠物助手相结合，通过游戏化的方式，为您带来直观、有趣且强大的交易体验。

---

## 🚀 功能演示
<video src="intro.mp4" controls="controls" style="max-width: 100%;">
</video>

---

## ✨ 项目特性

### 核心交易引擎

- **多执行器引擎**: 支持模拟盘、**永续合约 (CEX)** 和 **Hyperliquid 链上永续 (DEX)** 的无缝切换。
- **实时行情数据**: 接入交易所 API 获取实时行情，并支持多数据源扩展。
- **模块化架构**: 数据层、AI 层、策略层、风控层、执行层清晰分离，易于扩展。
- **完善的风控**: 日亏损限制、最大回撤、连续亏损熔断等多重风控规则。
- **回测系统**: 支持历史数据回测，计算 Sharpe、最大回撤等关键指标。

### AI 策略与分析

- **AI 委员会**: 多个独立的AI Agent共同决策，提高信号准确性。
- **Decision Flow**: 可视化的决策流矩阵，清晰展示AI的思考过程。
- **Vibe 策略偏好**: 用户可自定义交易策略偏好，AI 会严格遵守这些规则进行决策。
- **社交媒体抓取**: 通过 Apify 抓取 Reddit/Twitter 数据进行情绪分析。
- **鲸鱼追踪**: 监控大额链上交易，发现市场动向。
- **多策略支持**: 内置动量、反转、盘口失衡等多种策略，支持策略插件化扩展。

### 创新的 MoonMate 宠物助手

- **游戏化交易体验**: 将交易过程与一个可爱的AI宠物养成相结合，告别枯燥的数字。
- **智能状态指示**: 宠物拥有不同的表情状态，实时反映系统运行情况和交易盈亏。
- **成长系统**: 宠物拥有7个等级（Lv.1 新手 → Lv.7 传奇），根据累计总盈利自动升级，见证您的成长之路。
- **成就系统**: 内置8个精心设计的成就（如“首次盈利💰”、“连赢5单🔥”），激励您达成不同的交易里程碑。
- **便捷交互**: 
    - **悬停提示**: 鼠标悬停显示迷你仪表盘（总盈亏、胜率、成就等）。
    - **右键菜单**: 快速启动/停止系统、查看成就。
    - **自由拖拽**: 可将宠物拖拽到屏幕任意位置。

### 可视化前端

- **现代化仪表盘**: 使用 React + TailwindCSS 构建，实时展示账户余额、收益曲线、当前信号等核心信息。
- **多功能面板**: 提供持仓管理、订单记录、信号分析、风控状态等多个独立面板，全面掌控交易细节。

---

## 项目结构

```
├── backend/                 # 后端代码
│   ├── ai/                  # AI 层（多Agent、信号生成、情绪分析）
│   ├── data/                # 数据层（行情、社交媒体、鲸鱼追踪）
│   ├── strategy/            # 策略层（Vibe、Decision Flow、信号融合）
│   ├── risk/                # 风控层
│   ├── execution/           # 执行层（币安、Hyperliquid）
│   └── api/                 # API 接口
├── frontend/                # 前端代码
│   └── src/
│       ├── components/
│       │   ├── TradingPet.jsx # ✅ MoonMate 宠物组件
│       │   └── TradingPet.css # ✅ MoonMate 样式
│       └── utils/
│           └── petHelper.js   # ✅ MoonMate 工具函数
├── config/                  # 配置文件
├── tests/                   # 测试脚本
├── requirements.txt         # Python 依赖
├── start.sh                # 启动脚本
└── README.md               # 本文档
```

---

## 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+
- pnpm

### 安装依赖

```bash
# 安装后端依赖
sudo pip3 install -r requirements.txt

# 安装前端依赖
cd frontend && pnpm install
```

### 配置环境变量

在项目根目录创建 `.env` 文件，并根据需要配置以下变量：

```bash
# Apify Token（社交媒体抓取需要）
APIFY_API_TOKEN=\'your_apify_token\'

# --- 实盘交易配置 (CEX) ---
# 币安测试网或主网的 API Key
BINANCE_API_KEY=\'your_binance_api_key\'
BINANCE_API_SECRET=\'your_binance_api_secret\'

# --- 实盘交易配置 (DEX) ---
# Hyperliquid 测试网或主网的钱包私钥 (0x开头)
# 强烈建议使用仅用于交易的独立新钱包
HYPERLIQUID_PRIVATE_KEY=\'your_wallet_private_key\'
```

### 配置文件 (`config/dev.yaml`)

核心配置位于 `config/dev.yaml`，你可以在此切换交易模式和配置执行器。

```yaml
# 交易模式: paper (模拟盘) | live_cex (币安实盘) | live_dex (Hyperliquid实盘)
trading:
  mode: paper

# 币安永续合约配置
binance_futures:
  enabled: true # 设为 true 以启用
  api_key: ${BINANCE_API_KEY} # 从环境变量读取
  api_secret: ${BINANCE_API_SECRET}
  testnet: true # true=测试网, false=主网

# Hyperliquid链上永续配置
hyperliquid:
  enabled: true # 设为 true 以启用
  private_key: ${HYPERLIQUID_PRIVATE_KEY} # 从环境变量读取
  testnet: true # true=测试网, false=主网
```

### 运行项目

```bash
# 一键启动 (后台运行后端，前台运行前端)
./start.sh

# 访问服务
- 前端界面: http://localhost:3000
- 后端 API: http://localhost:8000
- API 文档: http://localhost:8000/docs
```

---

## 免责声明

本项目仅供学习和研究使用，不构成任何投资建议。加密货币交易具有极高风险，请谨慎决策。**使用本代码进行实盘交易所产生的任何损失，作者不承担任何责任。**

## 许可证

MIT License

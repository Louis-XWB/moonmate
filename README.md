# MoonMate - AI Trading Assistant with Gamification

> **Important**: This project is under active development, and some features are connected to real trading APIs. Before switching to live trading mode, make sure you fully understand the risks involved and start testing with minimal funds. The developers are not responsible for any losses from live trading.

MoonMate is an innovative Web3 AI automated trading system that combines complex quantitative trading strategies with a gamified AI pet assistant called "MoonMate", delivering an intuitive, fun, and powerful trading experience.

---

## Features

### Core Trading Engine

- **Multi-Executor Engine**: Seamlessly switch between paper trading, **perpetual futures (CEX)**, and **Hyperliquid on-chain perpetuals (DEX)**.
- **Real-Time Market Data**: Connects to exchange APIs for real-time market data with multi-source support.
- **Modular Architecture**: Clean separation between data layer, AI layer, strategy layer, risk control layer, and execution layer for easy extension.
- **Comprehensive Risk Control**: Multiple risk rules including daily loss limits, maximum drawdown, and consecutive loss circuit breakers.
- **Backtesting System**: Supports historical data backtesting with key metrics like Sharpe ratio and maximum drawdown.

### AI Strategy & Analysis

- **AI Committee**: Multiple independent AI Agents collaborate on decisions to improve signal accuracy.
- **Decision Flow**: Visual decision flow matrix that clearly shows the AI's reasoning process.
- **Vibe Strategy Preferences**: Users can customize trading strategy preferences, and the AI will strictly follow these rules when making decisions.
- **Social Media Scraping**: Scrapes Reddit/Twitter data via Apify for sentiment analysis.
- **Whale Tracking**: Monitors large on-chain transactions to identify market trends.
- **Multi-Strategy Support**: Built-in momentum, reversal, orderbook imbalance, and other strategies with plugin-based extensibility.

### Innovative MoonMate Pet Assistant

- **Gamified Trading Experience**: Combines the trading process with a cute AI pet companion, making numbers come alive.
- **Smart Status Indicator**: The pet has different emotional states that reflect the system's running status and trading P&L in real time.
- **Growth System**: The pet has 7 levels (Lv.1 Rookie to Lv.7 Legend), automatically leveling up based on cumulative profit.
- **Achievement System**: 8 carefully designed achievements (e.g., "First Profit", "5 Wins Streak") to motivate you to reach different trading milestones.
- **Convenient Interaction**:
    - **Hover Tooltip**: Hover to see a mini dashboard (Total P&L, win rate, achievements, etc.).
    - **Right-Click Menu**: Quickly start/stop the system and view achievements.
    - **Free Dragging**: Drag the pet to any position on the screen.

### Visual Frontend

- **Modern Dashboard**: Built with React + TailwindCSS, displaying real-time account balance, profit curves, current signals, and other key information.
- **Multi-Function Panels**: Position management, order history, signal analysis, risk control status, and more in separate panels for full trading control.

---

## Project Structure

```
├── backend/                 # Backend code
│   ├── ai/                  # AI layer (multi-agent, signal generation, sentiment analysis)
│   ├── data/                # Data layer (market data, social media, whale tracking)
│   ├── strategy/            # Strategy layer (Vibe, Decision Flow, signal fusion)
│   ├── risk/                # Risk control layer
│   ├── execution/           # Execution layer (Binance, Hyperliquid)
│   └── api/                 # API endpoints
├── frontend/                # Frontend code
│   └── src/
│       ├── components/
│       │   ├── TradingPet.jsx # MoonMate pet component
│       │   └── TradingPet.css # MoonMate styles
│       └── utils/
│           └── petHelper.js   # MoonMate utility functions
├── config/                  # Configuration files
├── tests/                   # Test scripts
├── requirements.txt         # Python dependencies
├── start.sh                # Startup script
└── README.md               # This file
```

---

## Quick Start

### Requirements

- Python 3.10+
- Node.js 18+
- pnpm

### Install Dependencies

```bash
# Install backend dependencies
sudo pip3 install -r requirements.txt

# Install frontend dependencies
cd frontend && pnpm install
```

### Configure Environment Variables

Create a `.env` file in the project root and configure the following variables as needed:

```bash
# Apify Token (required for social media scraping)
APIFY_API_TOKEN='your_apify_token'

# --- Live Trading Configuration (CEX) ---
# Binance testnet or mainnet API Key
BINANCE_API_KEY='your_binance_api_key'
BINANCE_API_SECRET='your_binance_api_secret'

# --- Live Trading Configuration (DEX) ---
# Hyperliquid testnet or mainnet wallet private key (starting with 0x)
# Strongly recommended to use a separate wallet dedicated to trading only
HYPERLIQUID_PRIVATE_KEY='your_wallet_private_key'
```

### Configuration File (`config/dev.yaml`)

Core configuration is in `config/dev.yaml`, where you can switch trading modes and configure executors.

```yaml
# Trading mode: paper | live_cex (Binance) | live_dex (Hyperliquid)
trading:
  mode: paper

# Binance perpetual futures configuration
binance_futures:
  enabled: true # Set to true to enable
  api_key: ${BINANCE_API_KEY} # Read from environment variable
  api_secret: ${BINANCE_API_SECRET}
  testnet: true # true=testnet, false=mainnet

# Hyperliquid on-chain perpetual configuration
hyperliquid:
  enabled: true # Set to true to enable
  private_key: ${HYPERLIQUID_PRIVATE_KEY} # Read from environment variable
  testnet: true # true=testnet, false=mainnet
```

### Run the Project

```bash
# One-click start (backend runs in background, frontend in foreground)
./start.sh

# Access services
- Frontend UI: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs
```

---

## Disclaimer

This project is for educational and research purposes only and does not constitute investment advice. Cryptocurrency trading carries extremely high risk; please make decisions carefully. **The authors are not responsible for any losses resulting from live trading using this code.**

## License

MIT License

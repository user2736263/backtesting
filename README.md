# Hyperliquid Perps Trading Bot - Comprehensive Documentation

An automated cryptocurrency trading bot for Hyperliquid perps that executes trades based on webhook signals, with integrated stop-loss protection, position management, and comprehensive logging.

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture & How It Works](#architecture--how-it-works)
3. [Prerequisites](#prerequisites)
4. [Installation & Setup](#installation--setup)
5. [Configuration](#configuration)
6. [Services Integration](#services-integration)
7. [API Endpoints](#api-endpoints)
8. [Trading Logic](#trading-logic)
9. [Deployment](#deployment)
10. [Security Considerations](#security-considerations)
11. [Monitoring & Logging](#monitoring--logging)
12. [Troubleshooting](#troubleshooting)

---

## Overview

This trading bot is designed to automatically execute cryptocurrency trades on Hyperliquid (perpetual futures) based on webhook signals from external trading indicators or strategies. The bot provides:

- **Automated Trade Execution**: Market buy/sell orders triggered via webhook
- **Long and Short Positions**: Support for both long (bullish) and short (bearish) strategies
- **Stop-Loss Protection**: Background monitoring thread automatically closes position if price breaches threshold
- **Position Management**: Tracks open positions and prevents duplicate trades (one position at a time)
- **Trade Cooldown**: Prevents overtrading with configurable cooldown periods
- **Comprehensive Logging**: All trades logged to Google Sheets with detailed metrics including position type
- **Emergency Controls**: Force exit and manual position management endpoints

**Current Trading Pair**: SOL/USDC  
**Default Stop-Loss**: 0.7% from entry price (configurable separately for longs and shorts)
**Capital Allocation**: 11% of available USDC balance per trade  
**Trade Cooldown**: 600 seconds (10 minutes)

### Position Types

The bot supports two types of positions:

1. **Long Positions**: Profit when price goes up
   - Opened with "buy" webhook when no position exists
   - Closed with "sell" webhook
   - Stop-loss triggers when price drops below threshold
   - Profit target triggers when price rises above target

2. **Short Positions**: Profit when price goes down
   - Opened with "sell" webhook when no position exists
   - Closed with "buy" webhook
   - Stop-loss triggers when price rises above threshold
   - Profit target triggers when price drops below target

---

## Architecture & How It Works

### System Architecture

```
External Trading Signal/Indicator
           ↓
    Webhook POST Request
           ↓
    Flask Webhook Endpoint (/webhook)
           ↓
    ┌──────────────┐
    │  Validate    │ → Check cooldown, position status
    └──────────────┘
           ↓
    ┌──────────────┐
    │  Execute     │ → Hyperliquid Perps (Agent Wallet)
    │  Buy/Sell    │ → Market Order
    └──────────────┘
           ↓
    ┌──────────────┐
    │  Position    │ → Track entry price, quantity
    │  Tracking    │
    └──────────────┘
           ↓
    ┌──────────────┐
    │  Stop-Loss   │ → Background thread monitors price
    │  Monitor     │ → Auto-sell if threshold breached
    └──────────────┘
           ↓
    ┌──────────────┐
    │  Logging     │ → Google Sheets
    │              │
    └──────────────┘
```

### Workflow Details

#### 1. **Webhook Reception**
- Flask server listens on `/webhook` endpoint (POST)
- Receives JSON payload with `action` field ("buy" or "sell")
- Validates cooldown period (prevents trades within 600 seconds of last trade)
- Checks current position status and position type (long/short)

**Webhook Behavior (Inverted Semantics)**:
- **"buy" action**:
  - If no position: Opens a **long** position
  - If in short position: **Closes the short** position
  - If in long position: Ignored
- **"sell" action**:
  - If no position: Opens a **short** position
  - If in long position: **Closes the long** position
  - If in short position: Ignored

#### 2. **Long Position (Buy Order) Execution**
- Validates sufficient USDC withdrawable margin
- Calculates trade size: 11% of available USDC
- Fetches current mid price for SOL/USDC
- Calculates quantity with proper precision (sizeIncrement, default 0.001 SOL)
- Executes market buy order via Hyperliquid perps (Agent Wallet)
- Stores entry price, quantity, position_side="long", and timestamp
- Activates stop-loss monitoring thread

#### 2b. **Short Position (Sell Order) Execution**
- Validates sufficient USDC withdrawable margin
- Calculates trade size: 11% of available USDC
- Fetches current mid price for SOL/USDC
- Calculates quantity with proper precision (sizeIncrement, default 0.001 SOL)
- Executes market sell order via Hyperliquid perps (Agent Wallet)
- Stores entry price, quantity, position_side="short", and timestamp
- Activates stop-loss monitoring thread

#### 3. **Stop-Loss Monitoring**
- Background daemon thread runs continuously while position is open
- Checks current price every 5 seconds
- **For Long Positions**:
  - Stop-loss threshold: `entry_price * (1 - STOP_LOSS_PERCENT)` = 0.7% below entry
  - Triggers when price drops to or below threshold
- **For Short Positions**:
  - Stop-loss threshold: `entry_price * (1 + STOP_LOSS_PERCENT_SHORT)` = 0.7% above entry
  - Triggers when price rises to or above threshold
- If threshold breached:
  - Attempts to execute close order (sell for long, buy for short)
  - Falls back to force exit if sell fails
  - Logs trade with reason "stop loss triggered"

#### 4. **Sell Order Execution**
- Validates position is open
- Executes reduce-only market sell for tracked quantity (closes long)
- Calculates PnL: `(sell_revenue - sell_fees) - (buy_cost + buy_fees)`
- Logs trade details to Google Sheets:
  - Entry price, sell price, quantity
  - PnL, time difference, timestamp
  - Sell reason (normal sell, stop loss, force exit)
- Clears position state and stops monitoring thread

#### 5. **Emergency Controls**
- Force exit endpoint closes position using available wallet balance (98% of free balance)
- Manual position state management endpoints
- Test endpoints for buy/sell without webhook

---

## Prerequisites

### Software Requirements

- **Python**: 3.7 or higher
- **pip**: Python package manager
- **Git**: For cloning the repository (if applicable)

### Account Requirements

1. **Hyperliquid Account**
   - Main account funded with USDC (perps margin)
   - Authorized Agent Wallet (API private key) for trading
   - Sufficient USDC margin for trading

2. **Google Cloud Project**
   - Google Cloud account
   - Service account created with JSON key
   - Google Sheets API enabled
   - Google Drive API enabled

3. [Removed] Email Account (email notifications not used)

4. [Removed] Proxy Service (no proxy required)

### Network Requirements

- Internet connection for API calls
- Public IP address or tunnel (Ngrok/Cloudflare Tunnel) for webhook access
- Port 5000 accessible (or configure custom port)

---

## Installation & Setup

### Step 1: Clone Repository

```bash
git clone <repository-url>
cd TradingBotHyperLiquid
```

### Step 2: Create Virtual Environment (Recommended)

```bash
python -m venv venv

# On Windows
venv\Scripts\activate

# On Linux/Mac
source venv/bin/activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

**Required packages:**
- `flask` - Web framework for webhook endpoints
- `hyperliquid-python-sdk` - Hyperliquid API client (Agent Wallet signing)
- `gspread` - Google Sheets API client
- `oauth2client` - Google authentication
- `requests` - HTTP requests (general)
- `pandas`, `numpy` - Data processing (if needed)

### Step 4: Service Account Setup

1. Place your Google Service Account JSON file in the project root
2. Rename it to `service_account.json`
3. Ensure the service account has access to your Google Sheet named "Trading Bot"

### Step 5: Configure Credentials

**⚠️ SECURITY WARNING**: Do not hardcode credentials. See [Security Considerations](#security-considerations) for recommended improvements.

Configure environment variables:
- `HL_OWNER_ADDRESS`
- `HL_AGENT_PRIVATE_KEY`

### Step 6: Create Google Sheet

1. Create a new Google Sheet named "Trading Bot"
2. Share it with the service account email from `service_account.json`
3. Add headers in row 1 (optional, bot will append rows):
   - Entry Price, Sell Price, Quantity, PnL, Time Diff, Date Time, Sell Reason, Percent of Trade

### Step 7: Run the Bot

```bash
python app.py
```

The bot will start on `http://0.0.0.0:5000` by default. To change port, set `PORT` environment variable:

```bash
# Windows PowerShell
$env:PORT=8080; python app.py

# Linux/Mac
PORT=8080 python app.py
```

---

## Configuration

### Trading Parameters

All configuration is currently in `app.py`. Key parameters:

| Parameter | Default Value | Description |
|-----------|--------------|-------------|
| `SYMBOL` | `"SOL/USDC"` | Trading pair (format: BASE/QUOTE) |
| `STOP_LOSS_PERCENT` | `0.007` | Stop-loss percentage for long positions (0.7%) |
| `STOP_LOSS_PERCENT_SHORT` | `0.007` | Stop-loss percentage for short positions (0.7%) |
| `TAKER_FEE_RATE` | `0.000432` | Hyperliquid taker fee (0.0432%) - used on position open |
| `MAKER_FEE_RATE` | `0.000144` | Hyperliquid maker fee (0.0144%) - used on position close |
| `TRADE_COOLDOWN` | `600` | Seconds between trades (10 minutes) |
| Capital Allocation | `11%` | Percentage of USDC balance per trade (hardcoded: `0.11` in line 302) |

### Hyperliquid Agent Wallet Configuration

Environment variables (see `env.example`):

```
HL_OWNER_ADDRESS=0x...
HL_AGENT_PRIVATE_KEY=0x...
```

Notes:
- Use an Agent Wallet with trading authorization. Funds remain in the main account.
- Store secrets in environment variables; never commit secrets.

### [Removed] Proxy Configuration (not required)

### [Removed] Email Configuration (not used)

### Google Sheets Configuration

- Sheet Name: `"Trading Bot"` (line 33)
- Uses first sheet (`sheet1`)
- Service account JSON: `service_account.json`

---

## Services Integration

### 1. Hyperliquid Agent Wallet Setup

#### Create and Authorize Agent Wallet
1. Open Hyperliquid app → API/Agent Wallets
2. Create new Agent Wallet and authorize trading
3. Copy the agent private key and store in environment
4. Set `HL_OWNER_ADDRESS` to your main account address

#### Verify Connection
On startup the bot logs:
```
🚀 Initializing Hyperliquid adapter (mainnet)
⚙️ Setting leverage for SOL: {USER_DEFINED_LEVERAGE}x (cross)
```

### 2. Google Sheets Setup

#### Create Service Account
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create new project or select existing
3. Enable Google Sheets API
4. Enable Google Drive API
5. Create Service Account:
   - IAM & Admin → Service Accounts → Create Service Account
   - Name: "Trading Bot Logger"
   - Grant "Editor" role (or custom role with Sheets/Drive permissions)
6. Create Key:
   - Click service account → Keys → Add Key → JSON
   - Download JSON file
   - Save as `service_account.json` in project root

#### Create and Share Sheet
1. Create Google Sheet named "Trading Bot"
2. Click "Share" button
3. Add service account email (from JSON file: `client_email` field)
4. Grant "Editor" access
5. Sheet ID or name will be accessed automatically by `gspread`

### [Removed] Email Setup (not used)

### [Removed] Proxy Setup (not required)

---

## API Endpoints

### Main Webhook Endpoint

#### `POST /webhook`
Primary endpoint for receiving trading signals.

**Request Body:**
```json
{
  "action": "buy"  // or "sell"
}
```

**Response (Success):**
```json
{
  "status": "success",
  "message": "Buy order executed.",
  "entry_price": 150.25,
  "quantity": 0.125
}
```

**Response (Ignored - Cooldown):**
```json
{
  "status": "ignored",
  "message": "Buy cooldown in effect."
}
```

**Response (Ignored - Already in Position):**
```json
{
  "status": "ignored",
  "message": "Already in position."
}
```

**Response (Error):**
```json
{
  "status": "error",
  "message": "Error description"
}
```

**Usage Example:**
```bash
curl -X POST http://localhost:5000/webhook \
  -H "Content-Type: application/json" \
  -d '{"action": "buy"}'
```

### Test Endpoints

#### `GET /test_buy`
Executes a test buy order to open a long position (bypasses webhook validation).

**Response:**
```
✅ Test buy executed.
```

**Use Case:** Testing long position opening logic without external webhook.

#### `GET /test_sell`
Executes a test sell order to close a long position (bypasses webhook validation).

**Response:**
```
✅ Test sell executed.
```

**Use Case:** Testing long position closing logic without external webhook.

#### `GET /test_short`
Executes a test sell order to open a short position (bypasses webhook validation).

**Response:**
```
✅ Test short executed.
```

**Use Case:** Testing short position opening logic without external webhook.

#### `GET /test_close_short`
Executes a test buy order to close a short position (bypasses webhook validation).

**Response:**
```
✅ Test close short executed.
```

**Use Case:** Testing short position closing logic without external webhook.

### Emergency Endpoints

#### `GET /force_sell`
Forces exit of current position by placing a reduce-only market order for the full position size.

**Response (Success):**
```json
{
  "status": "success",
  "message": "Force sell executed."
}
```

**Response (No Position):**
```json
{
  "status": "ignored",
  "message": "No open position to force sell."
}
```

**Use Case:** Emergency exit when normal sell fails or position tracking is incorrect.

### Position Management Endpoints

#### `GET /position_open`
Manually sets position state to "open" (for recovery scenarios).

**Response:**
```json
{
  "status": "success",
  "message": "position is set to open"
}
```

**Use Case:** Recovering from bot restart when position was open.

#### `GET /position_closed`
Manually sets position state to "closed" (for recovery scenarios).

**Response:**
```json
{
  "status": "success",
  "message": "position is set to closed"
}
```

**Use Case:** Resetting bot state after manual position closure.

---

## Trading Logic

### Position Tracking

The bot maintains global state variables:

```python
in_position       = False  # Whether currently holding a position
entry_price       = None   # Price at which position was opened
position_quantity = None   # Quantity of tokens held
buy_time          = None   # UTC timestamp of buy order
sell_time         = None   # UTC timestamp of sell order
last_trade_timestamp = 0   # Last trade execution time (for cooldown)
```

### Buy Logic

1. **Validation Checks:**
   - Cooldown period elapsed (600 seconds)
   - Not already in position
   - Sufficient USDC margin

2. **Order Calculation:**
   - Available balance: withdrawable USDC margin
   - Capital to use: `balance * 0.11` (11%)
   - Current price: current mid price for SOL/USDC
   - Quantity: `(capital_to_use / current_price)` rounded to 0.001

3. **Execution:**
   - Market buy order on Hyperliquid
   - Extract average fill price from order response
   - Store entry price, quantity, buy time
   - Start stop-loss monitoring thread

### Sell Logic

1. **Validation Checks:**
   - Position is open
   - Cooldown period elapsed
   - Valid position quantity

2. **Execution:**
   - Reduce-only market sell on Hyperliquid for `position_quantity`
   - Capture average fill price from order response
   - Calculate PnL with fees

3. **PnL Calculation (Long Positions):**
   ```python
   # Long: Buy at entry, sell at exit
   buy_cost = (entry_price * quantity) * (1 + TAKER_FEE_RATE)       # 0.0432% fee
   sell_revenue = (sell_price * quantity) * (1 - MAKER_FEE_RATE)    # 0.0144% fee
   pnl = sell_revenue - buy_cost
   ```

4. **Post-Sell Actions:**
   - Log to Google Sheets with position_side="long"
   - Clear position state
   - Stop monitoring thread

### Short Position Logic

1. **Opening Short:**
   - Market sell order with `reduce_only=False` creates negative position
   - Entry price = sell price (higher is better)
   - Break-even = `entry_price * (1 - (TAKER_FEE_RATE + MAKER_FEE_RATE))`

2. **Closing Short:**
   - Market buy order with `reduce_only=True` closes negative position
   - Exit price = buy price (lower is better for profit)

3. **PnL Calculation (Short Positions):**
   ```python
   # Short: Sell at entry (high), buy back at exit (low)
   sell_revenue = (entry_price * quantity) * (1 - TAKER_FEE_RATE)   # 0.0432% fee
   buy_cost = (exit_price * quantity) * (1 + MAKER_FEE_RATE)        # 0.0144% fee
   pnl = sell_revenue - buy_cost
   # Profit when exit_price < entry_price
   ```

4. **Stop-Loss for Shorts:**
   - Triggers when price goes UP: `entry_price * (1 + STOP_LOSS_PERCENT_SHORT)`
   - Profit target when price goes DOWN: `break_even_price * (1 - TARGET_PROFIT_PERCENT)`

5. **Price Tracking for Shorts:**
   - **Highest price** = worst case (loss increases as price rises)
   - **Lowest price** = best case (profit when price drops)

### Stop-Loss Monitoring

**Thread Behavior:**
- Daemon thread runs while `stop_safety_net` event is not set
- Checks price every 5 seconds
- Calculates threshold: `entry_price * (1 - 0.007)` = 99.3% of entry

**Trigger Conditions:**
- Current price ≤ stop-loss threshold
- Error in price fetching (falls back to force exit)

**Fallback Mechanism:**
- If normal sell fails → attempts force exit
- Force exit uses 98% of available wallet balance
- Ensures position is closed even if tracking is incorrect

### Cooldown Mechanism

**Purpose:** Prevents overtrading and respects indicator signals (e.g., Supertrend with 10-minute periods).

**Implementation:**
- Tracks `last_trade_timestamp` globally
- On webhook: `if (current_time - last_trade_timestamp) < 600: ignore`
- Applied to both buy and sell actions
- Reset after successful order execution

**Current Setting:** 600 seconds (10 minutes)

---

## Deployment

### Local Deployment

#### Windows
```powershell
# Activate virtual environment
venv\Scripts\activate

# Run bot
python app.py

# Or with custom port
$env:PORT=8080; python app.py
```

#### Linux/Mac
```bash
# Activate virtual environment
source venv/bin/activate

# Run bot
python app.py

# Or with custom port
PORT=8080 python app.py
```

### Cloud Deployment

#### Heroku
1. Create `Procfile`:
   ```
   web: python app.py
   ```
2. Deploy:
   ```bash
   heroku create trading-bot
   heroku config:set PORT=5000
   git push heroku main
   ```

#### AWS EC2 / DigitalOcean
1. SSH into server
2. Install Python and dependencies
3. Use process manager (PM2, systemd, supervisor):
   ```bash
   # Example with systemd
   sudo nano /etc/systemd/system/tradingbot.service
   ```
   ```ini
   [Unit]
   Description=Hyperliquid Trading Bot
   After=network.target

   [Service]
   User=your-user
   WorkingDirectory=/path/to/TradingBotHyperLiquid
   ExecStart=/path/to/venv/bin/python app.py
   Restart=always

   [Install]
   WantedBy=multi-user.target
   ```
4. Enable and start:
   ```bash
   sudo systemctl enable tradingbot
   sudo systemctl start tradingbot
   ```

#### Docker (Recommended)
Create `Dockerfile`:
```dockerfile
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

CMD ["python", "app.py"]
```

Build and run:
```bash
docker build -t trading-bot .
docker run -p 5000:5000 trading-bot
```

### Webhook Access

For external signals to reach your bot:

#### Option 1: Public IP (VPS/Cloud)
- Bot accessible via public IP
- Configure firewall: allow port 5000 (or custom port)
- Webhook URL: `http://your-ip:5000/webhook`

#### Option 2: Ngrok (Local Testing)
```bash
ngrok http 5000
```
Use provided URL: `https://abc123.ngrok.io/webhook`

#### Option 3: Cloudflare Tunnel
```bash
cloudflared tunnel --url http://localhost:5000
```

#### Option 4: Reverse Proxy (Nginx)
```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

## Security Considerations

### ⚠️ CRITICAL SECURITY WARNINGS

**Current Implementation Issues:**

1. **Hardcoded Credentials**
   - Hyperliquid Agent private key and owner address should not be hardcoded
   - [Removed] Proxy credentials were previously hardcoded
   - Service account JSON contains private keys

2. **Exposed Secrets**
   - If code is committed to public repository, credentials are exposed
   - Anyone with file access can see sensitive information

### Recommended Security Improvements

#### 1. Use Environment Variables

**Create `.env` file:**
```env
HL_OWNER_ADDRESS=0x...
HL_AGENT_PRIVATE_KEY=0x...
```

**Install python-dotenv:**
```bash
pip install python-dotenv
```

**Update `app.py`:**
```python
from dotenv import load_dotenv
load_dotenv()

# Adapter reads HL_* envs via from_env()
```

**Add to `.gitignore`:**
```
.env
service_account.json
*.json
```

#### 2. Secure Service Account JSON

- Store `service_account.json` outside repository
- Use environment variable for path: `GOOGLE_SERVICE_ACCOUNT_PATH`
- Never commit service account files

#### 3. API Key Permissions

- Use minimal required permissions
- Enable IP whitelist if available
- Rotate keys periodically
- **Never enable withdrawal permissions** unless absolutely necessary

#### 4. Webhook Security

Add authentication to webhook endpoint:

```python
@app.route('/webhook', methods=['POST'])
def webhook():
    # Verify webhook secret
    webhook_secret = request.headers.get('X-Webhook-Secret')
    if webhook_secret != os.getenv('WEBHOOK_SECRET'):
        return jsonify({"status": "unauthorized"}), 401
    
    # ... rest of webhook logic
```

#### 5. Network Security

- Use HTTPS with reverse proxy (Let's Encrypt SSL)
- Restrict access by IP if possible
- Use VPN or private network for deployment

#### 6. Regular Audits

- Review logs for unauthorized access
- Review Agent Wallet authorizations in Hyperliquid app
- Check Google Sheets access logs
- Rotate credentials periodically

---

## Monitoring & Logging

### Console Logging

The bot outputs detailed logs to console with emoji indicators:

- 🚀 System startup
- 📩 Webhook received
- ⏳ Cooldown active
- ⚠️ Warnings (already in position, no position, etc.)
- ✅ Successful operations
- ❌ Errors
- 🛒 Buy orders
- 📉 Sell orders
- 🛡️ Stop-loss monitoring
- 💰 Position updates

### Google Sheets Logging

**Sheet:** "Trading Bot" → Sheet1

**Columns:**
1. Entry Price - Price at which position was opened
2. Sell Price - Price at which position was closed
3. Position Quantity - Amount of tokens traded
4. PnL - Profit/Loss (with fees included)
5. Time Diff - Duration position was held (seconds)
6. Formatted Date Time - ISO timestamp of sell
7. Sell Reason - Reason for sell ("normal sell", "stop loss triggered", "force exit", "webhook close long/short")
8. Percent of Trade - Percentage calculation (entry_price/100 * pnl)
9. Highest Price - Highest price reached during trade
10. Highest % from Break-even - Percentage difference of highest price from break-even
11. Lowest Price - Lowest price reached during trade
12. Lowest/Highest Drawdown % - For longs: lowest drawdown from entry; For shorts: highest drawdown from entry
13. **Position Type** - "long" or "short" (NEW)

**Access:** View in Google Sheets, export to CSV for analysis

**Analysis Tips:**
- Filter by Position Type to analyze long vs short performance separately
- Use "Lowest/Highest Drawdown %" to optimize stop-loss settings for each position type
- Compare PnL between long and short positions to identify which strategy performs better

### [Removed] Email Notifications (not used)

### Monitoring Best Practices

1. **Check Logs Regularly**
   - Monitor console output for errors
   - Review stop-loss triggers

2. **Review Google Sheets**
   - Track win rate
   - Analyze PnL trends
   - Monitor position durations

3. **Hyperliquid App**
   - Verify orders executed correctly
   - Check margin and positions
   - Review Agent Wallet status

4. [Removed] Email Alerts

### Performance Metrics to Track

- Win rate: `(winning_trades / total_trades) * 100`
- Average PnL per trade
- Average position duration
- Stop-loss trigger frequency
- Cooldown effectiveness (trades prevented)

---

## Troubleshooting

### Common Issues

#### 1. "Insufficient USDC balance"
**Symptoms:** Buy order fails with balance error

**Solutions:**
- Check USDC balance/margin: Verify in Hyperliquid app
- Reduce capital allocation (currently 11%, hardcoded)
- Ensure balance accounts for trading fees

#### 2. "Failed to write to Google Sheet"
**Symptoms:** Error logging trades to sheets

**Solutions:**
- Verify `service_account.json` exists and is valid
- Check service account has access to sheet "Trading Bot"
- Ensure Google Sheets API is enabled
- Verify sheet name matches exactly (case-sensitive)

#### 3. "Error sending email"
**Symptoms:** Email notifications not received

**Solutions:**
- Verify GMX SMTP credentials are correct
- Check GMX account is not locked
- Test SMTP connection manually
- Verify sender/recipient emails are correct

#### [Removed] Proxy Connection Errors (proxy not used)

#### 5. Stop-Loss Not Triggering
**Symptoms:** Price drops below threshold but position not sold

**Solutions:**
- Check thread is running: Look for "🛡️ Safety net activated" in logs
- Verify stop-loss thread hasn't crashed (check error logs)
- Manually trigger `/force_sell` if needed
- Restart bot if thread stopped

#### 6. "Already in position" When Not
**Symptoms:** Bot thinks position is open but it's not

**Solutions:**
- Check Hyperliquid app for actual position
- Use `/position_closed` endpoint to reset state
- If position actually exists, use `/force_sell` to close
- Restart bot after manual position closure

#### 7. Cooldown Preventing Legitimate Trades
**Symptoms:** Webhook signals ignored due to cooldown

**Solutions:**
- Reduce `TRADE_COOLDOWN` value (currently 600 seconds)
- Use test endpoints (`/test_buy`, `/test_sell`) to bypass cooldown
- Check `last_trade_timestamp` logic

#### 8. Webhook Not Receiving Signals
**Symptoms:** External signals not reaching bot

**Solutions:**
- Verify bot is running: `curl http://localhost:5000/test_buy`
- Check firewall allows port 5000
- If using tunnel (Ngrok), verify URL is correct
- Check webhook sender is using correct URL and method (POST)
- Review Flask logs for incoming requests

#### 9. Quantity Precision Errors
**Symptoms:** Hyperliquid rejects orders due to quantity precision

**Solutions:**
- Ensure size respects market `sizeIncrement` (adapter enforces rounding)
- Adjust rounding in `execute_buy_order()` if needed
- Default precision used: 0.001 SOL

#### 10. Bot Crashes on Startup
**Symptoms:** Bot fails immediately after starting

**Solutions:**
- Check all credentials are valid
- Verify `service_account.json` exists
- Verify HL env vars and Agent Wallet authorization
- Check Python version: `python --version` (requires 3.7+)
- Verify all dependencies installed: `pip list`

### Debug Mode

Enable detailed logging:

```python
logging.basicConfig(level=logging.DEBUG)
```

This is already enabled (line 18), so check console for detailed error messages.

### Manual Recovery Procedures

#### Recovering from Bot Restart (Position Was Open)

1. Check actual position in Hyperliquid
2. If position exists:
   ```bash
   curl http://localhost:5000/position_open
   ```
3. Manually update entry price and quantity if needed (requires code modification)
4. Bot will resume stop-loss monitoring

#### Force Closing Stuck Position

```bash
curl http://localhost:5000/force_sell
```

This closes position using available wallet balance.

#### Resetting Bot State

```bash
# Close position state
curl http://localhost:5000/position_closed

# Verify state reset
curl http://localhost:5000/test_buy  # Should work if no position
```

---

## Additional Resources

### Hyperliquid Documentation
- Hyperliquid Docs: https://hyperliquid.gitbook.io/hyperliquid-docs
- Python SDK: https://github.com/hyperliquid-dex/hyperliquid-python-sdk

### Google Sheets API
- [Google Sheets API](https://developers.google.com/sheets/api)
- [gspread Documentation](https://gspread.readthedocs.io/)

### Flask Documentation
- [Flask Quickstart](https://flask.palletsprojects.com/)

---

## License

[Add your license information here]

---

## Support

For issues, questions, or contributions, please [add your contact method or issue tracker].

---

**Last Updated:** [Current Date]  
**Version:** 1.0  
**Maintained by:** [Your Name/Team]

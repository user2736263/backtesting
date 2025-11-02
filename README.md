# Binance Trading Bot - Comprehensive Documentation

An automated cryptocurrency trading bot for Binance that executes trades based on webhook signals, with integrated stop-loss protection, position management, and comprehensive logging.

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

This trading bot is designed to automatically execute cryptocurrency trades on Binance based on webhook signals from external trading indicators or strategies. The bot provides:

- **Automated Trade Execution**: Market buy/sell orders triggered via webhook
- **Stop-Loss Protection**: Background monitoring thread automatically sells if price drops below threshold
- **Position Management**: Tracks open positions and prevents duplicate trades
- **Trade Cooldown**: Prevents overtrading with configurable cooldown periods
- **Comprehensive Logging**: All trades logged to Google Sheets with detailed metrics
- **Email Notifications**: Automatic PnL notifications after each trade closure
- **Proxy Support**: Uses Oxylabs proxy for secure API connections
- **Emergency Controls**: Force exit and manual position management endpoints

**Current Trading Pair**: SOL/USDT  
**Default Stop-Loss**: 0.7% below entry price  
**Capital Allocation**: 11% of available USDT balance per trade  
**Trade Cooldown**: 600 seconds (10 minutes)

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
    │  Execute     │ → Binance API (via Proxy)
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
    │  Logging &   │ → Google Sheets + Email notification
    │  Notification│
    └──────────────┘
```

### Workflow Details

#### 1. **Webhook Reception**
- Flask server listens on `/webhook` endpoint (POST)
- Receives JSON payload with `action` field ("buy" or "sell")
- Validates cooldown period (prevents trades within 600 seconds of last trade)
- Checks current position status (prevents duplicate buys/sells)

#### 2. **Buy Order Execution**
- Validates sufficient USDT balance
- Calculates trade size: 11% of available USDT
- Fetches current market price for SOL/USDT
- Calculates quantity with proper precision (0.001 SOL)
- Executes market buy order via Binance API
- Stores entry price, quantity, and timestamp
- Activates stop-loss monitoring thread

#### 3. **Stop-Loss Monitoring**
- Background daemon thread runs continuously while position is open
- Checks current price every 5 seconds
- Calculates stop-loss threshold: `entry_price * (1 - 0.007)` = 0.7% below entry
- If price drops to or below threshold:
  - Attempts to execute sell order
  - Falls back to force exit if sell fails
  - Logs trade with reason "stop loss triggered"

#### 4. **Sell Order Execution**
- Validates position is open
- Executes market sell order for tracked quantity
- Calculates PnL: `(sell_revenue - sell_fees) - (buy_cost + buy_fees)`
- Logs trade details to Google Sheets:
  - Entry price, sell price, quantity
  - PnL, time difference, timestamp
  - Sell reason (normal sell, stop loss, force exit)
- Sends email notification with PnL
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

1. **Binance Account**
   - Active Binance account with API access enabled
   - API Key and Secret Key with trading permissions
   - Sufficient USDT balance for trading

2. **Google Cloud Project**
   - Google Cloud account
   - Service account created with JSON key
   - Google Sheets API enabled
   - Google Drive API enabled

3. **Email Account**
   - GMX email account (or modify for other SMTP providers)
   - Email credentials for SMTP authentication

4. **Proxy Service**
   - Oxylabs proxy account (or modify for other proxy providers)
   - Proxy username and password

### Network Requirements

- Internet connection for API calls
- Public IP address or tunnel (Ngrok/Cloudflare Tunnel) for webhook access
- Port 5000 accessible (or configure custom port)

---

## Installation & Setup

### Step 1: Clone Repository

```bash
git clone <repository-url>
cd TradingBotBinance
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
- `python-binance` - Binance API client
- `gspread` - Google Sheets API client
- `oauth2client` - Google authentication
- `requests` - HTTP requests and proxy support
- `pandas`, `numpy` - Data processing (if needed)

### Step 4: Service Account Setup

1. Place your Google Service Account JSON file in the project root
2. Rename it to `service_account.json`
3. Ensure the service account has access to your Google Sheet named "Trading Bot"

### Step 5: Configure Credentials

**⚠️ SECURITY WARNING**: Currently, credentials are hardcoded in `app.py`. See [Security Considerations](#security-considerations) for recommended improvements.

Edit `app.py` and update:
- Binance API credentials (lines 150-151)
- Proxy credentials (lines 154-155)
- Email credentials (line 67)

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
| `SYMBOL` | `"SOL/USDT"` | Trading pair (format: BASE/QUOTE) |
| `STOP_LOSS_PERCENT` | `0.007` | Stop-loss percentage (0.7%) |
| `TRADING_FEE_RATE` | `0.001` | Binance trading fee (0.1%) |
| `TRADE_COOLDOWN` | `600` | Seconds between trades (10 minutes) |
| Capital Allocation | `11%` | Percentage of USDT balance per trade (hardcoded: `0.11` in line 302) |

### Binance API Configuration

```python
API_KEY    = 'your_binance_api_key'
API_SECRET = 'your_binance_secret_key'
```

**API Permissions Required:**
- Enable Spot & Margin Trading
- Read Info permissions
- Enable Withdrawals (if needed)

**Restrictions:**
- Do NOT enable "Enable Withdrawals" unless absolutely necessary
- Use IP whitelist if available
- Rotate keys periodically

### Proxy Configuration

```python
ProxyUsername = "your_oxylabs_username"
ProxyPassword = "your_oxylabs_password"

proxies = {
    "https": f"https://user-{ProxyUsername}:{ProxyPassword}@ddc.oxylabs.io:8002"
}
```

**Proxy Purpose:**
- Provides stable IP address
- May bypass some rate limits
- Adds layer of security

### Email Configuration

```python
sender_email    = "tradingbot@gmx-ist-cool.de"  # GMX alias
recipient_email = "your-email@gmx.ch"
```

SMTP settings (hardcoded):
- Server: `mail.gmx.net`
- Port: `587`
- Protocol: `STARTTLS`

### Google Sheets Configuration

- Sheet Name: `"Trading Bot"` (line 33)
- Uses first sheet (`sheet1`)
- Service account JSON: `service_account.json`

---

## Services Integration

### 1. Binance API Setup

#### Create API Keys
1. Log into Binance account
2. Go to API Management
3. Create new API key
4. Name it (e.g., "Trading Bot")
5. Enable "Enable Spot & Margin Trading"
6. **Do NOT enable "Enable Withdrawals"** unless required
7. Set IP whitelist if available
8. Save API Key and Secret Key securely

#### Verify Connection
The bot prints connection status on startup:
```
🚀 Using LIVE Binance via python‑binance
SYMBOL INFO: {...}
BALANCE: {...}
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

### 3. Email (GMX) Setup

#### GMX Email Configuration
1. Create GMX account at [gmx.com](https://www.gmx.com)
2. Enable SMTP access (usually enabled by default)
3. SMTP Settings:
   - Server: `mail.gmx.net`
   - Port: `587`
   - Security: STARTTLS
   - Username: Your GMX email
   - Password: Your GMX password

#### Email Alias (Optional)
- Create email alias if desired (e.g., `tradingbot@gmx-ist-cool.de`)
- Update `sender_email` in `send_email()` function

### 4. Oxylabs Proxy Setup

#### Create Account
1. Sign up at [oxylabs.io](https://oxylabs.io)
2. Choose proxy plan (Datacenter proxies recommended)
3. Get credentials from dashboard

#### Configuration
- Username format: Provided by Oxylabs
- Password: Provided by Oxylabs
- Endpoint: `ddc.oxylabs.io:8002` (for datacenter proxies)
- Authentication: Basic auth in URL format

#### Verify Connection
Bot tests proxy on startup:
```python
response = requests.get("https://ip.oxylabs.io/location", proxies=proxies)
print(response.text)  # Should show proxy location
```

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
Executes a test buy order (bypasses webhook validation).

**Response:**
```
✅ Test buy executed.
```

**Use Case:** Testing buy logic without external webhook.

#### `GET /test_sell`
Executes a test sell order (bypasses webhook validation).

**Response:**
```
✅ Test sell executed.
```

**Use Case:** Testing sell logic without external webhook.

### Emergency Endpoints

#### `GET /force_sell`
Forces exit of current position using available wallet balance (98% of free balance).

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
   - Sufficient USDT balance

2. **Order Calculation:**
   - Available balance: `balance = get_asset_balance('USDT')['free']`
   - Capital to use: `balance * 0.11` (11%)
   - Current price: `get_symbol_ticker('SOLUSDT')['price']`
   - Quantity: `(capital_to_use / current_price)` rounded to 0.001

3. **Execution:**
   - Market buy order: `order_market_buy(symbol='SOLUSDT', quantity=quantity)`
   - Extract fill price from order response
   - Store entry price, quantity, buy time
   - Start stop-loss monitoring thread

### Sell Logic

1. **Validation Checks:**
   - Position is open
   - Cooldown period elapsed
   - Valid position quantity

2. **Execution:**
   - Market sell order: `order_market_sell(symbol='SOLUSDT', quantity=position_quantity)`
   - Extract fill price from order response
   - Calculate PnL with fees

3. **PnL Calculation:**
   ```python
   buy_cost = (entry_price * quantity) + (entry_price * quantity * 0.001)
   sell_revenue = (sell_price * quantity) - (sell_price * quantity * 0.001)
   pnl = sell_revenue - buy_cost
   ```

4. **Post-Sell Actions:**
   - Log to Google Sheets
   - Send email notification
   - Clear position state
   - Stop monitoring thread

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
   Description=Binance Trading Bot
   After=network.target

   [Service]
   User=your-user
   WorkingDirectory=/path/to/TradingBotBinance
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
   - Binance API keys are in plain text in `app.py` (lines 150-151)
   - Email password is hardcoded (line 67)
   - Proxy credentials are hardcoded (lines 154-155)
   - Service account JSON contains private keys

2. **Exposed Secrets**
   - If code is committed to public repository, credentials are exposed
   - Anyone with file access can see sensitive information

### Recommended Security Improvements

#### 1. Use Environment Variables

**Create `.env` file:**
```env
BINANCE_API_KEY=your_api_key
BINANCE_API_SECRET=your_secret
PROXY_USERNAME=your_proxy_username
PROXY_PASSWORD=your_proxy_password
EMAIL_USERNAME=your_email@gmail.com
EMAIL_PASSWORD=your_email_password
SENDER_EMAIL=tradingbot@gmx-ist-cool.de
RECIPIENT_EMAIL=your-email@gmx.ch
```

**Install python-dotenv:**
```bash
pip install python-dotenv
```

**Update `app.py`:**
```python
from dotenv import load_dotenv
load_dotenv()

API_KEY = os.getenv('BINANCE_API_KEY')
API_SECRET = os.getenv('BINANCE_API_SECRET')
ProxyUsername = os.getenv('PROXY_USERNAME')
ProxyPassword = os.getenv('PROXY_PASSWORD')
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
- Monitor API usage in Binance dashboard
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
7. Sell Reason - Reason for sell ("normal sell", "stop loss triggered", "force exit")
8. Percent of Trade - Percentage calculation (entry_price/100 * pnl)

**Access:** View in Google Sheets, export to CSV for analysis

### Email Notifications

**Trigger:** After each sell order execution

**Format:**
- Subject: `PnL: {pnl_value}` (e.g., "PnL: 2.345678")
- Body: Empty (subject contains key information)
- From: `tradingbot@gmx-ist-cool.de`
- To: `remy3@gmx.ch` (configure in code)

**Use Case:** Quick mobile notifications of trade results

### Monitoring Best Practices

1. **Check Logs Regularly**
   - Monitor console output for errors
   - Review stop-loss triggers
   - Watch for proxy connection issues

2. **Review Google Sheets**
   - Track win rate
   - Analyze PnL trends
   - Monitor position durations

3. **Binance Dashboard**
   - Verify orders executed correctly
   - Check balance changes
   - Review API usage

4. **Email Alerts**
   - Set up email forwarding to mobile
   - Create filters for PnL alerts

### Performance Metrics to Track

- Win rate: `(winning_trades / total_trades) * 100`
- Average PnL per trade
- Average position duration
- Stop-loss trigger frequency
- Cooldown effectiveness (trades prevented)

---

## Troubleshooting

### Common Issues

#### 1. "Insufficient USDT balance"
**Symptoms:** Buy order fails with balance error

**Solutions:**
- Check USDT balance: Verify in Binance account
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

#### 4. Proxy Connection Errors
**Symptoms:** API calls fail, proxy errors in logs

**Solutions:**
- Verify Oxylabs credentials are correct
- Check proxy account is active and has credits
- Test proxy connection: `curl --proxy ... https://ip.oxylabs.io/location`
- Consider removing proxy temporarily for testing

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
- Check Binance account for actual position
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
**Symptoms:** Binance rejects orders due to quantity precision

**Solutions:**
- Verify symbol precision: `client.get_symbol_info("SOLUSDT")`
- Check `LOT_SIZE` filter for minimum/maximum quantity
- Adjust rounding in `execute_buy_order()` if needed
- Current precision: 0.001 SOL

#### 10. Bot Crashes on Startup
**Symptoms:** Bot fails immediately after starting

**Solutions:**
- Check all credentials are valid
- Verify `service_account.json` exists
- Test Binance connection manually
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

1. Check actual position in Binance
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

### Binance API Documentation
- [Binance API Docs](https://binance-docs.github.io/apidocs/spot/en/)
- [Python-Binance Library](https://python-binance.readthedocs.io/)

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

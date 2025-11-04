# --- No changes here (imports & logging) ---
import threading
import time
from flask import Flask, request, jsonify
import os
import logging
import csv
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import datetime
import math
from decimal import Decimal, ROUND_DOWN
from dotenv import load_dotenv
from exchanges.hyperliquid_adapter import from_env as hl_from_env

# Load environment variables
load_dotenv()

logging.basicConfig(level=logging.DEBUG)

def get_gsheet_client():
    scope = ["https://spreadsheets.google.com/feeds",
             "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name(
        "service_account.json", scope)
    client = gspread.authorize(creds)
    return client

# Profit calculation functions
def calculate_break_even_price(entry_price):
    """
    Calculate the break-even price that covers total trading fees.
    Break-even price = entry_price * (1 + (TAKER_FEE_RATE + MAKER_FEE_RATE))
    """
    total_fees = TAKER_FEE_RATE + MAKER_FEE_RATE  # Buy (taker) + Sell (maker)
    break_even = entry_price * (1 + total_fees)
    return break_even

def calculate_target_profit_price(break_even_price, target_percent):
    """
    Calculate the target profit price above break-even
    Target price = break_even_price * (1 + target_percent)
    """
    target_price = break_even_price * (1 + target_percent)
    return target_price

def calculate_break_even_price_short(entry_price):
    """
    For shorts: need to buy back lower to profit.
    Break-even = entry_price * (1 - (TAKER_FEE_RATE + MAKER_FEE_RATE))
    """
    total_fees = TAKER_FEE_RATE + MAKER_FEE_RATE
    break_even = entry_price * (1 - total_fees)
    return break_even

def calculate_target_profit_price_short(break_even_price, target_percent):
    """
    For shorts: target is BELOW break-even.
    Target price = break_even_price * (1 - target_percent)
    """
    target_price = break_even_price * (1 - target_percent)
    return target_price

#LOGGER TO GOOGLE SHEET
def save_to_gsheet(entry_price, sell_price, position_quantity,
                   pnl, time_diff, formatted_date_time, sell_reason, percent_of_trade,
                   highest_price, percent_diff_from_break_even, lowest_price, lowest_drawdown_pct,
                   position_side):
    try:
        client = get_gsheet_client()
        sheet = client.open("Trading Bot").sheet1
        sheet.append_row([
            entry_price,
            sell_price,
            position_quantity,
            pnl,
            round(time_diff, 2) if time_diff is not None else "N/A",
            formatted_date_time,
            sell_reason,
            percent_of_trade,
            highest_price if highest_price is not None else "N/A",
            round(percent_diff_from_break_even, 4) if percent_diff_from_break_even is not None else "N/A",
            lowest_price if lowest_price is not None else "N/A",
            round(lowest_drawdown_pct, 4) if lowest_drawdown_pct is not None else "N/A",
            position_side if position_side is not None else "N/A"
        ])
        print("✅ Logged to Google Sheet.")
    except Exception as e:
        print("❌ Failed to write to Google Sheet:", e)

#Force Trade SELL
def force_exit():
    global in_position, entry_price, position_quantity, stop_safety_net, sell_time
    global highest_price, lowest_price, break_even_price, target_profit_price, position_side

    print("⛔ FORCE EXIT: Attempting to close position using available wallet balance.")

    pos_size, _pos_entry = adapter.get_position(coin)
    if pos_size is None or pos_size == 0:
        print("❌ No open position to force close.")
        return

    is_short = pos_size < 0
    actual_size = abs(pos_size)
    detected_side = "short" if is_short else "long"

    try:
        if is_short:
            sell_avg_px, filled_sz = adapter.place_market_buy_reduce_only(coin, actual_size)
            print("Force closing SHORT position")
        else:
            sell_avg_px, filled_sz = adapter.place_market_sell_reduce_only(coin, actual_size)
            print("Force closing LONG position")
        
        sell_time = datetime.datetime.utcnow()
        formatted_date_time = sell_time.isoformat(timespec='milliseconds') + 'Z'
        exit_price = float(sell_avg_px)

        qty_for_pnl = float(Decimal(filled_sz).quantize(Decimal("0.001"), rounding=ROUND_DOWN))
        
        # Calculate PnL based on position type
        if is_short:
            # Short: sold at entry, buying back now
            sell_revenue = (entry_price * qty_for_pnl) * (1 - TAKER_FEE_RATE)
            buy_cost = (exit_price * qty_for_pnl) * (1 + MAKER_FEE_RATE)
            pnl = sell_revenue - buy_cost
        else:
            # Long: bought at entry, selling now
            buy_cost = (entry_price * qty_for_pnl) * (1 + TAKER_FEE_RATE)
            sell_revenue = (exit_price * qty_for_pnl) * (1 - MAKER_FEE_RATE)
            pnl = sell_revenue - buy_cost
        
        percent_of_trade = entry_price/100 * pnl if entry_price else 0
        time_diff = (sell_time - buy_time).total_seconds() \
                    if buy_time else None
        
        # Calculate percent difference of highest price from break-even
        percent_diff_from_break_even = None
        if highest_price is not None and break_even_price is not None:
            percent_diff_from_break_even = ((highest_price - break_even_price) / break_even_price) * 100
        
        # Calculate drawdown from entry
        drawdown_pct = None
        if is_short:
            # For shorts, highest price is worst
            if highest_price is not None and entry_price is not None:
                drawdown_pct = ((highest_price - entry_price) / entry_price) * 100
        else:
            # For longs, lowest price is worst
            if lowest_price is not None and entry_price is not None:
                drawdown_pct = ((lowest_price - entry_price) / entry_price) * 100

        print(f"✅ FORCE EXIT | Closed at ${exit_price:.6f}, PnL: ${pnl:.6f}")
        save_to_gsheet(entry_price, exit_price, qty_for_pnl,
                       pnl, time_diff, formatted_date_time, "force exit", percent_of_trade, 
                       highest_price, percent_diff_from_break_even, lowest_price, drawdown_pct,
                       position_side if position_side else detected_side)
        
    except Exception as e:
        print("❌ Force exit failed:", e)
    finally:
        in_position       = False
        entry_price       = None
        position_quantity = None
        position_side     = None
        highest_price     = None
        lowest_price      = None
        break_even_price  = None
        target_profit_price = None
        stop_safety_net.set()

#-------------setting trade status-------------
def position_open():
    print("setting position to true")
    global in_position
    in_position = True
    print("now in position")

def position_closed():
    print("setting position to false")
    global in_position
    in_position = False
    print("now not in position")
    
# --- Global State------------
# Load configuration from environment variables with defaults
SYMBOL                 = os.getenv("SYMBOL", "SOL/USDC")
STOP_LOSS_PERCENT      = float(os.getenv("STOP_LOSS_PERCENT", "0.007"))
STOP_LOSS_PERCENT_SHORT = float(os.getenv("STOP_LOSS_PERCENT_SHORT", "0.007"))
# Fee rates
TAKER_FEE_RATE         = float(os.getenv("TAKER_FEE_RATE", "0.000432"))  # 0.0432%
MAKER_FEE_RATE         = float(os.getenv("MAKER_FEE_RATE", "0.000144"))  # 0.0144%
TRADE_COOLDOWN         = int(os.getenv("TRADE_COOLDOWN", "600"))
CAPITAL_ALLOCATION_PERCENT = float(os.getenv("CAPITAL_ALLOCATION_PERCENT", "0.11"))
TARGET_PROFIT_PERCENT  = float(os.getenv("TARGET_PROFIT_PERCENT", "0.001"))

in_position            = False
entry_price            = None
position_quantity      = None
position_side          = None
safety_net_thread      = None
stop_safety_net        = threading.Event()
last_trade_timestamp   = 0
buy_time               = None
sell_time              = None
highest_price          = None
lowest_price           = None
break_even_price       = None
target_profit_price    = None

# --- Hyperliquid Adapter Setup ---
print("🚀 Initializing Hyperliquid adapter (mainnet)")
adapter = hl_from_env()
coin = SYMBOL.split('/')[0]
quote_asset = SYMBOL.split('/')[1]

# Apply user-defined leverage (cross by default)
try:
    user_leverage = float(os.getenv("USER_DEFINED_LEVERAGE", "1"))
    leverage_mode = os.getenv("LEVERAGE_MODE", "cross")
    if user_leverage > 0:
        print(f"⚙️ Setting leverage for {coin}: {user_leverage}x ({leverage_mode})")
        try:
            adapter.set_leverage(coin, user_leverage, leverage_mode)
            print("✅ Leverage set")
        except Exception as e:
            print("⚠️ Unable to set leverage:", e)
except Exception as e:
    print("⚠️ Leverage configuration error:", e)

# --- Flask --- main webhook---------------------------------------------------------------------------------
app = Flask(__name__)

@app.route('/')
def health():
    return jsonify({"status": "ok", "service": "Hyperliquid Trading Bot"}), 200

@app.route('/webhook', methods=['POST'])
def webhook():
    global in_position, entry_price, position_quantity, \
           stop_safety_net, last_trade_timestamp, position_side

    data = request.get_json()
    print("📩 Received webhook data:", data)
    print(f"[STATE] in_position: {in_position}, position_side: {position_side}, "
          f"entry_price: {entry_price}, quantity: {position_quantity}")

    action = data.get("action", "").lower()
    now    = time.time()

    # Check cooldown
    if now - last_trade_timestamp < TRADE_COOLDOWN:
        print("⏳ Cooldown active, ignoring signal.")
        return jsonify({"status":"ignored", "message":"Cooldown in effect."}),200

    if action == "buy":
        # BUY can mean: open long OR close short
        if in_position:
            if position_side == "short":
                # Close existing short position
                try:
                    execute_close_short_order(sell_reason="webhook close short")
                    last_trade_timestamp = time.time()
                    return jsonify({"status": "success", "message": "Short position closed."}), 200
                except Exception as e:
                    print("❌ Error closing short:", e)
                    return jsonify({"status":"error","message":str(e)}),500
            else:
                print("⚠️ Already in long position. Ignoring buy.")
                return jsonify({"status":"ignored", "message":"Already in long position."}),200
        else:
            # Open new long position
            try:
                execute_buy_order()
                last_trade_timestamp = time.time()
                return jsonify({
                    "status": "success",
                    "message": "Long position opened.",
                    "entry_price": entry_price,
                    "quantity": position_quantity
                }), 200
            except Exception as e:
                print("❌ Error opening long:", e)
                return jsonify({"status":"error","message":str(e)}),500

    elif action == "sell":
        # SELL can mean: close long OR open short
        if in_position:
            if position_side == "long":
                # Close existing long position
                try:
                    execute_sell_order(sell_reason="webhook close long")
                    last_trade_timestamp = time.time()
                    return jsonify({"status":"success", "message":"Long position closed."}),200
                except Exception as e:
                    print("❌ Error closing long:", e)
                    return jsonify({"status":"error","message":str(e)}),500
            else:
                print("⚠️ Already in short position. Ignoring sell.")
                return jsonify({"status":"ignored", "message":"Already in short position."}),200
        else:
            # Open new short position
            try:
                execute_short_order()
                last_trade_timestamp = time.time()
                return jsonify({
                    "status": "success",
                    "message": "Short position opened.",
                    "entry_price": entry_price,
                    "quantity": position_quantity
                }), 200
            except Exception as e:
                print("❌ Error opening short:", e)
                return jsonify({"status":"error","message":str(e)}),500

    print("⚠️ Unknown action received.")
    return jsonify({"status":"error",
                    "message":"Unknown action."}),400

#-----------------------------------other webhooks------------------------------------
@app.route('/test_buy')
def test_buy():
    try:
        execute_buy_order()
        return "✅ Test buy executed."
    except Exception as e:
        return f"❌ Error during test buy: {e}"

@app.route('/test_sell')
def test_sell():
    try:
        execute_sell_order()
        return "✅ Test sell executed."
    except Exception as e:
        return f"❌ Error during test sell: {e}"

@app.route('/test_short')
def test_short():
    try:
        execute_short_order()
        return "✅ Test short executed."
    except Exception as e:
        return f"❌ Error during test short: {e}"

@app.route('/test_close_short')
def test_close_short():
    try:
        execute_close_short_order()
        return "✅ Test close short executed."
    except Exception as e:
        return f"❌ Error during test close short: {e}"

@app.route('/force_sell')
def force_sell():
    global in_position
    if not in_position:
        print("⚠️ No position open. Force sell ignored.")
        return jsonify({"status":"ignored",
                        "message":"No open position to force sell."}),200
    try:
        force_exit()
        return jsonify({"status":"success",
                        "message":"Force sell executed."}),200
    except Exception as e:
        print("❌ Error during force sell:", e)
        return jsonify({"status":"error","message":str(e)}),500

@app.route('/position_open')
def position_open_call():
    position_open()
    return jsonify({"status": "success", "message": "position is set to open"}), 200

@app.route('/position_closed')
def position_close_call():
    position_closed()
    return jsonify({"status": "success", "message": "position is set to closed"}), 200

# --- Trade Logic -------------------------------------------------------------------------------
def execute_buy_order():
    global in_position, entry_price, position_quantity, stop_safety_net, buy_time
    global highest_price, lowest_price, break_even_price, target_profit_price

    print("🚀 Executing market BUY order...")

    quote_asset = SYMBOL.split('/')[1]
    
    try:
        withdrawable = adapter.get_withdrawable_usdc()
        if withdrawable is None:
            raise Exception("Unable to fetch withdrawable USDC.")
        balance = float(withdrawable)
        print(f"{quote_asset} Withdrawable:", balance)
    except Exception as e:
        print("💥 Error fetching withdrawable margin:", e)
        return

    if balance <= 0:
        raise Exception(f"Insufficient {quote_asset} balance.")

    capital_to_use = balance * CAPITAL_ALLOCATION_PERCENT
    current_price  = adapter.get_mid_price(coin)
    if current_price is None:
        raise Exception("Unable to fetch current mid price.")
    quantity_unrounded       = capital_to_use / float(current_price)
    quantity = Decimal(quantity_unrounded).quantize(Decimal("0.001"), rounding=ROUND_DOWN)
    
    # round to market size precision
    quantity = float(quantity)

    print(f"🛒 Buying {quantity} {SYMBOL} at "
          f"${current_price} using ${capital_to_use:.2f}")
    avg_price, filled_size = adapter.place_market_buy(coin, float(quantity))

    in_position = True
    position_side = "long"
    buy_time    = datetime.datetime.utcnow()

    entry_price       = float(avg_price)
    position_quantity = float(Decimal(filled_size).quantize(Decimal("0.001"), rounding=ROUND_DOWN))
    
    # Calculate break-even and target profit prices
    break_even_price = calculate_break_even_price(entry_price)
    target_profit_price = calculate_target_profit_price(break_even_price, TARGET_PROFIT_PERCENT)
    
    # Initialize highest and lowest price tracking
    highest_price = entry_price
    lowest_price = entry_price
    
    print(f"💰 Bought {position_quantity} of {SYMBOL} at ${entry_price:.6f}")
    print(f"📊 BREAK-EVEN PRICE: ${break_even_price:.6f} (covers {(TAKER_FEE_RATE + MAKER_FEE_RATE) * 100:.4f}% total fees)")
    print(f"🎯 TARGET PROFIT PRICE: ${target_profit_price:.6f} (target profit: {TARGET_PROFIT_PERCENT * 100}%)")
    print(f"📈 Starting price tracking at: ${entry_price:.6f}")

    stop_safety_net.clear()
    thread = threading.Thread(
        target=monitor_position,
        args=(entry_price,),
        daemon=True
    )
    thread.start()


def execute_short_order():
    global in_position, entry_price, position_quantity, stop_safety_net, buy_time
    global highest_price, lowest_price, break_even_price, target_profit_price, position_side

    print("🚀 Executing market SELL order (OPEN SHORT)...")

    quote_asset = SYMBOL.split('/')[1]
    
    try:
        withdrawable = adapter.get_withdrawable_usdc()
        if withdrawable is None:
            raise Exception("Unable to fetch withdrawable USDC.")
        balance = float(withdrawable)
        print(f"{quote_asset} Withdrawable:", balance)
    except Exception as e:
        print("💥 Error fetching withdrawable margin:", e)
        return

    if balance <= 0:
        raise Exception(f"Insufficient {quote_asset} balance.")

    capital_to_use = balance * CAPITAL_ALLOCATION_PERCENT
    current_price  = adapter.get_mid_price(coin)
    if current_price is None:
        raise Exception("Unable to fetch current mid price.")
    quantity_unrounded = capital_to_use / float(current_price)
    quantity = Decimal(quantity_unrounded).quantize(Decimal("0.001"), rounding=ROUND_DOWN)
    quantity = float(quantity)

    print(f"🛒 Shorting {quantity} {SYMBOL} at "
          f"${current_price} using ${capital_to_use:.2f}")
    avg_price, filled_size = adapter.place_market_sell(coin, float(quantity))

    in_position = True
    position_side = "short"
    buy_time = datetime.datetime.utcnow()

    entry_price = float(avg_price)
    position_quantity = float(Decimal(filled_size).quantize(Decimal("0.001"), rounding=ROUND_DOWN))
    
    # Calculate break-even and target profit (inverted for shorts)
    break_even_price = calculate_break_even_price_short(entry_price)
    target_profit_price = calculate_target_profit_price_short(break_even_price, TARGET_PROFIT_PERCENT)
    
    # Initialize price tracking
    highest_price = entry_price
    lowest_price = entry_price
    
    print(f"📉 Shorted {position_quantity} of {SYMBOL} at ${entry_price:.6f}")
    print(f"📊 BREAK-EVEN PRICE: ${break_even_price:.6f} (covers {(TAKER_FEE_RATE + MAKER_FEE_RATE) * 100:.4f}% total fees)")
    print(f"🎯 TARGET PROFIT PRICE: ${target_profit_price:.6f} (target profit: {TARGET_PROFIT_PERCENT * 100}%)")
    print(f"📈 Starting price tracking at: ${entry_price:.6f}")

    stop_safety_net.clear()
    thread = threading.Thread(
        target=monitor_position,
        args=(entry_price,),
        daemon=True
    )
    thread.start()


def execute_close_short_order(sell_reason="normal close short"):
    global in_position, entry_price, position_quantity, stop_safety_net, sell_time
    global highest_price, lowest_price, break_even_price, position_side

    print(f"📈 Executing market BUY order to CLOSE SHORT (Reason: {sell_reason})")
    avg_price, filled_size = adapter.place_market_buy_reduce_only(coin, position_quantity)

    in_position = False
    sell_time = datetime.datetime.utcnow()
    formatted_date_time = sell_time.isoformat(timespec='milliseconds') + 'Z'
    time_diff = (sell_time - buy_time).total_seconds() if buy_time else None

    print("✅ Close short order filled size:", filled_size)
    exit_price = float(avg_price)

    # PnL for shorts: sold high (entry), bought low (exit) = profit
    sell_revenue = (entry_price * position_quantity) * (1 - TAKER_FEE_RATE)
    buy_cost = (exit_price * position_quantity) * (1 + MAKER_FEE_RATE)
    pnl = sell_revenue - buy_cost
    percent_of_trade = entry_price/100 * pnl
    
    # For shorts: highest price from break-even is BAD (loss potential)
    percent_diff_from_break_even = None
    if highest_price is not None and break_even_price is not None:
        percent_diff_from_break_even = ((highest_price - break_even_price) / break_even_price) * 100
    
    # For shorts: highest drawdown = how far price went UP from entry (negative for shorts)
    highest_drawdown_pct = None
    if highest_price is not None and entry_price is not None:
        highest_drawdown_pct = ((highest_price - entry_price) / entry_price) * 100

    print(f"📊 Short trade closed | Entry: ${entry_price:.6f}, "
          f"Exit: ${exit_price:.6f}, Qty: {position_quantity}, "
          f"PnL: ${pnl:.6f}, Time: {time_diff}s")
    if highest_price is not None:
        print(f"📈 Highest price during trade (worst): ${highest_price:.6f}")
    if percent_diff_from_break_even is not None:
        print(f"📊 Highest price % diff from break-even: {percent_diff_from_break_even:.4f}%")
    if lowest_price is not None:
        print(f"📉 Lowest price during trade (best): ${lowest_price:.6f}")
    if highest_drawdown_pct is not None:
        print(f"📊 Highest drawdown from entry: {highest_drawdown_pct:.4f}%")
    
    save_to_gsheet(entry_price, exit_price,
                   position_quantity, pnl,
                   time_diff, formatted_date_time, sell_reason, percent_of_trade, 
                   highest_price, percent_diff_from_break_even, lowest_price, highest_drawdown_pct,
                   position_side)

    in_position = False
    entry_price = None
    position_quantity = None
    position_side = None
    highest_price = None
    lowest_price = None
    break_even_price = None
    target_profit_price = None
    stop_safety_net.set()


def execute_sell_order(sell_reason="normal sell"):
    global in_position, entry_price, position_quantity, stop_safety_net, sell_time
    global highest_price, lowest_price, break_even_price

    print(f"📉 Executing market SELL order (Reason: {sell_reason})")
    avg_price, filled_size = adapter.place_market_sell_reduce_only(coin, position_quantity)

    in_position = False
    sell_time   = datetime.datetime.utcnow()
    formatted_date_time = sell_time.isoformat(timespec='milliseconds') + 'Z' #for time and date logging
    time_diff   = (sell_time - buy_time).total_seconds() \
                  if buy_time else None

    print("✅ Sell order filled size:", filled_size)
    sell_price = float(avg_price)

    buy_cost     = (entry_price * position_quantity) * (1 + TAKER_FEE_RATE)
    sell_revenue = (sell_price * position_quantity) * (1 - MAKER_FEE_RATE)
    pnl = sell_revenue - buy_cost
    percent_of_trade = entry_price/100 * pnl
    
    # Calculate percent difference of highest price from break-even
    percent_diff_from_break_even = None
    if highest_price is not None and break_even_price is not None:
        percent_diff_from_break_even = ((highest_price - break_even_price) / break_even_price) * 100
    
    # Calculate lowest price drawdown from entry
    lowest_drawdown_pct = None
    if lowest_price is not None and entry_price is not None:
        lowest_drawdown_pct = ((lowest_price - entry_price) / entry_price) * 100

    print(f"📊 Trade closed | Entry: ${entry_price:.6f}, "
          f"Sell: ${sell_price:.6f}, Qty: {position_quantity}, "
          f"PnL: ${pnl:.6f}, Time: {time_diff}s")
    if highest_price is not None:
        print(f"📈 Highest price during trade: ${highest_price:.6f}")
    if percent_diff_from_break_even is not None:
        print(f"📊 Highest price % diff from break-even: {percent_diff_from_break_even:.4f}%")
    if lowest_price is not None:
        print(f"📉 Lowest price during trade: ${lowest_price:.6f}")
    if lowest_drawdown_pct is not None:
        print(f"📊 Lowest drawdown from entry: {lowest_drawdown_pct:.4f}%")
    
    save_to_gsheet(entry_price, sell_price,
                   position_quantity, pnl,
                   time_diff, formatted_date_time, sell_reason, percent_of_trade, 
                   highest_price, percent_diff_from_break_even, lowest_price, lowest_drawdown_pct,
                   "long")

    in_position       = False
    entry_price       = None
    position_quantity = None
    position_side     = None
    highest_price     = None
    lowest_price      = None
    break_even_price  = None
    target_profit_price = None
    stop_safety_net.set()

def monitor_position(entry):
    global highest_price, lowest_price, break_even_price, target_profit_price, position_side
    
    print(f"🛡️ Position monitoring activated ({position_side} position). Tracking stop-loss and profit target...")
    
    # Load stop-loss percent based on position side
    if position_side == "short":
        stop_loss_pct = STOP_LOSS_PERCENT_SHORT
    else:
        stop_loss_pct = STOP_LOSS_PERCENT
    
    while not stop_safety_net.is_set():
        try:
            current_price = adapter.get_mid_price(coin)
            if current_price is None:
                raise Exception("No price returned")
            
            # Update highest price
            if highest_price is None or current_price > highest_price:
                highest_price = current_price
                print(f"📈 New highest price: ${highest_price:.6f}")
            
            # Update lowest price
            if lowest_price is None or current_price < lowest_price:
                lowest_price = current_price
                print(f"📉 New lowest price: ${lowest_price:.6f}")
            
            # Calculate thresholds based on position side
            if position_side == "short":
                # Short: stop-loss when price goes UP
                stop_loss_threshold = entry * (1 + stop_loss_pct)
                # Short: profit target when price goes DOWN
                profit_check = target_profit_price is not None and current_price <= target_profit_price
                stop_check = current_price >= stop_loss_threshold
            else:
                # Long: stop-loss when price goes DOWN
                stop_loss_threshold = entry * (1 - stop_loss_pct)
                # Long: profit target when price goes UP
                profit_check = target_profit_price is not None and current_price >= target_profit_price
                stop_check = current_price <= stop_loss_threshold
            
            # Status logging
            status_line = f"💰 Price: ${current_price:.6f} | Break-even: ${break_even_price:.6f} | Target: ${target_profit_price:.6f} | Highest: ${highest_price:.6f} | Lowest: ${lowest_price:.6f}"
            print(status_line)
            
            # Check stop-loss first (priority)
            if stop_check:
                print(f"❗ STOP-LOSS TRIGGERED! ${current_price:.6f} {'≥' if position_side == 'short' else '≤'} ${stop_loss_threshold:.6f}")
                try:
                    if position_side == "short":
                        execute_close_short_order(sell_reason="stop loss triggered")
                    else:
                        execute_sell_order(sell_reason="stop loss triggered")
                except Exception as e:
                    print("⚠️ Error in stop loss execution:", e)
                    print("⚠️ Attempting force exit...")
                    force_exit()
                break
            
            # Check profit target
            if profit_check:
                print(f"🎯 PROFIT TARGET REACHED! ${current_price:.6f} {'≤' if position_side == 'short' else '≥'} ${target_profit_price:.6f}")
                try:
                    if position_side == "short":
                        execute_close_short_order(sell_reason="profit target reached")
                    else:
                        execute_sell_order(sell_reason="profit target reached")
                except Exception as e:
                    print("⚠️ Error in profit target execution:", e)
                    print("⚠️ Attempting force exit...")
                    force_exit()
                break
                
        except Exception as e:
            print("⚠️ Error in position monitor:", e)
            print("⚠️ Attempting force exit...")
            force_exit()
            break
        time.sleep(5)

# --- Run Flask ---
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

import os
import telebot
from telebot import types
import json
import requests
import pandas as pd
import numpy as np
from datetime import datetime
from flask import Flask
from threading import Thread
import logging
import time
import sys

# ============ SETUP PS============
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Get Telegram token from environment
TOKEN = os.getenv('TELEGRAM_TOKEN')
if not TOKEN:
    logger.error("❌ ERROR: TELEGRAM_TOKEN environment variable not set!")
    logger.error("Please set it in Render.com dashboard → Environment")
    exit(1)

bot = telebot.TeleBot(TOKEN)
logger.info(f"✅ Bot initialized with token: {TOKEN[:10]}...")

# ============ DATA STORAGE ============
trades = []  # In-memory storage
user_data = {}  # Store user session data

# ============ FLASK WEB SERVER ============
app = Flask(__name__)

@app.route('/')
def home():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>MyCFJournalBot</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 800px; margin: 40px auto; padding: 20px; }
            .status { background: #4CAF50; color: white; padding: 10px; border-radius: 5px; }
            .container { background: #f5f5f5; padding: 20px; border-radius: 10px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🚀 MyCFJournalBot</h1>
            <div class="status">✅ Bot is running on Render.com</div>
            <p><strong>Status:</strong> Active</p>
            <p><strong>Uptime:</strong> Since deployment</p>
            <p><strong>Endpoints:</strong></p>
            <ul>
                <li><a href="/health">/health</a> - Health check</li>
                <li><a href="/stats">/stats</a> - Bot statistics</li>
            </ul>
        </div>
    </body>
    </html>
    """

@app.route('/health')
def health():
    return {"status": "healthy", "service": "mycfjournalbot", "timestamp": datetime.now().isoformat()}, 200

@app.route('/stats')
def stats():
    return {
        "bot_name": "MyCFJournalBot",
        "status": "running",
        "trades_logged": len(trades),
        "users": len(user_data),
        "server_time": datetime.now().isoformat()
    }, 200

# ============ BUTTON MENUS ============
def get_main_menu():
    """Returns the main menu keyboard"""
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add("🎯 NEW TRADE", "📊 DASHBOARD")
    markup.add("📝 JOURNAL", "💰 PERFORMANCE")
    markup.add("🧮 COMPOUND", "🔄 RESTART")
    return markup

def get_coin_menu():
    """Returns coin selection keyboard"""
    markup = types.ReplyKeyboardMarkup(row_width=3, resize_keyboard=True)
    markup.add("BTC", "ETH", "SOL")
    markup.add("ADA", "AVAX", "BNB")
    markup.add("Other", "🏠 MAIN MENU")
    return markup

def get_position_menu():
    """Returns position selection keyboard"""
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add("LONG 📈", "SHORT 📉")
    markup.add("🏠 MAIN MENU")
    return markup

# ============ BOT COMMAND HANDLERS ============

@bot.message_handler(commands=['start', 'help'])
def start_command(message):
    """Handle /start and /help commands"""
    welcome = """
🚀 *Welcome to MyCFJournalBot!*

*Your Crypto Futures Trading Journal*

*Quick Commands:*
/start - Show this menu
/trade - Log new trade
/journal - View today's trades
/performance - Your trading stats
/compound - Calculate projections
/ping - Check if bot is alive

*Features:*
• One-tap trade logging
• Futures market analysis  
• Compound calculator
• Performance tracking
• Psychology journaling

Tap 🎯 NEW TRADE below to begin!
"""
    
    bot.send_message(message.chat.id, welcome, 
                     parse_mode='Markdown', 
                     reply_markup=get_main_menu())
    
    logger.info(f"User {message.from_user.id} started bot")

@bot.message_handler(commands=['ping'])
def ping_command(message):
    """Handle /ping command"""
    bot.reply_to(message, "🏓 Pong! Bot is alive and running on Render.com")
    logger.info(f"Ping from user {message.from_user.id}")

@bot.message_handler(commands=['trade'])
def trade_command(message):
    """Handle /trade command"""
    new_trade(message)

@bot.message_handler(commands=['journal'])
def journal_command(message):
    """Handle /journal command"""
    show_journal(message)

@bot.message_handler(commands=['performance'])
def performance_command(message):
    """Handle /performance command"""
    show_performance(message)

@bot.message_handler(commands=['compound'])
def compound_command(message):
    """Handle /compound command"""
    show_compound(message)

# ============ BUTTON HANDLERS ============

@bot.message_handler(func=lambda msg: msg.text == "🎯 NEW TRADE")
def new_trade(message):
    """Handle NEW TRADE button"""
    try:
        # Get BTC price for context
        btc_price = get_btc_price()
        
        msg = f"""
📊 *Market Context*
────────────────
BTC: ${btc_price:,.2f}
Time: {datetime.now().strftime('%H:%M')}
Status: ✅ Live on Render

*Select coin to trade:*
        """
        
        bot.send_message(message.chat.id, msg, parse_mode='Markdown', reply_markup=get_coin_menu())
        
        # Store user state
        user_data[message.chat.id] = {"step": "coin"}
        
    except Exception as e:
        logger.error(f"Error in new_trade: {e}")
        bot.reply_to(message, "⚠️ Error getting market data. Try again.")

@bot.message_handler(func=lambda msg: msg.text in ["BTC", "ETH", "SOL", "ADA", "AVAX", "BNB", "Other"])
def handle_coin_selection(message):
    """Handle coin selection"""
    user_id = message.chat.id
    
    if user_id not in user_data:
        user_data[user_id] = {}
    
    user_data[user_id]["coin"] = message.text
    user_data[user_id]["step"] = "position"
    
    # Get coin price if not "Other"
    price_info = ""
    if message.text != "Other":
        try:
            price = get_coin_price(message.text)
            price_info = f"\nCurrent Price: ${price:,.2f}"
        except:
            pass
    
    msg = f"""
✅ *Coin Selected:* {message.text}
{price_info}

*Select position direction:*
    """
    
    bot.send_message(message.chat.id, msg, parse_mode='Markdown', reply_markup=get_position_menu())

@bot.message_handler(func=lambda msg: msg.text in ["LONG 📈", "SHORT 📉"])
def handle_position(message):
    """Handle position selection"""
    user_id = message.chat.id
    
    if user_id in user_data:
        position = "long" if "LONG" in message.text else "short"
        user_data[user_id]["position"] = position
        user_data[user_id]["step"] = "size"
        
        msg = f"""
✅ *Position:* {position.upper()}

*Enter position size (e.g., 0.1):*
        """
        
        bot.send_message(message.chat.id, msg, parse_mode='Markdown')
    else:
        bot.reply_to(message, "Please start with /trade first")

@bot.message_handler(func=lambda msg: msg.text == "🏠 MAIN MENU")
def main_menu_button(message):
    """Handle MAIN MENU button"""
    bot.send_message(message.chat.id, "Returning to main menu...", 
                     reply_markup=get_main_menu())
    # Clear any user session data
    if message.chat.id in user_data:
        del user_data[message.chat.id]

@bot.message_handler(func=lambda msg: msg.text == "📝 JOURNAL")
def journal_button(message):
    """Handle JOURNAL button"""
    show_journal(message)

@bot.message_handler(func=lambda msg: msg.text == "💰 PERFORMANCE")
def performance_button(message):
    """Handle PERFORMANCE button"""
    show_performance(message)

@bot.message_handler(func=lambda msg: msg.text == "🧮 COMPOUND")
def compound_button(message):
    """Handle COMPOUND button"""
    show_compound(message)

@bot.message_handler(func=lambda msg: msg.text == "📊 DASHBOARD")
def dashboard_button(message):
    """Handle DASHBOARD button"""
    show_dashboard(message)

@bot.message_handler(func=lambda msg: msg.text == "🔄 RESTART")
def restart_button(message):
    """Handle RESTART button"""
    bot.reply_to(message, "🔄 Bot is restarting... (Render will auto-restart if needed)")
    logger.info(f"Restart requested by user {message.from_user.id}")

# ============ SIZE AND ENTRY HANDLERS ============

@bot.message_handler(func=lambda msg: 
                     user_data.get(msg.chat.id, {}).get("step") == "size")
def handle_size(message):
    """Handle position size input"""
    try:
        size = float(message.text)
        user_id = message.chat.id
        
        user_data[user_id]["size"] = size
        user_data[user_id]["step"] = "entry"
        
        # Calculate approximate position value
        coin = user_data[user_id].get("coin", "BTC")
        if coin != "Other":
            try:
                price = get_coin_price(coin)
                value = price * size
                value_info = f"\nApprox Value: ${value:,.2f}"
            except:
                value_info = ""
        else:
            value_info = ""
        
        msg = f"""
✅ *Size:* {size}
{value_info}

*Enter entry price (e.g., 41500):*
        """
        
        bot.send_message(message.chat.id, msg, parse_mode='Markdown')
        
    except ValueError:
        bot.reply_to(message, "Please enter a valid number (e.g., 0.1)")

@bot.message_handler(func=lambda msg: 
                     user_data.get(msg.chat.id, {}).get("step") == "entry")
def handle_entry(message):
    """Handle entry price input"""
    try:
        entry = float(message.text)
        user_id = message.chat.id
        
        # Save the trade
        trade = {
            "id": len(trades) + 1,
            "user_id": user_id,
            "username": message.from_user.username,
            "timestamp": datetime.now().isoformat(),
            "coin": user_data[user_id].get("coin", "Unknown"),
            "position": user_data[user_id].get("position", "long"),
            "size": user_data[user_id].get("size", 0),
            "entry": entry,
            "status": "open",
            "pnl": 0,
            "result": "open"
        }
        
        trades.append(trade)
        
        # Clear user data
        if user_id in user_data:
            del user_data[user_id]
        
        # Success message
        success_msg = f"""
🎉 *TRADE LOGGED SUCCESSFULLY!*

*Trade #{trade['id']}*
• Coin: {trade['coin']}
• Position: {trade['position'].upper()}
• Size: {trade['size']}
• Entry: ${trade['entry']:,.2f}
• Time: {datetime.now().strftime('%H:%M')}

✅ *Saved to journal!*

Next steps:
1. Close trade when complete
2. Check /journal to view all trades
3. Use /performance for statistics
        """
        
        bot.send_message(message.chat.id, success_msg, parse_mode='Markdown', reply_markup=get_main_menu())
        
        logger.info(f"Trade logged: {trade}")
        
    except ValueError:
        bot.reply_to(message, "Please enter a valid price (e.g., 41500)")

# ============ FEATURE FUNCTIONS ============

def show_journal(message):
    """Show trading journal"""
    user_trades = [t for t in trades if t.get('user_id') == message.chat.id]
    
    if not user_trades:
        bot.reply_to(message, "📭 No trades recorded yet.\nUse /trade to log your first trade!", 
                     reply_markup=get_main_menu())
        return
    
    msg = "📝 *YOUR TRADING JOURNAL*\n\n"
    
    for trade in user_trades[-10:]:  # Last 10 trades
        date = datetime.fromisoformat(trade['timestamp']).strftime('%m/%d %H:%M')
        status = "🟢 OPEN" if trade.get('status') == 'open' else "🔴 CLOSED"
        
        msg += f"""
*Trade #{trade['id']}* {status}
{trade['coin']} {trade['position'].upper()}
Entry: ${trade['entry']:,.2f}
Size: {trade['size']}
Time: {date}
────────────────────
"""
    
    bot.send_message(message.chat.id, msg, parse_mode='Markdown', reply_markup=get_main_menu())

def show_performance(message):
    """Show performance statistics"""
    user_trades = [t for t in trades if t.get('user_id') == message.chat.id]
    closed_trades = [t for t in user_trades if t.get('status') == 'closed']
    
    if not user_trades:
        bot.reply_to(message, "No trades to analyze yet. Start trading!", 
                     reply_markup=get_main_menu())
        return
    
    # Calculate metrics
    total_trades = len(user_trades)
    open_trades = len([t for t in user_trades if t.get('status') == 'open'])
    
    if closed_trades:
        # Only calculate P&L for closed trades
        pnl_values = [t.get('pnl', 0) for t in closed_trades]
        total_pnl = sum(pnl_values)
        wins = sum(1 for pnl in pnl_values if pnl > 0)
        win_rate = (wins / len(closed_trades) * 100) if closed_trades else 0
        avg_pnl = total_pnl / len(closed_trades) if closed_trades else 0
    else:
        total_pnl = 0
        win_rate = 0
        avg_pnl = 0
    
    msg = f"""
💰 *PERFORMANCE DASHBOARD*

*Overview:*
• Total Trades: {total_trades}
• Open Positions: {open_trades}
• Closed Trades: {len(closed_trades)}

*Closed Trade Stats:*
• Win Rate: {win_rate:.1f}%
• Total P&L: ${total_pnl:.2f}
• Avg P&L: ${avg_pnl:.2f}

*Tips:*
• Aim for 60%+ win rate
• Risk management is key
• Journal every trade
        """
    
    bot.send_message(message.chat.id, msg, parse_mode='Markdown', reply_markup=get_main_menu())

def show_compound(message):
    """Show compound calculator"""
    msg = """
🧮 *COMPOUND CALCULATOR*

*The Magic of Compounding:*

*Example Scenario:*
• Starting Capital: $10,000
• Risk per Trade: 2% ($200)
• Target Gain: 20% of risk ($40)
• Win Rate: 60%

*After 100 trades:*
Expected Capital: ~$45,000
Growth: 350% 📈

*Key Formula:*
New Capital = Old Capital × (1 + (Win% × Reward% - Loss% × Risk%))

*Try This:*
1. Start with 2% risk per trade
2. Aim for 1:2 risk-reward ratio
3. Be consistent
4. Watch your capital grow!

💡 *Remember:* Small consistent gains > Big risky bets
        """
    
    bot.send_message(message.chat.id, msg, parse_mode='Markdown', reply_markup=get_main_menu())

def show_dashboard(message):
    """Show trading dashboard"""
    user_trades = [t for t in trades if t.get('user_id') == message.chat.id]
    
    msg = f"""
📊 *TRADING DASHBOARD*

*Quick Stats:*
Total Trades: {len(user_trades)}
Today's Trades: {len([t for t in user_trades if datetime.fromisoformat(t['timestamp']).date() == datetime.now().date()])}

*Market Overview:*
"""
    
    try:
        btc_price = get_btc_price()
        eth_price = get_coin_price("ETH")
        msg += f"""
BTC: ${btc_price:,.2f}
ETH: ${eth_price:,.2f}
"""
    except:
        msg += "Market data unavailable\n"
    
    msg += """
*Quick Actions:*
• Tap 🎯 NEW TRADE to log a trade
• Tap 📝 JOURNAL to review trades
• Tap 🧮 COMPOUND for projections
"""
    
    bot.send_message(message.chat.id, msg, parse_mode='Markdown', reply_markup=get_main_menu())

# ============ HELPER FUNCTIONS ============

def get_btc_price():
    """Get current BTC price from CoinGecko"""
    try:
        response = requests.get(
            "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd",
            timeout=5
        )
        data = response.json()
        return data['bitcoin']['usd']
    except:
        logger.warning("Failed to fetch BTC price, using fallback")
        return 42000  # Fallback price

def get_coin_price(coin):
    """Get price for specific coin"""
    coin_map = {
        "BTC": "bitcoin",
        "ETH": "ethereum", 
        "SOL": "solana",
        "ADA": "cardano",
        "AVAX": "avalanche-2",
        "BNB": "binancecoin"
    }
    
    coin_id = coin_map.get(coin.upper(), coin.lower())
    
    try:
        response = requests.get(
            f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd",
            timeout=5
        )
        data = response.json()
        return data[coin_id]["usd"]
    except:
        logger.warning(f"Failed to fetch {coin} price")
        return {
            "BTC": 42000,
            "ETH": 2200,
            "SOL": 100,
            "ADA": 0.5,
            "AVAX": 35,
            "BNB": 300
        }.get(coin.upper(), 100)

# ============ START SERVICES ============

def run_flask():
    """Start Flask web server for Render health checks"""
    port = int(os.getenv('PORT', 10000))
    logger.info(f"Starting Flask on port {port}")
    app.run(host='0.0.0.0', port=port)

def run_bot():
    """Run Telegram bot with error handling"""
    logger.info("🤖 Starting Telegram bot...")
    
    # Set bot commands for better UX
    bot.set_my_commands([
        telebot.types.BotCommand("start", "Start the bot"),
        telebot.types.BotCommand("trade", "Log a new trade"),
        telebot.types.BotCommand("journal", "View your trades"),
        telebot.types.BotCommand("performance", "View performance stats"),
        telebot.types.BotCommand("compound", "Compound calculator"),
        telebot.types.BotCommand("ping", "Check if bot is alive"),
    ])
    
    while True:
        try:
            logger.info("Starting bot polling...")
            bot.polling(none_stop=True, interval=0, timeout=20)
        except Exception as e:
            logger.error(f"Bot polling error: {e}")
            logger.info("Restarting bot in 5 seconds...")
            time.sleep(5)

if __name__ == "__main__":
    logger.info("=" * 50)
    logger.info("🚀 MyCFJournalBot Starting on Render.com")
    logger.info(f"Python version: {sys.version}")
    logger.info(f"Current directory: {os.getcwd()}")
    logger.info("=" * 50)
    
    # Start Flask web server in background
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    # Start Telegram bot
    run_bot()
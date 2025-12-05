# ADD THESE IMPORTS FIRST
import os
import sys

# Force Python version check
print(f"Python version: {sys.version}")
print(f"Current directory: {os.getcwd()}")
print(f"Files in directory: {os.listdir('.')}")

# Rest of your imports...
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

# Rest of your code...


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

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load token from environment
TOKEN = os.getenv('TELEGRAM_TOKEN')
if not TOKEN:
    logger.error("TELEGRAM_TOKEN not set!")
    exit(1)

bot = telebot.TeleBot(TOKEN)

# Web server for health checks
app = Flask('')

@app.route('/')
def home():
    return "🚀 MyCFJournalBot is running on Railway!"

@app.route('/health')
def health():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

def run_web():
    port = int(os.getenv('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

# Start web server
Thread(target=run_web, daemon=True).start()

# ============ TRADING JOURNAL CODE ============

# Simple data storage (in production, use database)
trades_file = "trades.json"

def load_trades():
    try:
        if os.path.exists(trades_file):
            with open(trades_file, 'r') as f:
                return json.load(f)
    except:
        pass
    return []

def save_trades(trades):
    with open(trades_file, 'w') as f:
        json.dump(trades, f, default=str)

# Button menus
def get_main_menu():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add("🎯 NEW TRADE", "📊 DASHBOARD")
    markup.add("📝 JOURNAL", "💰 PERFORMANCE")
    markup.add("🧮 COMPOUND", "⚙️ SETTINGS")
    return markup

# Bot commands
@bot.message_handler(commands=['start', 'help'])
def start_command(message):
    welcome = """
🚀 *Welcome to MyCFJournalBot!*

*Your Crypto Futures Trading Journal*

*Quick Commands:*
/start - Show this menu
/trade - Log new trade
/journal - View today's trades
/performance - Your trading stats
/compound - Calculate projections

*Features:*
• One-tap trade logging
• Futures market analysis
• Compound calculator
• Performance tracking
• Psychology journaling

Tap 🎯 NEW TRADE to begin!
"""
    bot.send_message(message.chat.id, welcome, 
                     parse_mode='Markdown', 
                     reply_markup=get_main_menu())

@bot.message_handler(func=lambda msg: msg.text == "🎯 NEW TRADE")
def new_trade(message):
    # Get market context
    try:
        btc_price = get_btc_price()
        market_msg = f"""
📊 *Market Context*
BTC: ${btc_price:,.2f}
Time: {datetime.now().strftime('%H:%M')}

*Ready to log your trade!*
        """
        bot.send_message(message.chat.id, market_msg, parse_mode='Markdown')
    except:
        bot.send_message(message.chat.id, "Let's log your trade!")
    
    # Ask for coin
    markup = types.ReplyKeyboardMarkup(row_width=3, resize_keyboard=True)
    markup.add("BTC", "ETH", "SOL")
    markup.add("ADA", "AVAX", "Other")
    markup.add("🏠 MAIN MENU")
    
    bot.send_message(message.chat.id, "Select coin:", reply_markup=markup)
    
    # Store user state (simplified)
    user_data[message.chat.id] = {"step": "coin"}

@bot.message_handler(func=lambda msg: msg.text in ["BTC", "ETH", "SOL", "ADA", "AVAX", "Other"])
def handle_coin(message):
    user_id = message.chat.id
    if user_id not in user_data:
        user_data[user_id] = {}
    
    user_data[user_id]["coin"] = message.text
    user_data[user_id]["step"] = "position"
    
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add("LONG 📈", "SHORT 📉")
    markup.add("🏠 MAIN MENU")
    
    bot.send_message(message.chat.id, f"{message.text} - Select position:", reply_markup=markup)

@bot.message_handler(func=lambda msg: msg.text in ["LONG 📈", "SHORT 📉"])
def handle_position(message):
    user_id = message.chat.id
    if user_id in user_data:
        position = "long" if "LONG" in message.text else "short"
        user_data[user_id]["position"] = position
        user_data[user_id]["step"] = "size"
        
        msg = f"Position: {position.upper()}\n\nEnter position size (e.g., 0.1):"
        bot.send_message(message.chat.id, msg)

# Helper functions
def get_btc_price():
    try:
        response = requests.get(
            "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd",
            timeout=5
        )
        data = response.json()
        return data['bitcoin']['usd']
    except:
        return 42000  # Fallback

@bot.message_handler(commands=['journal'])
def show_journal(message):
    trades = load_trades()
    user_trades = [t for t in trades if t.get('user_id') == message.chat.id]
    
    if not user_trades:
        bot.send_message(message.chat.id, "No trades recorded yet.")
        return
    
    msg = "📝 *Your Trading Journal*\n\n"
    for trade in user_trades[-5:]:  # Last 5 trades
        msg += f"""
• {trade.get('coin', 'N/A')} {trade.get('position', '').upper()}
  Entry: ${trade.get('entry', 0):,.2f}
  P&L: ${trade.get('pnl', 0):,.2f}
  Time: {trade.get('time', 'N/A')}
────────────────────
"""
    
    bot.send_message(message.chat.id, msg, parse_mode='Markdown')

@bot.message_handler(commands=['performance'])
def performance(message):
    trades = load_trades()
    user_trades = [t for t in trades if t.get('user_id') == message.chat.id]
    
    if not user_trades:
        bot.send_message(message.chat.id, "No trades to analyze.")
        return
    
    total_pnl = sum(t.get('pnl', 0) for t in user_trades)
    wins = sum(1 for t in user_trades if t.get('pnl', 0) > 0)
    win_rate = (wins / len(user_trades) * 100) if user_trades else 0
    
    msg = f"""
💰 *Performance Summary*

Total Trades: {len(user_trades)}
Win Rate: {win_rate:.1f}%
Total P&L: ${total_pnl:.2f}
Avg P&L per Trade: ${total_pnl/len(user_trades):.2f}

*Keep trading consistently!*
"""
    bot.send_message(message.chat.id, msg, parse_mode='Markdown')

@bot.message_handler(commands=['compound'])
def compound_calc(message):
    msg = """
🧮 *Compound Calculator*

*Example:*
Starting: $10,000
Risk per Trade: 2%
Target Gain: 20% of risk
Win Rate: 60%

After 100 trades: ~$45,000
Growth: 350%

*Key Insight:*
Consistency + Risk Management = Compounding Magic!
"""
    bot.send_message(message.chat.id, msg, parse_mode='Markdown')

# User data storage (in-memory, for demo)
user_data = {}

# Error handling
def polling_with_restart():
    while True:
        try:
            logger.info("Starting bot polling...")
            bot.polling(none_stop=True, interval=0, timeout=20)
        except Exception as e:
            logger.error(f"Bot error: {e}")
            import time
            time.sleep(5)

if __name__ == "__main__":
    logger.info("🤖 MyCFJournalBot starting on Railway...")
    logger.info(f"Token loaded: {'Yes' if TOKEN else 'No'}")
    
    # Create data directory if it doesn't exist
    if not os.path.exists('data'):
        os.makedirs('data')
    
    polling_with_restart()
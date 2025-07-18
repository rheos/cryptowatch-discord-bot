#!/bin/bash

# Start the new modular Discord bot

cd "$(dirname "$0")"

# Check if already running
if [ -f data/bot.pid ]; then
    PID=$(cat data/bot.pid)
    if ps -p $PID > /dev/null 2>&1; then
        echo "Bot is already running with PID $PID"
        exit 1
    fi
fi

# Create data directory if it doesn't exist
mkdir -p data

# Start the bot
echo "Starting CryptoWatch Discord bot..."
nohup python3 main.py > /dev/null 2>&1 &

# The bot writes its own PID file
sleep 2

if [ -f data/bot.pid ]; then
    echo "Bot started with PID $(cat data/bot.pid)"
    echo "Logs: tail -f bot.log"
    echo "Stop: ./stop-bot.sh"
else
    echo "Failed to start bot. Check bot.log for errors."
fi
#!/bin/bash

# Start the Discord bot in the background with nohup
# Redirect all output to /dev/null since we're using logging

cd "$(dirname "$0")"
nohup python3 crypto-watch-bot.py > /dev/null 2>&1 &
echo $! > bot.pid
echo "Bot started with PID $(cat bot.pid)"
echo "Logs are being written to bot.log"
#!/bin/bash

# Stop the Discord bot using the saved PID

if [ -f bot.pid ]; then
    PID=$(cat bot.pid)
    if ps -p $PID > /dev/null; then
        kill $PID
        echo "Bot stopped (PID $PID)"
        rm bot.pid
    else
        echo "Bot not running (PID $PID not found)"
        rm bot.pid
    fi
else
    echo "No bot.pid file found"
fi
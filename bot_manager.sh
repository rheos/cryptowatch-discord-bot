#!/bin/bash

# Discord Bot Manager Script

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BOT_PID_FILE="$SCRIPT_DIR/bot.pid"
BOT_LOG_FILE="$SCRIPT_DIR/logs/bot.log"

# Ensure logs directory exists
mkdir -p "$SCRIPT_DIR/logs"

start_bot() {
    if [ -f "$BOT_PID_FILE" ]; then
        PID=$(cat "$BOT_PID_FILE")
        if ps -p $PID > /dev/null 2>&1; then
            echo "Bot is already running with PID $PID"
            return 1
        else
            echo "Removing stale PID file"
            rm "$BOT_PID_FILE"
        fi
    fi
    
    # Source environment variables if .env exists
    if [ -f "$SCRIPT_DIR/.env" ]; then
        source "$SCRIPT_DIR/.env"
        echo "Loaded environment from .env (CONFIG_FILE=$CONFIG_FILE)"
    else
        echo "Warning: No .env file found. Using defaults."
    fi
    
    echo "Starting Discord bot..."
    cd "$SCRIPT_DIR"
    nohup python3 main.py >> "$BOT_LOG_FILE" 2>&1 &
    BOT_PID=$!
    echo $BOT_PID > "$BOT_PID_FILE"
    echo "Bot started with PID $BOT_PID"
    echo "Logs: tail -f $SCRIPT_DIR/logs/*.log"
    echo "Or specific logs: tail -f $SCRIPT_DIR/logs/timezone.log"
}

stop_bot() {
    if [ ! -f "$BOT_PID_FILE" ]; then
        echo "Bot is not running (no PID file found)"
        return 1
    fi
    
    PID=$(cat "$BOT_PID_FILE")
    if ps -p $PID > /dev/null 2>&1; then
        echo "Stopping bot with PID $PID..."
        kill $PID
        sleep 2
        
        # Force kill if still running
        if ps -p $PID > /dev/null 2>&1; then
            echo "Force killing bot..."
            kill -9 $PID
        fi
        
        rm "$BOT_PID_FILE"
        echo "Bot stopped"
    else
        echo "Bot is not running (process not found)"
        rm "$BOT_PID_FILE"
    fi
}

restart_bot() {
    echo "Restarting bot..."
    stop_bot
    sleep 1
    start_bot
}

status_bot() {
    if [ -f "$BOT_PID_FILE" ]; then
        PID=$(cat "$BOT_PID_FILE")
        if ps -p $PID > /dev/null 2>&1; then
            echo "Bot is running with PID $PID"
            echo "Uptime: $(ps -o etime= -p $PID | xargs)"
        else
            echo "Bot is not running (stale PID file)"
        fi
    else
        echo "Bot is not running"
    fi
}

logs_bot() {
    echo "Available log files:"
    ls -la "$SCRIPT_DIR/logs/"*.log 2>/dev/null | grep -v "bot.log" | awk '{print "  - " $9}'
    echo ""
    echo "Following all logs (Ctrl+C to stop):"
    tail -f "$SCRIPT_DIR/logs/"*.log 2>/dev/null | grep -v "==> .*/bot.log <=="
}

case "$1" in
    start)
        start_bot
        ;;
    stop)
        stop_bot
        ;;
    restart)
        restart_bot
        ;;
    status)
        status_bot
        ;;
    logs)
        logs_bot
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|logs}"
        exit 1
        ;;
esac
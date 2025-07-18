#!/bin/bash

# Monitor script to check system health and restart if needed

# Check memory usage
MEM_USAGE=$(free | grep Mem | awk '{print ($3/$2) * 100.0}')
MEM_THRESHOLD=85

# Check if memory usage is above threshold
if (( $(echo "$MEM_USAGE > $MEM_THRESHOLD" | bc -l) )); then
    echo "$(date): High memory usage detected: $MEM_USAGE%"
    
    # Log top memory consumers
    echo "Top memory consumers:"
    ps aux --sort=-%mem | head -5
    
    # Restart MySQL if it's using too much memory
    MYSQL_MEM=$(ps aux | grep mysql | grep -v grep | awk '{print $4}' | head -1)
    if (( $(echo "${MYSQL_MEM:-0} > 40" | bc -l) )); then
        echo "Restarting MySQL due to high memory usage"
        sudo systemctl restart mysql
    fi
fi

# Check for stuck processes (running > 30 minutes)
ps -eo pid,etimes,cmd | grep -E "collect_prices|collect_funding" | while read pid time cmd; do
    if [ "$time" -gt 1800 ]; then
        echo "$(date): Killing stuck process $pid: $cmd (running for $time seconds)"
        kill -9 $pid
    fi
done

# Log current status
echo "$(date): Memory: $MEM_USAGE%, Load: $(uptime | awk -F'load average:' '{print $2}')"
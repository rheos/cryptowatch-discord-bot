#!/bin/bash
# Monitor CPU credits and usage

# Check CPU credit balance (if available via AWS CLI)
if command -v aws &> /dev/null; then
    CREDITS=$(aws lightsail get-instance-metric-data \
        --instance-name mysql-singapore \
        --metric-name CPUCreditBalance \
        --period 300 \
        --start-time $(date -u -d '5 minutes ago' +%Y-%m-%dT%H:%M:%S) \
        --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
        --unit Count \
        --statistics Average \
        --query 'metricData[0].average' \
        --output text 2>/dev/null)
    
    if [ ! -z "$CREDITS" ]; then
        echo "$(date): CPU Credits: $CREDITS"
        
        # Alert if credits are low
        if (( $(echo "$CREDITS < 20" | bc -l) )); then
            echo "WARNING: Low CPU credits!"
            # Could send alert email/notification here
        fi
    fi
fi

# Log current CPU usage
CPU_USAGE=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1)
echo "$(date): CPU Usage: $CPU_USAGE%"

# Check for high CPU processes
echo "Top CPU consumers:"
ps aux --sort=-%cpu | head -5
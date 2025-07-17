#!/bin/bash

# Switch between test and production configurations

if [ "$1" == "test" ]; then
    echo "Switching to TEST environment..."
    cp config.test.json config.json
    echo "Now using test configuration"
    echo "Remember to update channel IDs in config.test.json!"
elif [ "$1" == "prod" ]; then
    echo "Switching to PRODUCTION environment..."
    cp config.prod.json config.json
    echo "Now using production configuration"
    echo "⚠️  CAUTION: This is PRODUCTION!"
else
    echo "Usage: ./switch-env.sh [test|prod]"
    echo "Current config:"
    if grep -q "1394725769883812091" config.json 2>/dev/null; then
        echo "  → PRODUCTION"
    else
        echo "  → TEST"
    fi
fi
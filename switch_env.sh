#!/bin/bash

# Script to switch between development and production configs

if [ "$1" = "dev" ] || [ "$1" = "development" ]; then
    echo "Switching to DEVELOPMENT environment..."
    cp config.development.json config.json
    echo "✅ Now using config.development.json"
    echo "Remember to update bot token if needed!"
elif [ "$1" = "prod" ] || [ "$1" = "production" ]; then
    echo "Switching to PRODUCTION environment..."
    cp config.production.json config.json
    echo "✅ Now using config.production.json"
    echo "⚠️  WARNING: This is PRODUCTION! Be careful!"
    echo "Remember to update bot token if needed!"
else
    echo "Usage: ./switch_env.sh [dev|prod]"
    echo "  dev  - Switch to development config"
    echo "  prod - Switch to production config"
    exit 1
fi

# Show current config info
echo ""
echo "Current configuration:"
grep "server_name" config.json
echo ""
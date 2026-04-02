#!/bin/bash

# Script to switch between development and production configs

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ "$1" = "dev" ] || [ "$1" = "development" ]; then
    echo "Switching to DEVELOPMENT environment..."

    # Create/update .env file
    cat > "$SCRIPT_DIR/.env" << EOF
# Development environment
export BOT_ENV=development
export CONFIG_FILE=config.development.json
export MYSQL_HOST=localhost
export MYSQL_PORT=3306
export MYSQL_DATABASE=cryptowatch_bot
export MYSQL_USER=cwt_user
export MYSQL_PASSWORD=your_dev_password_here
export API_BASE_URL=http://localhost:3000/api
EOF

    echo "Environment set to DEVELOPMENT"
    echo "Run: source .env"
    echo "Then: ./bot_manager.sh start"

elif [ "$1" = "prod" ] || [ "$1" = "production" ]; then
    echo "Switching to PRODUCTION environment..."

    # Create/update .env file
    cat > "$SCRIPT_DIR/.env" << 'EOF'
# Production environment
export BOT_ENV=production
export CONFIG_FILE=config.production.json
export MYSQL_HOST=localhost
export MYSQL_PORT=3306
export MYSQL_DATABASE=cryptowatch_bot
export MYSQL_USER=cwt_user
export MYSQL_PASSWORD='your_prod_password_here'
export API_BASE_URL=https://example.com/api
EOF

    echo "Environment set to PRODUCTION"
    echo "WARNING: This is PRODUCTION! Be careful!"
    echo "Run: source .env"
    echo "Then: ./bot_manager.sh start"

else
    echo "Usage: ./switch_env.sh [dev|prod]"
    echo "  dev  - Switch to development config"
    echo "  prod - Switch to production config"
    echo ""
    echo "Current environment:"
    if [ -f "$SCRIPT_DIR/.env" ]; then
        grep "CONFIG_FILE" "$SCRIPT_DIR/.env" 2>/dev/null || echo "No CONFIG_FILE set"
    else
        echo "No .env file found"
    fi
    exit 1
fi

# Show which config will be used
echo ""
echo "Will use: $CONFIG_FILE"
if [ -f "$SCRIPT_DIR/$CONFIG_FILE" ]; then
    echo "Server: $(grep "server_name" "$SCRIPT_DIR/$CONFIG_FILE" | cut -d'"' -f4)"
else
    echo "Warning: $CONFIG_FILE not found!"
fi

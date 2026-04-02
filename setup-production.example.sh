#!/bin/bash
# Production setup script for Discord bot (without Docker)

echo "Setting up Discord bot for production..."

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run migrations
echo "Running database migrations..."
CONFIG_FILE=config.production.json python migrate.py migrate

# Create systemd service file
cat > discord-bot.service << EOF
[Unit]
Description=CryptoWatch Discord Bot
After=network.target mysql.service

[Service]
Type=simple
User=$(whoami)
WorkingDirectory=$(pwd)
Environment="CONFIG_FILE=config.production.json"
Environment="MYSQL_HOST=localhost"
Environment="MYSQL_PORT=3306"
Environment="MYSQL_DATABASE=cryptowatch_bot"
Environment="MYSQL_USER=cwt_user"
Environment="MYSQL_PASSWORD=your_mysql_password_here"
Environment="DEFAULT_GUILD_ID=YOUR_PRODUCTION_GUILD_ID"
ExecStart=$(pwd)/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

echo "Systemd service file created: discord-bot.service"
echo ""
echo "To install as a service:"
echo "1. Edit discord-bot.service and set DEFAULT_GUILD_ID"
echo "2. sudo cp discord-bot.service /etc/systemd/system/"
echo "3. sudo systemctl daemon-reload"
echo "4. sudo systemctl enable discord-bot"
echo "5. sudo systemctl start discord-bot"
echo ""
echo "To run manually:"
echo "source venv/bin/activate"
echo "CONFIG_FILE=config.production.json python main.py"

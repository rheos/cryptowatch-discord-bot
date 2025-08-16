# CryptoWatch Discord Bot

A comprehensive Discord bot for crypto trading communities that provides timezone displays, market event tracking, funding rate alerts, volatility tracking, and community engagement management.

## IMPORTANT: Environment Notes
- **Development**: Uses Docker containers (docker-compose)
- **Production**: Runs directly on AWS EC2 instance (NO Docker)
- **Database**: MySQL (`cryptowatch_bot` database)
  - Dev: Runs in Docker container
  - Prod: AWS EC2 instance

## Features

### 🕐 Timezone Display
- Updates channel names every 5 minutes with current time
- Supports multiple timezones (Vancouver, Halifax, Brisbane, Istanbul, Kolkata)
- Displays time in format: "City H:MM AM/PM"
- Respects Discord's rate limits (2 updates per 10 minutes per channel)

### 📈 Market Events & Tracking
- Shows countdown to major market events:
  - London Open (7:00 AM UTC)
  - US Open (1:30 PM UTC)
  - NYSE Close (8:00 PM UTC)
  - Asia Open (12:00 AM UTC)
  - Daily Close (12:00 AM UTC)
- Skips stock market events on weekends
- Updates pinned message with all market times and countdowns

### 💰 Crypto Data Commands (Slash Commands)
- `/price <symbol>` - Get current price of a cryptocurrency
- `/funding <mode>` - Check funding rates:
  - Most Negative - Extreme negative funding rates
  - Scanner - Overview of all funding categories
  - Improving - Rates becoming less negative
  - Worsening - Rates becoming more negative
  - Recently Turned Positive - Flipped from negative to positive
  - Check Specific Symbol - Check a specific coin's funding
- `/volatility <mode>` - Track market volatility:
  - Scanner - Overview across all timeframes
  - Most Volatile - Top movers for specific timeframe
  - Check Specific Symbol - Check volatility for a specific coin
- `/watchlist <exchange>` - Export TradingView watchlist for supported exchanges

### 🔄 Auto Updates
- Automatically updates designated channels with:
  - Funding rate summaries (every 30 minutes)
  - Volatility alerts (when thresholds exceeded)
  - Market notifications
- Message editing for persistent updates (funding summary, market events)
- Auto-cleanup of old messages (older than 4 hours)

### 📊 Volatility Scanner
- Monitors price movements across multiple timeframes
- Configurable thresholds for each timeframe
- Automatic alerts for significant moves
- Support for 5m, 15m, 1h, 4h, 24h, 48h timeframes

### 👥 Engagement System
- **Role Progression**:
  - `@NewMember` - New joins (limited to welcome channels)
  - `@Member` - Has posted introduction (access to general channels)
  - `@Active` - Regular participants (access to premium channels)
  - `@Vacation` - Temporary status to preserve Active role

- **Admin Commands** (Slash):
  - `/admin action:analyze` - View member activity statistics
  - `/admin action:backfill` - Backfill engagement data
  - `/admin action:settings` - View current settings

- **User Commands** (Slash):
  - `/mystats` - Check your own engagement statistics
  - `/help` - Get help information

### 🤖 AI Assistant
- `/luna <question>` - Chat with Luna, the crypto-specialized AI assistant
- Powered by GPT-3.5-turbo with crypto market knowledge
- Context-aware responses about trading and market analysis

### ⚙️ Setup & Configuration
- `/setup` - Initial bot configuration (admin only)
- Database-driven settings (no more config file editing)
- Per-guild configuration stored in MySQL

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

Required packages:
- discord.py>=2.3.0
- pytz
- aiohttp
- aiomysql
- python-dateutil
- openai

### 2. Discord Bot Setup

1. Go to https://discord.com/developers/applications
2. Create a new application
3. Go to Bot section and create a bot
4. Enable these Privileged Gateway Intents:
   - Server Members Intent (for engagement tracking)
   - Message Content Intent (for legacy commands)
   - Presence Intent (for member tracking)
5. Copy the bot token

### 3. Database Setup

The bot uses MySQL database with automatic migrations:

```bash
# Run migrations
python run_migrations.py
```

Database schema is managed through migration files in `migrations/` directory.

### 4. Configuration

Configuration is now stored in the database, not JSON files. Initial setup:

1. Set environment variables:
```bash
export DISCORD_TOKEN="your_bot_token"
export MYSQL_HOST="mysql"  # or "localhost" for production
export MYSQL_USER="cwt_user"
export MYSQL_PASSWORD="your_password"
export MYSQL_DATABASE="cryptowatch_bot"
```

2. Run the bot and use `/setup` command to configure settings

### 5. Discord Server Setup

1. **Create Required Roles**:
   - NewMember
   - Member
   - Active
   - Vacation

2. **Create Required Channels**:
   - #welcome (read-only rules)
   - #welcome-chat (for introductions)
   - Timezone display channels (voice channels)
   - Market event channel (voice channel for countdown)
   - Market schedule channel (text channel for pinned message)
   - Funding alerts channel
   - Volatility alerts channel

3. **Set Permissions**:
   - NewMember: Can only see welcome channels
   - Member: Can see all general channels
   - Active: Can see premium channels
   - Bot role: Should be at or near the top of role hierarchy

### 6. Bot Permissions

When inviting the bot, ensure it has:
- Manage Channels (for timezone updates)
- Manage Roles (for engagement system)
- Send Messages
- Manage Messages (for pinning)
- Read Message History
- Add Reactions
- View Channels
- Use Slash Commands

### 7. Running the Bot

#### Development (Docker)
```bash
cd ../cryptowatchtools
docker-compose up discord-bot
```

#### Production (Direct)
```bash
./switch_env.sh production
python main.py

# Or using bot manager
./bot_manager.sh start
./bot_manager.sh status
./bot_manager.sh stop
./bot_manager.sh restart
```

## Slash Commands Reference

### Public Commands
- `/price <symbol>` - Get cryptocurrency price
- `/funding <mode> [limit] [symbol]` - Analyze funding rates
- `/volatility <mode> [timeframe] [limit] [symbol]` - Track volatility
- `/watchlist <exchange>` - Get TradingView watchlist
- `/mystats` - Check your engagement statistics
- `/luna <question>` - Chat with AI assistant
- `/help` - Get help information

### Admin Commands
- `/setup` - Configure bot settings
- `/admin <action>` - Administrative functions
- `/market <action>` - Market event management
- `/timezone <action>` - Timezone channel management

## Logging

Logs are stored in the `logs/` directory:
- `timezone.log` - Timezone update logs
- `crypto.log` - Crypto data logs
- `crypto_commands.log` - Slash command logs
- `market-events.log` - Market event logs
- `auto-updates.log` - Auto update logs
- `engagement.log` - Engagement system logs
- `ai_chat.log` - AI assistant logs
- `slash_commands.log` - General slash command logs
- `errors.log` - Error-only log

## Database Migration

The bot uses a migration system for database updates:

```bash
# Check migration status
python run_migrations.py status

# Run pending migrations
python run_migrations.py

# Rollback last migration (if needed)
python run_migrations.py rollback
```

## Rate Limits & Best Practices

- Channel name updates: 2 per 10 minutes per channel
- Message editing: No hard limit, but be reasonable
- Slash commands: Follow Discord's rate limits
- API calls: Cached where possible to reduce load
- Bulk operations: Use sparingly to avoid rate limits

## Features Configuration

All features can be toggled via database settings:
- Timezone updates
- Market events
- Funding alerts
- Volatility scanner
- Engagement tracking
- AI assistant

Use `/admin action:settings` to view current configuration.

## Troubleshooting

1. **Bot not responding to commands**: 
   - Ensure slash commands are synced (happens on startup)
   - Check bot has Use Slash Commands permission

2. **Channel updates not working**: 
   - Verify bot has Manage Channels permission
   - Check rate limit hasn't been exceeded

3. **Engagement not working**: 
   - Ensure feature is enabled in database
   - Verify roles exist and bot can manage them
   - Bot role must be higher than roles it manages

4. **Database connection issues**:
   - Check MySQL is running
   - Verify credentials in environment
   - Ensure database exists

## Support

For issues or questions:
- Check logs in `logs/` directory
- Ensure all permissions are granted
- Verify database connectivity
- Check Discord's status page for API issues
- Review migration status with `run_migrations.py status`
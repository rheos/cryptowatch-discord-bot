# CryptoWatch Discord Bot

A comprehensive Discord bot for crypto trading communities that provides timezone displays, market event tracking, funding rate alerts, volatility tracking, and community engagement management.

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

### 💰 Crypto Data Integration
- `!negative` - Check extreme negative funding rates
- `!funding <symbol>` - Get funding rate history for a specific symbol
- `!watchlist <exchange>` - Get TradingView watchlist for an exchange
- Integrates with CryptoWatchTools API

### 🔄 Auto Updates
- Automatically updates designated channels with:
  - Latest funding rate alerts
  - Market notifications
- Configurable update intervals

### 📊 Volatility Tracking
- Monitors and reports market volatility
- Tracks significant price movements
- Provides volatility-based alerts

### 👥 Engagement System (NEW!)
- **Role Progression**:
  - `@NewMember` - New joins (limited to welcome channels)
  - `@Member` - Has posted introduction (access to general channels)
  - `@Active` - Regular participants (access to premium channels)
  - `@Vacation` - Temporary status to preserve Active role

- **Admin Commands**:
  - `!analyze_members` - View member activity statistics
  - `!grandfather_active days:X messages:Y` - Grant Active to qualifying members
  - `!check_user @user` - Check specific user's engagement stats
  - `!grant_active @user` - Manually grant Active role
  - `!grant_vacation @user days:X` - Grant vacation mode

- **User Commands**:
  - `!mystats` - Check your own engagement statistics
  - `!vacation` - Request vacation mode (Active members only)

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

Required packages:
- discord.py
- pytz
- aiohttp
- python-dateutil

### 2. Discord Bot Setup

1. Go to https://discord.com/developers/applications
2. Create a new application
3. Go to Bot section and create a bot
4. Enable these Privileged Gateway Intents:
   - Server Members Intent (for engagement tracking)
   - Message Content Intent (for commands)
   - Presence Intent (for member tracking)
5. Copy the bot token

### 3. Configuration

Create appropriate config file:
- Development: Copy config to `config.development.json`
- Production: Copy config to `config.production.json`

Then update `config.json` to point to the correct environment.

#### Config Structure:
```json
{
  "bot_token": "YOUR_BOT_TOKEN",
  "server_name": "SERVER_NAME",
  "timezone_channels": [
    {
      "timezone": "America/Vancouver",
      "channel_id": CHANNEL_ID
    }
  ],
  "market_event_channel_id": CHANNEL_ID,
  "market_times_message_channel_id": CHANNEL_ID,
  "auto_update_channels": {
    "funding": CHANNEL_ID,
    "alerts": CHANNEL_ID
  },
  "api_base_url": "https://example.com/api",
  "engagement": {
    "enabled": true,
    "roles": {
      "new_member": "NewMember",
      "member": "Member",
      "active": "Active",
      "vacation": "Vacation"
    },
    "thresholds": {
      "active_messages": 10,
      "active_days": 30
    },
    "channels": {
      "welcome_chat": "welcome-chat"
    }
  }
}
```

### 4. Discord Server Setup

1. **Create Required Roles**:
   - NewMember
   - Member
   - Active
   - Vacation

2. **Create Required Channels**:
   - #welcome (read-only rules)
   - #welcome-chat (for introductions)
   - Timezone display channels
   - Market event channel
   - Auto-update channels

3. **Set Permissions**:
   - NewMember: Can only see welcome channels
   - Member: Can see all general channels
   - Active: Can see premium channels

### 5. Bot Permissions

When inviting the bot, ensure it has:
- Manage Channels (for timezone updates)
- Manage Roles (for engagement system)
- Send Messages
- Read Message History
- Add Reactions
- View Channels

### 6. Running the Bot

```bash
# Development
./switch_env.sh development
python main.py

# Production
./switch_env.sh production
python main.py

# Using bot manager
./bot_manager.sh start
./bot_manager.sh status
./bot_manager.sh stop
./bot_manager.sh restart
```

## Environment Management

Use `switch_env.sh` to switch between development and production:
```bash
./switch_env.sh development  # Uses config.development.json
./switch_env.sh production   # Uses config.production.json
```

## Logging

Logs are stored in the `logs/` directory:
- `bot.log` - Main bot log
- `timezone.log` - Timezone update logs
- `crypto.log` - Crypto data logs
- `market-events.log` - Market event logs
- `auto-updates.log` - Auto update logs
- `engagement.log` - Engagement system logs
- `errors.log` - Error-only log

## Engagement System Implementation

### Phase 1: Setup (Day 1)
- Deploy bot with engagement disabled
- Create roles but don't assign
- Test commands with admin role

### Phase 2: Analysis (Day 2-3)
- Run `!analyze_members` to understand current state
- Determine grandfather settings

### Phase 3: Grandfather (Day 4-7)
- Announce new system
- Run `!grandfather_active days:30 messages:10`
- Give members time to understand changes

### Phase 4: Enable (Day 8+)
- Set `engagement.enabled` to `true`
- New members start in welcome flow
- Monitor and adjust as needed

## Rate Limits & Best Practices

- Channel name updates: 2 per 10 minutes per channel
- Message history scanning: Be conservative to avoid API limits
- Bulk operations: Use sparingly to avoid rate limits
- Member role updates: Batch when possible

## Troubleshooting

1. **Bot not updating channels**: Check bot has Manage Channels permission
2. **Engagement not working**: Ensure engagement.enabled is true and roles exist
3. **Commands not responding**: Check Message Content Intent is enabled
4. **Missing members in analysis**: Bot needs Read Message History permission

## Support

For issues or questions:
- Check logs in `logs/` directory
- Ensure all permissions are granted
- Verify configuration is correct
- Check Discord's status page for API issues
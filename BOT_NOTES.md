# Discord Bot Technical Notes

## Overview
CryptoWatch Discord Bot - A multi-functional bot that combines timezone displays, market event tracking, and crypto funding rate monitoring.

## Architecture

### Main Components
- **main.py**: Entry point that loads all cogs and manages the bot lifecycle
- **bot_manager.sh**: Shell script for starting/stopping/managing the bot as a background process
- **Cogs**: Modular components that handle different functionalities

### Active Cogs

#### 1. TimezoneCog (`cogs/timezone_cog.py`)
- **Purpose**: Updates Discord channel names to show current time in different timezones
- **Behavior**: 
  - Rounds time DOWN to last 5-minute interval (e.g., 10:19 → 10:15)
  - Updates every 5 minutes to respect Discord's rate limit (2 channel updates per 10 minutes)
  - Configured timezones: Vancouver, Halifax (shown as PEI), Brisbane, Istanbul, India (Kolkata)
  - Smart updates: Only updates channels if the time has actually changed
- **Key Design Decision**: Shows 5-minute intervals instead of exact time to avoid rate limiting
- **Rate Limit Protection**: Checks current channel names before updating to avoid unnecessary API calls

#### 2. MarketEventsCog (`cogs/market_events_cog.py`)
- **Purpose**: Tracks and displays market open/close times
- **Features**:
  - Updates a channel name with countdown to next market event
  - Maintains a pinned message with full market schedule
  - Handles weekends intelligently (only shows crypto-relevant events on weekends)
  - Times are rounded to 5-minute intervals to stay in sync with timezone channels
- **Market Events**: London Open, NY Open, NY Close, Asia Open, Daily Close
- **Weekend Logic**: Filters out traditional market events, keeps 24/7 crypto events
- **Time Rounding**: All times rounded down to last 5-minute interval for consistency

#### 3. CryptoDataCog (`cogs/crypto_data_cog.py`)
- **Purpose**: Provides crypto funding rate commands
- **API Integration**: Connects to https://cryptowatchtools.com/api
- **Commands**:
  - `!negative` (aliases: `!n`, `!neg`) - Most negative funding rates
  - `!turned` (aliases: `!t`) - Coins that turned positive
  - `!improving` (aliases: `!i`) - Negative but improving rates
  - `!worsening` (aliases: `!w`) - Getting more negative
  - `!scanner` (aliases: `!scan`) - Comprehensive overview
  - `!help` (aliases: `!h`, `!commands`) - Custom help menu
  - `!purge` (aliases: `!clear`) - Admin-only bulk message deletion
- **Data Source**: BloFin exchange funding rates via the web app API
- **Custom Help**: Replaced default Discord.py help with formatted embed

#### 4. AutoUpdatesCog (`cogs/auto_updates_cog.py`)
- **Purpose**: Posts scheduled updates to designated channels
- **Features**:
  - Funding summary every 4 hours
  - Extreme rate alerts every 30 minutes
  - Only active if channels are configured

#### 5. AutoRoleCog (`cogs/auto_role_cog.py`)
- **Purpose**: Automatically assigns roles to new members
- **Features**:
  - Assigns "Members" role to new users on join
  - Configurable role name (default: "Members")
  - Logs role assignment success/failure
- **Requirements**: Bot needs "Manage Roles" permission and must be above the target role

## Configuration

### config.json Structure
```json
{
  "bot_token": "Discord bot token",
  "timezone_channels": [
    {"timezone": "America/Vancouver", "channel_id": 123},
    {"timezone": "America/Halifax", "channel_id": 456},
    {"timezone": "Australia/Brisbane", "channel_id": 789},
    {"timezone": "Europe/Istanbul", "channel_id": 012},
    {"timezone": "Asia/Kolkata", "channel_id": 1395827299424800788}
  ],
  "market_event_channel_id": 345,
  "market_times_message_channel_id": 678,
  "auto_update_channels": {
    "funding": null,
    "alerts": null
  }
}
```

## Logging
- Main log: `logs/bot.log` with rotation (10MB max, 5 backups)
- Separate cog logs: 
  - `logs/timezone.log` - Timezone update events
  - `logs/market-events.log` - Market event updates
  - `logs/crypto.log` - Crypto command usage
  - `logs/auto-updates.log` - Scheduled update posts
  - `logs/auto-role.log` - Role assignment events
- Both file and console logging enabled
- Note: Console output duplicates in logs when using bot_manager.sh

## Management
- Start: `./bot_manager.sh start`
- Stop: `./bot_manager.sh stop`
- Status: `./bot_manager.sh status`
- Logs: `./bot_manager.sh logs`
- Restart: `./bot_manager.sh restart`

## Important Behaviors

### Timezone Updates
- Shows LAST 5-minute interval, not current exact time
- This is intentional to avoid Discord rate limits
- Updates happen at :00, :05, :10, :15, :20, etc.
- Smart updates: Checks current channel name before updating to avoid rate limits
- India timezone shows as "India" not "Kolkata" for clarity

### Market Events
- Automatically adjusts for weekends
- Shows "Opening Now" or "Closing Now" when within 5 minutes of event
- Calculates next event considering weekends for traditional markets
- Times are rounded to 5-minute intervals to match timezone channels

### Discord Connection
- Bot name: HAL#0193
- Requires message content intent for crypto commands
- Handles reconnection automatically
- Rate limit aware: Implements smart channel name checking

### Command System
- Custom help command with formatted embeds
- Admin-only purge command for channel cleanup
- Commands match web app terminology (e.g., !negative not !funding)

## Common Issues

### Bot Stops Unexpectedly
- Check logs for errors
- Verify Discord token is valid
- Ensure all channel IDs in config exist

### Time Shows Wrong
- Remember: it shows the LAST 5-minute interval
- This is by design, not a bug

### Duplicate Log Entries
- Normal when using bot_manager.sh
- Console output is redirected to same log file

## Data Flow
1. Bot starts and loads all cogs
2. Each cog starts its own update loops
3. Timezone/market cogs update Discord channel names
4. Crypto cog responds to user commands
5. Auto-updates post to channels if configured

## Integration with CryptoWatchTools
- API endpoint: https://cryptowatchtools.com/api
- Endpoints used:
  - /most-negative
  - /turned-positive
  - /improving-negative
  - /worsening-negative
  - /funding-scanner-data
- Data updates every 30 minutes on the web app side

## Future Considerations
- Price tracking commands pending (waiting for volatility scanner)
- May need to adjust rate limits if adding more timezone channels
- Consider adding error recovery for API failures
- Add customizable auto-role configuration per server
- Consider caching API responses to reduce web app load
- Add command cooldowns to prevent spam
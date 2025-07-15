# CryptoWatch Discord Bot

A Discord bot that updates channel names to display current time in different timezones and countdown to market events.

## Features

- Updates channel names every 5 minutes with current time
- Supports multiple timezones
- Displays time in format: "City H:MM AM/PM"
- Shows countdown to next major market event (London Open, US Open, etc.)
- Auto-assigns roles to new members
- Updates a pinned message with all market times in major timezones

## Setup

1. Install dependencies:
```bash
pip install discord.py pytz
```

2. Create a Discord application and bot:
   - Go to https://discord.com/developers/applications
   - Create a new application
   - Go to Bot section and create a bot
   - Copy the bot token

3. Configure the bot:
   - Copy `config.example.json` to `config.json`
   - Add your bot token
   - Update channel IDs with your Discord channel IDs

4. Invite bot to your server:
   - Use OAuth2 URL Generator with `bot` scope
   - Select "Manage Channels" permission
   - Use the generated URL to invite the bot

5. (Optional) Set up pinned market times message:
```bash
python setup-market-times.py
# Follow prompts to create message
# Add the IDs to config.json
```

6. Run the bot:
```bash
python crypto-watch-bot.py
```

## Configuration

The `config.json` file contains:
- `bot_token`: Your Discord bot token
- `market_event_channel_id`: Channel ID for market event countdown (optional)
- `market_times_message_channel_id`: Channel containing pinned times message (optional)
- `market_times_message_id`: Message ID to update with market times (optional)
- `channels`: Array of channels to update with timezone
  - `timezone`: Timezone string (e.g., "America/Vancouver")
  - `channel_id`: Discord channel ID

## Market Events

The bot tracks these market events (all times UTC):
- London Open: 7:00 AM
- US Open: 1:30 PM
- NYSE Close: 8:00 PM
- Asia Open: 12:00 AM
- Daily Close: 12:00 AM

Stock market events are skipped on weekends.

## Rate Limits

Discord limits channel name updates to 2 per 10 minutes per channel, so the bot updates every 5 minutes to stay within limits.
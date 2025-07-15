# CryptoWatch Discord Bot

A Discord bot that updates channel names to display current time in different timezones.

## Features

- Updates channel names every 5 minutes with current time
- Supports multiple timezones
- Displays time in format: "🕒 City H:MM AM/PM"

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

5. Run the bot:
```bash
python crypto-watch-bot
```

## Configuration

The `config.json` file contains:
- `bot_token`: Your Discord bot token
- `channels`: Array of channels to update
  - `timezone`: Timezone string (e.g., "America/Vancouver")
  - `channel_id`: Discord channel ID

## Rate Limits

Discord limits channel name updates to 2 per 10 minutes per channel, so the bot updates every 5 minutes to stay within limits.
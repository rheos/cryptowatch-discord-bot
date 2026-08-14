# CryptoWatch Discord Bot

A production Discord bot for crypto communities. It keeps market times, funding and volatility alerts, TradingView signals, and member-role workflows inside Discord.

The bot was built for the wider CryptoWatchTools stack. It depends on a companion market-data API and MySQL schema, so this repository is an engineering reference rather than a standalone public bot service.

![CryptoWatch Discord Bot](timebot.png)

## Capabilities

- Timezone channels that stay current without exceeding Discord's channel-update limits
- Market-session countdowns and a persistent schedule message
- Slash commands for prices, funding rates, and volatility across several timeframes
- Funding, volatility, and TradingView alerts routed to configured channels
- Role progression and activity tracking for community operations
- Mention-based assistant requests delegated to the companion API
- MySQL migrations, database-backed guild settings, and rotating per-feature logs

## Architecture

The Python process is organized as Discord cogs around a shared bot and database connection. Discord handles commands and community events; the companion API supplies market data and assistant responses; MySQL stores guild configuration, engagement state, and migration history.

```text
Discord server
    |
    v
discord.py bot ----> CryptoWatchTools market-data API
    |
    v
MySQL
```

This separation keeps Discord-specific concerns in the bot while market-data collection and analysis remain in the companion service.

## Repository map

| Path | Purpose |
| --- | --- |
| `main.py` | Bot lifecycle, cog loading, command sync, and Discord events |
| `cogs/` | Timezones, market display, crypto data, alerts, engagement, and assistant behavior |
| `database.py` | MySQL connection and persistence helpers |
| `migrations/` | Ordered database schema changes |
| `run_migrations.py` | Migration status, apply, and rollback commands |
| `config.example.json` | Public-safe example of bot and guild configuration |
| `bot_manager.sh` | Direct-process operations for the original deployment model |

## Operator notes

The public repository is not a complete deployment. To run it, an operator needs:

- Python 3 and the packages in `requirements.txt`
- A Discord application with member, message-content, and presence intents
- A MySQL database initialized with `python run_migrations.py`
- A private config file based on `config.example.json`, including `bot_token`
- A compatible CryptoWatchTools API at the configured `api_base_url`
- Discord roles, channels, and permissions that match the guild configuration

The example environment switcher is `switch_env.example.sh`; copy and review it before use. Production secrets and the companion CryptoWatchTools repository are intentionally not included here.

## Operational boundaries

The original deployment ran directly on an AWS EC2 host, while development used the larger CryptoWatchTools Docker environment. The Docker command from that environment is not reproducible from this repository alone.

The assistant cog delegates requests to the configured companion API. This repository does not select or call a language model directly.

## License

This repository does not currently include an open-source license. Public visibility does not grant permission to copy, redistribute, or reuse its code or documentation.

Built by [Novadiem Studio](https://novadiem.com) for the CryptoWatchTools system.

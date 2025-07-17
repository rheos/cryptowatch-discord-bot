# Proposed Bot Structure

```
discord-bot/
├── main.py                    # Main bot entry point
├── config.json               # Configuration file
├── requirements.txt          # Python dependencies
├── .gitignore               
├── README.md
│
├── cogs/                     # Discord cogs (modular commands)
│   ├── __init__.py
│   ├── timezone_cog.py       # Timezone channel updates
│   ├── market_events_cog.py  # Market event countdown
│   └── crypto_data_cog.py    # Funding rates & API data
│
├── utils/                    # Shared utilities
│   ├── __init__.py
│   ├── time_utils.py         # Time/timezone helpers
│   ├── market_utils.py       # Market event calculations
│   └── api_client.py         # API client for CryptoWatchTools
│
├── services/                 # Background services
│   ├── __init__.py
│   └── update_scheduler.py   # Manages all scheduled updates
│
└── data/                     # Runtime data files
    ├── bot.pid
    └── market_message.id
```

## Benefits:
1. **Separation of concerns** - Each feature in its own module
2. **Easy to maintain** - Find and fix issues quickly
3. **Scalable** - Add new features without cluttering
4. **Testable** - Can test individual components
5. **Team friendly** - Multiple people can work on different parts
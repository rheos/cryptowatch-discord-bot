# Migration Guide: From Monolithic to Modular Bot

## What's New

The bot has been refactored from a single file (`crypto-watch-bot.py`) into a modular structure:

```
OLD: crypto-watch-bot.py (one big file)
NEW: main.py + cogs/ (modular components)
```

## Benefits
- ✅ Each feature is now independent
- ✅ Easy to add new features
- ✅ Better error handling
- ✅ Can reload parts without restarting
- ✅ Includes crypto data commands

## Migration Steps

1. **Stop the old bot**:
   ```bash
   ./stop-bot.sh
   ```

2. **Update config.json** to include new features:
   ```json
   {
     "auto_update_channels": {
       "funding": null,  // Set channel ID for auto updates
       "alerts": null    // Set channel ID for alerts
     }
   }
   ```

3. **Install new dependencies**:
   ```bash
   pip3 install aiohttp
   ```

4. **Start the new bot**:
   ```bash
   ./start-bot-new.sh
   ```

## New Commands Available

### Crypto Commands
- `!funding [limit]` - Show most negative funding rates
- `!turned [limit]` - Show coins that turned positive  
- `!improving [limit]` - Show improving negative rates
- `!cryptohelp` - Show crypto command help

### Aliases
- `!f` = `!funding`
- `!t` = `!turned`
- `!i` = `!improving`

## Testing the Migration

1. Check timezone updates still work
2. Check market event countdown still works
3. Test new crypto commands: `!funding`
4. Check logs: `tail -f bot.log`

## Rollback Plan

If you need to go back to the old bot:
```bash
./stop-bot.sh
nohup python3 crypto-watch-bot.py > /dev/null 2>&1 &
```

## Configuration for Auto Updates

To enable automatic funding updates, edit `config.json`:

```json
"auto_update_channels": {
  "funding": 1234567890,  // Your channel ID
  "alerts": 9876543210    // Your alerts channel ID
}
```

The bot will then:
- Post funding summaries every 4 hours to the funding channel
- Post extreme alerts (< -0.2%) to the alerts channel
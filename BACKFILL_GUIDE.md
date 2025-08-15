# Engagement Data Backfill Guide

## Overview
The engagement backfill functionality allows you to populate historical member activity data from Discord message history. This prevents guilds from starting at zero when engagement tracking is first enabled.

## Methods Available

### 1. Discord Slash Commands (Recommended for Production)
Quick and easy backfill directly from Discord:

#### `/backfill_engagement`
- **Parameters:**
  - `days` (optional): Number of days to scan (default: 30, max: 90)
  - `channel` (optional): Specific channel to scan, or all channels if not specified
- **Usage Example:** `/backfill_engagement days:30`
- **Features:**
  - Real-time progress updates
  - Shows top 10 most active members
  - Handles rate limits automatically
  - Safe to run multiple times (adds to existing data)

#### `/backfill_status`
- Check current engagement data coverage
- Shows earliest/latest dates, total messages, and active members
- Useful to verify backfill completion

### 2. Python Script (For Advanced Users)
Full-featured script with resume capability:

```bash
# Run from discord-bot directory
cd /home/user/Documents/foaftech/webdev/crypto-site/discord-bot

# Basic usage (scans all guilds with engagement enabled)
python3 scripts/backfill_engagement.py

# Scan specific guild
python3 scripts/backfill_engagement.py --guild 1000000000000000000

# Custom history period
python3 scripts/backfill_engagement.py --days 60

# Reset and start fresh
python3 scripts/backfill_engagement.py --reset
```

**Features:**
- Resumable if interrupted (saves progress)
- Detailed logging to `backfill_engagement.log`
- Scans up to 50 channels per guild
- Handles large servers efficiently

## Production Deployment Steps

1. **Enable Engagement Tracking**
   ```
   /setup action:"Toggle Engagement Tracking"
   ```

2. **Run Initial Backfill**
   ```
   /backfill_engagement days:30
   ```

3. **Verify Data**
   ```
   /backfill_status
   ```

4. **Test Member Analysis**
   ```
   /admin action:"Analyze Member Activity"
   ```

## Important Notes

- **Rate Limits**: Discord has rate limits on message history access. The backfill respects these limits automatically.
- **Performance**: Scanning 30 days of a medium-sized server (~20 active channels) takes about 2-5 minutes.
- **Data Storage**: Activity is stored daily per member. Running backfill multiple times adds to existing counts.
- **Privacy**: Only message counts are stored, not message content.
- **Permissions**: Bot needs read message history permission in channels to scan.

## Troubleshooting

### "No engagement data found"
- Ensure engagement tracking is enabled first
- Check bot has read permissions in channels
- Verify members have sent messages in the time period

### Backfill seems slow
- Normal for servers with lots of history
- Consider scanning fewer days initially
- Use specific channel parameter for testing

### Missing activity for some members
- Bot can only see messages in channels it has access to
- Private threads and voice channels are not scanned
- Deleted messages are not included

## Database Impact

The backfill populates the `member_activity_daily` table:
- One row per member per day with activity
- Typical storage: ~1KB per active member per month
- Indexes on guild_id, user_id, and activity_date for fast queries
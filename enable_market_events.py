#!/usr/bin/env python3
"""
Enable market events for the guild
"""
import asyncio
import os
from database import BotDatabase

async def enable_market_events():
    """Enable market events and migrate existing configuration"""
    db_config = {
        'database': {
            'host': os.environ.get('MYSQL_HOST', 'mysql'),
            'port': 3306,
            'user': 'cwt_user',
            'password': 'example_password',
            'name': 'cryptowatch_bot'
        }
    }
    
    db = BotDatabase(db_config)
    await db.connect()
    
    try:
        guild_id = 1000000000000000000
        
        # Enable market events
        await db.set_setting(guild_id, 'market_events.enabled', True)
        print("✓ Enabled market events")
        
        # Check current status
        enabled = await db.get_setting(guild_id, 'market_events.enabled')
        print(f"Market events enabled: {enabled}")
        
        # Check if channels are configured
        channels = await db.get_guild_channels(guild_id)
        has_market_events = False
        has_market_times = False
        
        for channel in channels:
            if channel['channel_type'] == 'market_events':
                has_market_events = True
                print(f"✓ Market events channel: {channel['channel_id']}")
            elif channel['channel_type'] == 'market_times':
                has_market_times = True
                print(f"✓ Market times channel: {channel['channel_id']}")
        
        if not has_market_events or not has_market_times:
            print("\n⚠️  Missing channels! Use /setup_market_channels to configure them.")
        else:
            print("\n✅ All channels configured! Market events should start updating within 5 minutes.")
            
    finally:
        await db.close()

if __name__ == "__main__":
    asyncio.run(enable_market_events())
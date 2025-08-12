#!/usr/bin/env python3
"""
Check if guild and settings were properly migrated
"""
import asyncio
import os
from database import BotDatabase
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def check_migration():
    """Check migration status"""
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
        
        logger.info("=== Checking Migration Status ===\n")
        
        # Check if guild exists
        async with db.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("SELECT * FROM guilds WHERE guild_id = %s", (guild_id,))
                guild = await cursor.fetchone()
                
                if guild:
                    logger.info(f"✓ Guild found in database: {guild}")
                else:
                    logger.error("✗ Guild NOT found in database")
                    return
        
        # Check settings
        logger.info("\n=== Checking Settings ===")
        settings = await db.get_all_settings(guild_id)
        
        if settings:
            logger.info(f"Found {len(settings)} settings:")
            for key, data in settings.items():
                logger.info(f"  {key}: {data['value']}")
        else:
            logger.error("No settings found!")
        
        # Check channels
        logger.info("\n=== Checking Channels ===")
        channels = await db.get_guild_channels(guild_id)
        
        if channels:
            logger.info(f"Found {len(channels)} channels:")
            for channel in channels:
                logger.info(f"  {channel['channel_type']} ({channel.get('channel_subtype', 'N/A')}): {channel['channel_id']}")
        else:
            logger.error("No channels found!")
        
        # Check engagement settings specifically
        logger.info("\n=== Checking Engagement Settings ===")
        eng_settings = await db.get_engagement_settings(guild_id)
        if eng_settings:
            logger.info(f"Engagement settings: {eng_settings}")
        else:
            logger.error("No engagement settings found!")
            
    finally:
        await db.close()

if __name__ == "__main__":
    asyncio.run(check_migration())
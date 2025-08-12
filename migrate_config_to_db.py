#!/usr/bin/env python3
"""
Migrate configuration from JSON files to new V2 database
"""
import asyncio
import json
import os
from database import BotDatabase
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def migrate_config():
    """Migrate config from JSON to database"""
    # Load config
    config_file = os.environ.get('CONFIG_FILE', 'config.json')
    with open(config_file, 'r') as f:
        config_data = json.load(f)
    
    # Database config
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
        # Guild ID from Discord bot logs
        guild_id = 1000000000000000000
        
        logger.info("=== Migrating Configuration to Database ===")
        
        # Migrate timezone channels
        if 'timezone_channels' in config_data:
            for tz_config in config_data['timezone_channels']:
                timezone = tz_config['timezone']
                channel_id = tz_config['channel_id']
                
                await db.configure_guild_channel(
                    guild_id,
                    'timezone',
                    channel_id,
                    {'timezone': timezone},
                    timezone
                )
                logger.info(f"✓ Configured timezone channel: {timezone} -> {channel_id}")
        
        # Migrate alert channels
        if 'market_event_channel_id' in config_data:
            await db.configure_guild_channel(
                guild_id,
                'market_events',
                config_data['market_event_channel_id']
            )
            logger.info(f"✓ Configured market events channel: {config_data['market_event_channel_id']}")
        
        if 'auto_update_channels' in config_data:
            channels = config_data['auto_update_channels']
            for channel_type, channel_id in channels.items():
                await db.configure_guild_channel(
                    guild_id,
                    channel_type,
                    channel_id
                )
                logger.info(f"✓ Configured {channel_type} channel: {channel_id}")
        
        # Migrate engagement settings
        if 'engagement' in config_data:
            eng = config_data['engagement']
            
            # Set engagement enabled
            await db.set_setting(guild_id, 'engagement.enabled', eng.get('enabled', False))
            logger.info(f"✓ Set engagement.enabled = {eng.get('enabled', False)}")
            
            # Set thresholds
            if 'thresholds' in eng:
                thresholds = eng['thresholds']
                if 'active_messages' in thresholds:
                    await db.set_setting(guild_id, 'engagement.messages_threshold', thresholds['active_messages'])
                    logger.info(f"✓ Set engagement.messages_threshold = {thresholds['active_messages']}")
                if 'active_days' in thresholds:
                    await db.set_setting(guild_id, 'engagement.days_threshold', thresholds['active_days'])
                    logger.info(f"✓ Set engagement.days_threshold = {thresholds['active_days']}")
            
            # Set warnings
            if 'warnings' in eng:
                warnings = eng['warnings']
                if 'days_before' in warnings:
                    await db.set_setting(guild_id, 'engagement.warning_days', warnings['days_before'])
                    logger.info(f"✓ Set engagement.warning_days = {warnings['days_before']}")
                if 'min_messages_warning' in warnings:
                    await db.set_setting(guild_id, 'engagement.warning_min_messages', warnings['min_messages_warning'])
                    logger.info(f"✓ Set engagement.warning_min_messages = {warnings['min_messages_warning']}")
                if 'dm_enabled' in warnings:
                    await db.set_setting(guild_id, 'engagement.dm_warnings', warnings['dm_enabled'])
                    logger.info(f"✓ Set engagement.dm_warnings = {warnings['dm_enabled']}")
        
        # Migrate engagement log channel
        if 'engagement' in config_data and 'channels' in config_data['engagement']:
            eng_channels = config_data['engagement']['channels']
            if 'engagement_log_id' in eng_channels:
                await db.configure_guild_channel(
                    guild_id,
                    'engagement_log',
                    eng_channels['engagement_log_id']
                )
                logger.info(f"✓ Configured engagement log channel: {eng_channels['engagement_log_id']}")
        
        logger.info("\n✅ Configuration migration complete!")
        
        # Show all settings
        logger.info("\n=== Current Settings ===")
        all_settings = await db.get_all_settings(guild_id)
        for key, data in all_settings.items():
            logger.info(f"{key}: {data['value']}")
        
    finally:
        await db.close()

if __name__ == "__main__":
    asyncio.run(migrate_config())
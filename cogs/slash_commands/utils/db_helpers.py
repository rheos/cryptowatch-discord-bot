"""
Database helper functions for slash commands
Modular, reusable functions for database operations
"""
import logging
from typing import Dict, List, Optional, Any
import aiomysql

logger = logging.getLogger('discord-bot.db_helpers')

async def get_guild_settings(pool, guild_id: int) -> Dict[str, Any]:
    """
    Get all settings for a guild from the new schema
    Returns a dictionary with setting keys and values
    """
    try:
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute("""
                    SELECT sr.setting_key, gs.value, sr.description, sr.setting_type
                    FROM guild_settings gs
                    JOIN settings_registry sr ON gs.setting_id = sr.setting_id
                    WHERE gs.guild_id = %s
                """, (guild_id,))
                
                results = await cursor.fetchall()
                
                settings = {}
                for row in results:
                    key = row['setting_key']
                    value = row['value']
                    # Convert value based on type
                    if row['setting_type'] == 'boolean':
                        settings[key] = value.lower() == 'true'
                    elif row['setting_type'] == 'integer':
                        settings[key] = int(value) if value else 0
                    else:
                        settings[key] = value
                
                return settings
                
    except Exception as e:
        logger.error(f"Error getting guild settings: {e}")
        return {}

async def get_timezone_channels(pool, guild_id: int) -> List[Dict]:
    """
    Get all timezone channels for a guild
    """
    try:
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute("""
                    SELECT channel_id, timezone, display_name 
                    FROM timezone_channels 
                    WHERE guild_id = %s
                    ORDER BY timezone
                """, (guild_id,))
                
                return await cursor.fetchall()
                
    except Exception as e:
        logger.error(f"Error getting timezone channels: {e}")
        return []

async def set_guild_setting(pool, guild_id: int, setting_key: str, value: Any) -> bool:
    """
    Set a single guild setting
    """
    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                # Get setting_id
                await cursor.execute("""
                    SELECT setting_id, setting_type 
                    FROM settings_registry 
                    WHERE setting_key = %s
                """, (setting_key,))
                
                result = await cursor.fetchone()
                if not result:
                    logger.error(f"Setting key not found: {setting_key}")
                    return False
                
                setting_id, setting_type = result
                
                # Convert value to string based on type
                if setting_type == 'boolean':
                    value_str = 'true' if value else 'false'
                else:
                    value_str = str(value)
                
                # Insert or update
                await cursor.execute("""
                    INSERT INTO guild_settings (guild_id, setting_id, value)
                    VALUES (%s, %s, %s)
                    ON DUPLICATE KEY UPDATE value = VALUES(value)
                """, (guild_id, setting_id, value_str))
                
                await conn.commit()
                return True
                
    except Exception as e:
        logger.error(f"Error setting guild setting {setting_key}: {e}")
        return False

async def enable_feature(pool, guild_id: int, feature: str) -> bool:
    """
    Enable a feature for a guild
    Features: market_enabled, funding_enabled, volatility_enabled, engagement_enabled, timezone_enabled
    """
    return await set_guild_setting(pool, guild_id, f"{feature}_enabled", True)

async def disable_feature(pool, guild_id: int, feature: str) -> bool:
    """
    Disable a feature for a guild
    """
    return await set_guild_setting(pool, guild_id, f"{feature}_enabled", False)

async def configure_channel(pool, guild_id: int, channel_type: str, channel_id: int) -> bool:
    """
    Configure a channel for a specific purpose
    Channel types: market_countdown, market_schedule, funding_alerts, general_alerts, volatility_alerts
    """
    return await set_guild_setting(pool, guild_id, channel_type, str(channel_id))

async def add_timezone_channel(pool, guild_id: int, channel_id: int, timezone: str, display_name: Optional[str] = None) -> bool:
    """
    Add or update a timezone channel
    """
    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("""
                    INSERT INTO timezone_channels (guild_id, channel_id, timezone, display_name)
                    VALUES (%s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE 
                        timezone = VALUES(timezone),
                        display_name = VALUES(display_name)
                """, (guild_id, channel_id, timezone, display_name))
                
                await conn.commit()
                return True
                
    except Exception as e:
        logger.error(f"Error adding timezone channel: {e}")
        return False

async def remove_timezone_channel(pool, guild_id: int, channel_id: int) -> bool:
    """
    Remove a timezone channel
    """
    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("""
                    DELETE FROM timezone_channels 
                    WHERE guild_id = %s AND channel_id = %s
                """, (guild_id, channel_id))
                
                await conn.commit()
                return cursor.rowcount > 0
                
    except Exception as e:
        logger.error(f"Error removing timezone channel: {e}")
        return False

async def get_feature_status(pool, guild_id: int) -> Dict[str, bool]:
    """
    Get status of all features for a guild
    """
    settings = await get_guild_settings(pool, guild_id)
    
    return {
        'market': settings.get('market_enabled', False),
        'funding': settings.get('funding_enabled', False),
        'volatility': settings.get('volatility_enabled', False),
        'engagement': settings.get('engagement_enabled', False),
        'timezone': settings.get('timezone_enabled', False),
    }

async def get_configured_channels(pool, guild_id: int) -> Dict[str, Optional[int]]:
    """
    Get all configured channel IDs for a guild
    """
    settings = await get_guild_settings(pool, guild_id)
    
    channels = {}
    channel_keys = ['market_countdown', 'market_schedule', 'funding_alerts', 
                   'general_alerts', 'volatility_alerts']
    
    for key in channel_keys:
        if key in settings:
            try:
                channels[key] = int(settings[key])
            except (ValueError, TypeError):
                channels[key] = None
        else:
            channels[key] = None
    
    return channels
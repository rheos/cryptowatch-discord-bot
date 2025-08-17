"""
Database connection and utilities for Discord bot - Version 2 with improved schema
"""
import aiomysql
import logging
import json
from typing import Optional, Dict, Any, List
from datetime import datetime, date, timedelta
# from migrations.migration_runner import MigrationRunner  # Removed - using SQL migrations directly

logger = logging.getLogger('discord-bot.database')
# Set up logger if not already configured
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

class BotDatabase:
    def __init__(self, config):
        self.config = config
        self.pool = None
        
    async def connect(self):
        """Create database connection pool"""
        db_config = self.config.get('database', {})
        
        self.pool = await aiomysql.create_pool(
            host=db_config.get('host', 'localhost'),
            port=db_config.get('port', 3306),
            user=db_config.get('user', 'bot_user'),
            password=db_config.get('password'),
            db='cryptowatch_bot',  # Always use Discord bot database
            minsize=5,
            maxsize=10,
            autocommit=False,
            charset='utf8mb4'
        )
        logger.info("Database connection pool created")
        
        # Migrations are now run manually via SQL files
        # No automatic migration on connect
        
    async def close(self):
        """Close database connections"""
        if self.pool:
            self.pool.close()
            await self.pool.wait_closed()
            logger.info("Database connection pool closed")
    
    # Guild Management
    async def register_guild(self, guild_id: int, guild_name: str, owner_id: int):
        """Register a new guild"""
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("""
                    INSERT INTO guilds (guild_id, guild_name, owner_id)
                    VALUES (%s, %s, %s) AS new_values
                    ON DUPLICATE KEY UPDATE 
                        guild_name = new_values.guild_name,
                        owner_id = new_values.owner_id,
                        updated_at = NOW()
                """, (guild_id, guild_name, owner_id))
                
                await conn.commit()
                logger.info(f"Registered guild: {guild_name} ({guild_id})")
    
    # Settings Management (EAV Pattern)
    async def get_setting(self, guild_id: int, setting_key: str) -> Optional[Any]:
        """Get a single setting value"""
        async with self.pool.acquire() as conn:
            # Ensure we're reading fresh data by committing any pending transactions
            await conn.commit()
            
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                # First try to get guild-specific setting
                await cursor.execute("""
                    SELECT gs.value as setting_value, sr.setting_type
                    FROM guild_settings gs
                    JOIN settings_registry sr ON gs.setting_id = sr.setting_id
                    WHERE gs.guild_id = %s AND sr.setting_key = %s
                """, (guild_id, setting_key))
                
                result = await cursor.fetchone()
                
                # If no guild setting, get default
                if not result:
                    await cursor.execute("""
                        SELECT default_value as setting_value, setting_type
                        FROM settings_registry
                        WHERE setting_key = %s
                    """, (setting_key,))
                    result = await cursor.fetchone()
                
                if not result:
                    return None
                
                # Convert value based on type
                return self._convert_setting_value(result['setting_value'], result['setting_type'])
    
    async def set_setting(self, guild_id: int, setting_key: str, value: Any, updated_by: int = None):
        """Set a setting value using new normalized schema"""
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                # Convert value to string
                str_value = json.dumps(value) if isinstance(value, (dict, list)) else str(value)
                
                # Get setting_id from registry
                await cursor.execute("""
                    SELECT setting_id FROM settings_registry 
                    WHERE setting_key = %s
                """, (setting_key,))
                
                result = await cursor.fetchone()
                if not result:
                    logger.error(f"Setting key not found: {setting_key}")
                    return False
                
                setting_id = result['setting_id']
                
                # Insert or update the setting
                await cursor.execute("""
                    INSERT INTO guild_settings (guild_id, setting_id, value)
                    VALUES (%s, %s, %s)
                    ON DUPLICATE KEY UPDATE 
                        value = VALUES(value),
                        updated_at = NOW()
                """, (guild_id, setting_id, str_value))
                
                await conn.commit()
                return True
    
    async def get_all_settings(self, guild_id: int, category: str = None) -> Dict[str, Any]:
        """Get all settings for a guild"""
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                query = """
                    SELECT 
                        sr.setting_key,
                        COALESCE(gs.value, sr.default_value) as value,
                        sr.setting_type,
                        sr.description,
                        ss.section_key as category
                    FROM settings_registry sr
                    LEFT JOIN guild_settings gs ON sr.setting_id = gs.setting_id AND gs.guild_id = %s
                    LEFT JOIN settings_sections ss ON sr.section_id = ss.section_id
                """
                params = [guild_id]
                
                if category:
                    query += " WHERE sd.category = %s"
                    params.append(category)
                
                await cursor.execute(query, params)
                
                settings = {}
                for row in await cursor.fetchall():
                    value = self._convert_setting_value(row['value'], row['setting_type'])
                    settings[row['setting_key']] = {
                        'value': value,
                        'description': row['description'],
                        'category': row['category']
                    }
                
                return settings
    
    def _convert_setting_value(self, value: str, setting_type: str) -> Any:
        """Convert setting value from string to appropriate type"""
        if value is None:
            return None
            
        if setting_type == 'boolean':
            return value.lower() in ('true', '1', 'yes', 'on')
        elif setting_type == 'integer':
            return int(value)
        elif setting_type == 'json':
            return json.loads(value)
        else:  # string
            return value
    
    # Channel Management
    async def configure_guild_channel(self, guild_id: int, channel_type: str, channel_id: int, 
                                    settings: dict = None, channel_subtype: str = None):
        """Configure a channel for a guild"""
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("""
                    INSERT INTO guild_channels (guild_id, channel_type, channel_subtype, channel_id, settings)
                    VALUES (%s, %s, %s, %s, %s) AS new_values
                    ON DUPLICATE KEY UPDATE 
                        settings = new_values.settings,
                        updated_at = NOW()
                """, (guild_id, channel_type, channel_subtype, channel_id, json.dumps(settings or {})))
                await conn.commit()
    
    async def get_guild_channels(self, guild_id: int, channel_type: str = None) -> List[Dict[str, Any]]:
        """Get configured channels for a guild"""
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                query = "SELECT * FROM guild_channels WHERE guild_id = %s"
                params = [guild_id]
                
                if channel_type:
                    query += " AND channel_type = %s"
                    params.append(channel_type)
                
                await cursor.execute(query, params)
                
                channels = []
                for row in await cursor.fetchall():
                    channel_data = dict(row)
                    if channel_data['settings']:
                        channel_data['settings'] = json.loads(channel_data['settings'])
                    channels.append(channel_data)
                
                return channels
    
    async def remove_guild_channel(self, guild_id: int, channel_id: int) -> bool:
        """Remove a channel configuration by channel ID"""
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("""
                    DELETE FROM guild_channels 
                    WHERE guild_id = %s AND channel_id = %s
                """, (guild_id, channel_id))
                affected = cursor.rowcount
                await conn.commit()
                return affected > 0
    
    # Activity Tracking
    async def track_message(self, guild_id: int, user_id: int):
        """Track a message from a user"""
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                # Update daily activity
                await cursor.execute("""
                    INSERT INTO member_activity_daily (guild_id, user_id, activity_date, message_count)
                    VALUES (%s, %s, CURDATE(), 1)
                    ON DUPLICATE KEY UPDATE message_count = message_count + 1
                """, (guild_id, user_id))
                
                # Update member status
                await cursor.execute("""
                    INSERT INTO member_status (guild_id, user_id, last_message_at)
                    VALUES (%s, %s, NOW())
                    ON DUPLICATE KEY UPDATE last_message_at = NOW()
                """, (guild_id, user_id))
                
                await conn.commit()
    
    async def get_member_stats(self, guild_id: int, user_id: int, days: int = 30) -> dict:
        """Get member statistics"""
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute("""
                    SELECT 
                        SUM(message_count) as total_messages,
                        COUNT(DISTINCT activity_date) as active_days,
                        MAX(activity_date) as last_active_date
                    FROM member_activity_daily
                    WHERE guild_id = %s 
                        AND user_id = %s 
                        AND activity_date >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
                """, (guild_id, user_id, days))
                
                return await cursor.fetchone()
    
    async def get_active_members(self, guild_id: int, threshold: int = 10, days: int = 30) -> list:
        """Get members who meet the activity threshold"""
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute("""
                    SELECT 
                        user_id,
                        SUM(message_count) as total_messages,
                        COUNT(DISTINCT activity_date) as active_days,
                        MAX(activity_date) as last_active_date
                    FROM member_activity_daily
                    WHERE guild_id = %s 
                        AND activity_date >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
                    GROUP BY user_id
                    HAVING total_messages >= %s
                    ORDER BY total_messages DESC
                """, (guild_id, days, threshold))
                
                return await cursor.fetchall()
    
    async def get_all_member_stats(self, guild_id: int, days: int = 30) -> list:
        """Get statistics for all members in a guild"""
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                # Debug: Check what database we're connected to
                await cursor.execute("SELECT DATABASE()")
                db_name = await cursor.fetchone()
                logger.info(f"get_all_member_stats: Querying database '{db_name['DATABASE()']}' for guild {guild_id}")
                
                await cursor.execute("""
                    SELECT 
                        user_id,
                        SUM(message_count) as total_messages,
                        COUNT(DISTINCT activity_date) as active_days,
                        MAX(activity_date) as last_active_date
                    FROM member_activity_daily
                    WHERE guild_id = %s 
                        AND activity_date >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
                    GROUP BY user_id
                    ORDER BY total_messages DESC
                """, (guild_id, days))
                
                results = await cursor.fetchall()
                logger.info(f"get_all_member_stats: Found {len(results)} members with activity in last {days} days")
                return results
    
    # Audit Logging
    async def log_action(self, guild_id: int, user_id: int, action: str, 
                        entity_type: str = None, entity_id: str = None,
                        old_value: Any = None, new_value: Any = None):
        """Log an action for audit trail"""
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                old_json = json.dumps(old_value) if old_value is not None else None
                new_json = json.dumps(new_value) if new_value is not None else None
                
                await cursor.execute("""
                    INSERT INTO audit_log 
                    (guild_id, user_id, action, entity_type, entity_id, old_value, new_value)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (guild_id, user_id, action, entity_type, entity_id, old_json, new_json))
                
                await conn.commit()
    
    # Compatibility methods for engagement features
    async def get_engagement_settings(self, guild_id: int) -> dict:
        """Get engagement settings for a guild (compatibility method)"""
        settings = {}
        
        # Get all engagement settings
        # Note: engagement_enabled is in Features section, others are in Engagement section
        engagement_keys = [
            'engagement_enabled',  # In Features section (enables/disables the feature)
            'messages_threshold',  # In Engagement section
            'days_threshold',      # In Engagement section
            'warning_days',        # In Engagement section
            'warning_min_messages', # In Engagement section
            'dm_warnings'          # In Engagement section
        ]
        
        for key in engagement_keys:
            value = await self.get_setting(guild_id, key)
            # Map to old field names for compatibility
            if key == 'engagement_enabled':
                settings['enabled'] = value
            elif key == 'messages_threshold':
                settings['active_messages_threshold'] = value
            elif key == 'days_threshold':
                settings['active_days_threshold'] = value
            elif key == 'warning_days':
                settings['warning_days_before'] = value
            elif key == 'warning_min_messages':
                settings['warning_min_messages'] = value
            elif key == 'dm_warnings':
                settings['dm_warnings_enabled'] = value
        
        return settings
    
    async def update_engagement_settings(self, guild_id: int, **kwargs):
        """Update engagement settings (compatibility method)"""
        # Map old field names to new setting keys
        field_mapping = {
            'enabled': 'engagement_enabled',
            'active_messages_threshold': 'messages_threshold',
            'active_days_threshold': 'days_threshold',
            'warning_days_before': 'warning_days',
            'warning_min_messages': 'warning_min_messages',
            'dm_warnings_enabled': 'dm_warnings'
        }
        
        for old_field, value in kwargs.items():
            if old_field in field_mapping:
                await self.set_setting(guild_id, field_mapping[old_field], value)
    
    async def get_guild_settings(self, guild_id: int) -> dict:
        """Get all settings for a guild (compatibility method)"""
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                # Get basic guild info
                await cursor.execute("""
                    SELECT * FROM guilds WHERE guild_id = %s
                """, (guild_id,))
                guild = await cursor.fetchone()
                
                if not guild:
                    return None
                
                # Get all settings
                settings = await self.get_all_settings(guild_id)
                
                # Get channels
                channels = {}
                channel_list = await self.get_guild_channels(guild_id)
                for channel in channel_list:
                    if channel['channel_subtype']:
                        # For timezone channels
                        key = f"{channel['channel_type']}_{channel['channel_subtype'].replace('/', '_')}"
                    else:
                        key = channel['channel_type']
                    
                    channels[key] = {
                        'id': channel['channel_id'],
                        'settings': channel['settings']
                    }
                
                return {
                    'guild': guild,
                    'settings': settings,
                    'channels': channels
                }
    
    async def update_member_activity(self, guild_id: int, user_id: int, 
                                    activity_date: str, message_count: int):
        """Update member activity for a specific date"""
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("""
                    INSERT INTO member_activity_daily 
                    (guild_id, user_id, activity_date, message_count)
                    VALUES (%s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE 
                    message_count = message_count + VALUES(message_count)
                """, (guild_id, user_id, activity_date, message_count))
                await conn.commit()
    
    async def get_activity_summary(self, guild_id: int) -> dict:
        """Get summary of engagement data for a guild"""
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute("""
                    SELECT 
                        MIN(activity_date) as earliest_date,
                        MAX(activity_date) as latest_date,
                        COUNT(DISTINCT activity_date) as total_days,
                        SUM(message_count) as total_messages,
                        COUNT(DISTINCT user_id) as unique_members,
                        AVG(daily_total) as avg_messages_per_day
                    FROM (
                        SELECT 
                            activity_date,
                            SUM(message_count) as daily_total,
                            user_id
                        FROM member_activity_daily
                        WHERE guild_id = %s
                        GROUP BY activity_date, user_id
                    ) as daily_stats
                """, (guild_id,))
                
                summary = await cursor.fetchone()
                
                if summary and summary['total_messages']:
                    return {
                        'earliest_date': summary['earliest_date'],
                        'latest_date': summary['latest_date'],
                        'total_days': summary['total_days'],
                        'total_messages': int(summary['total_messages']),
                        'unique_members': summary['unique_members'],
                        'avg_messages_per_day': float(summary['avg_messages_per_day'] or 0)
                    }
                
                return None
    
    async def remove_guild_channel(self, guild_id: int, channel_id: int):
        """Remove a channel configuration"""
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("""
                    DELETE FROM guild_channels 
                    WHERE guild_id = %s AND channel_id = %s
                """, (guild_id, channel_id))
                await conn.commit()
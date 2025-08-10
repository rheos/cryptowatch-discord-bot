"""
Database connection and utilities for Discord bot
"""
import aiomysql
import logging
import json
from typing import Optional
from migrations.migration_runner import MigrationRunner

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
            db=db_config.get('name', 'cryptowatch_bot'),
            minsize=5,
            maxsize=10,
            autocommit=False,
            charset='utf8mb4'
        )
        logger.info("Database connection pool created")
        
        # Run migrations
        runner = MigrationRunner(self.pool)
        await runner.run_all_pending()
        
    async def close(self):
        """Close database connections"""
        if self.pool:
            self.pool.close()
            await self.pool.wait_closed()
            logger.info("Database connection pool closed")
    
    async def get_guild_settings(self, guild_id: int) -> dict:
        """Get settings for a guild"""
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                # Get basic guild info
                await cursor.execute("""
                    SELECT * FROM guilds WHERE guild_id = %s
                """, (guild_id,))
                guild = await cursor.fetchone()
                
                if not guild:
                    return None
                
                # Get settings
                await cursor.execute("""
                    SELECT * FROM guild_settings WHERE guild_id = %s
                """, (guild_id,))
                settings = await cursor.fetchone()
                
                # Get channels
                await cursor.execute("""
                    SELECT channel_type, channel_id, settings 
                    FROM guild_channels WHERE guild_id = %s
                """, (guild_id,))
                channels = {}
                for row in await cursor.fetchall():
                    channels[row['channel_type']] = {
                        'id': row['channel_id'],
                        'settings': json.loads(row['settings']) if row['settings'] else {}
                    }
                
                return {
                    'guild': guild,
                    'settings': settings,
                    'channels': channels
                }
    
    async def track_message(self, guild_id: int, user_id: int):
        """Track a message from a user"""
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                # Update daily activity
                await cursor.execute("""
                    INSERT INTO member_activity (guild_id, user_id, date, message_count)
                    VALUES (%s, %s, CURDATE(), 1)
                    ON DUPLICATE KEY UPDATE message_count = message_count + 1
                """, (guild_id, user_id))
                
                # Update member status
                await cursor.execute("""
                    INSERT INTO member_status (guild_id, user_id, last_message_at, total_messages)
                    VALUES (%s, %s, NOW(), 1)
                    ON DUPLICATE KEY UPDATE 
                        last_message_at = NOW(),
                        total_messages = total_messages + 1
                """, (guild_id, user_id))
                
                await conn.commit()
    
    async def get_member_stats(self, guild_id: int, user_id: int, days: int = 30) -> dict:
        """Get member statistics"""
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute("""
                    SELECT 
                        SUM(message_count) as total_messages,
                        COUNT(DISTINCT date) as active_days,
                        MAX(date) as last_active_date
                    FROM member_activity
                    WHERE guild_id = %s 
                        AND user_id = %s 
                        AND date >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
                """, (guild_id, user_id, days))
                
                return await cursor.fetchone()
    
    async def register_guild(self, guild_id: int, guild_name: str, owner_id: int):
        """Register a new guild"""
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("""
                    INSERT INTO guilds (guild_id, guild_name, owner_id)
                    VALUES (%s, %s, %s)
                    ON DUPLICATE KEY UPDATE 
                        guild_name = VALUES(guild_name),
                        owner_id = VALUES(owner_id),
                        updated_at = NOW()
                """, (guild_id, guild_name, owner_id))
                
                # Insert default settings
                await cursor.execute("""
                    INSERT IGNORE INTO guild_settings (guild_id)
                    VALUES (%s)
                """, (guild_id,))
                
                await conn.commit()
                logger.info(f"Registered guild: {guild_name} ({guild_id})")
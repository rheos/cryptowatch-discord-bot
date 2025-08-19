"""
Activity tracking module for engagement system
Handles message counting and buffering for efficient database writes
"""
import discord
import asyncio
import time
import logging
from collections import defaultdict
from datetime import datetime, timedelta

logger = logging.getLogger('engagement.activity_tracker')


class ActivityTracker:
    """Tracks member activity and buffers database writes"""
    
    def __init__(self, bot):
        self.bot = bot
        self.message_buffer = defaultdict(lambda: defaultdict(int))
        self.buffer_lock = asyncio.Lock()
        self.last_flush_time = time.time()
        
        # Cache for member activity
        self.member_activity = defaultdict(lambda: {"messages": 0, "last_active": None})
        
    async def track_message(self, guild_id, user_id):
        """Buffer a message for tracking"""
        async with self.buffer_lock:
            self.message_buffer[guild_id][user_id] += 1
    
    async def flush_buffer(self):
        """Flush the message buffer to database"""
        async with self.buffer_lock:
            if not self.message_buffer:
                return
            
            # Copy and clear buffer
            buffer_copy = dict(self.message_buffer)
            self.message_buffer.clear()
        
        # Batch update to database
        try:
            updates = []
            for guild_id, user_counts in buffer_copy.items():
                for user_id, count in user_counts.items():
                    updates.append((guild_id, user_id, count))
            
            if updates:
                async with self.bot.db.pool.acquire() as conn:
                    async with conn.cursor() as cursor:
                        # Batch update all message counts
                        await cursor.executemany("""
                            INSERT INTO member_activity_daily (guild_id, user_id, activity_date, message_count)
                            VALUES (%s, %s, CURDATE(), %s)
                            ON DUPLICATE KEY UPDATE message_count = message_count + VALUES(message_count)
                        """, updates)
                        
                        # Update last_message_at for all users
                        for guild_id, user_id, _ in updates:
                            await cursor.execute("""
                                INSERT INTO member_status (guild_id, user_id, last_message_at)
                                VALUES (%s, %s, NOW())
                                ON DUPLICATE KEY UPDATE last_message_at = NOW()
                            """, (guild_id, user_id))
                        
                        await conn.commit()
                
                logger.info(f"Flushed {len(updates)} user message counts to database")
        except Exception as e:
            logger.error(f"Error flushing message buffer: {e}", exc_info=True)
    
    async def get_member_activity(self, guild_id, member_id, days=30):
        """Get member activity in the last X days"""
        try:
            # Get activity from database
            stats = await self.bot.db.get_member_stats(guild_id, member_id, days)
            
            if stats:
                return {
                    "messages": stats['total_messages'] or 0,
                    "last_active": stats['last_active_date'],
                    "active_days": stats.get('active_days', 0)
                }
            else:
                return {"messages": 0, "last_active": None, "active_days": 0}
            
        except Exception as e:
            logger.error(f"Error getting activity for member {member_id}: {e}")
            return {"messages": 0, "last_active": None, "active_days": 0}
    
    async def get_all_member_stats(self, guild_id, days=30):
        """Get activity stats for all members in a guild"""
        try:
            return await self.bot.db.get_all_member_stats(guild_id, days)
        except Exception as e:
            logger.error(f"Error getting all member stats: {e}")
            return []
    
    async def get_active_members(self, guild_id, threshold=10, days=30):
        """Get list of active members"""
        try:
            return await self.bot.db.get_active_members(guild_id, threshold, days)
        except Exception as e:
            logger.error(f"Error getting active members: {e}")
            return []
    
    # Backfill functionality removed - use scripts/backfill_engagement.py instead
    # The external script is more robust with proper database handling
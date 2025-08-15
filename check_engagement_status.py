#!/usr/bin/env python3
"""
Check and enable engagement tracking
"""

import asyncio
import logging
import json
import aiomysql
import os
from config_loader import load_config

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('check_engagement')

async def check_and_enable_engagement():
    """Check engagement status and enable if needed"""
    
    # Load config using the same loader as main.py
    config = load_config('config.development.json')
    db_config = config['database']
    
    logger.info(f"Connecting to database at {db_config['host']}:{db_config['port']}")
    
    # Connect to database
    pool = await aiomysql.create_pool(
        host=db_config['host'],
        port=db_config['port'],
        user=db_config['user'],
        password=db_config['password'],
        db=db_config['name'],
        minsize=1,
        maxsize=5,
        autocommit=False
    )
    
    try:
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                # Get all guilds
                await cursor.execute("SELECT guild_id, guild_name FROM guilds")
                guilds = await cursor.fetchall()
                
                if not guilds:
                    logger.warning("No guilds found in database")
                    return
                
                for guild in guilds:
                    guild_id = guild['guild_id']
                    guild_name = guild['guild_name']
                    
                    logger.info(f"\n=== Guild: {guild_name} ({guild_id}) ===")
                    
                    # Check engagement settings
                    await cursor.execute("""
                        SELECT setting_key, setting_value
                        FROM guild_settings
                        WHERE guild_id = %s AND setting_key LIKE 'engagement.%'
                    """, (guild_id,))
                    settings = await cursor.fetchall()
                    
                    engagement_enabled = False
                    if settings:
                        for setting in settings:
                            logger.info(f"  {setting['setting_key']}: {setting['setting_value']}")
                            if setting['setting_key'] == 'engagement.enabled' and setting['setting_value'] == '1':
                                engagement_enabled = True
                    else:
                        logger.info("  No engagement settings found")
                    
                    # Enable engagement if not enabled
                    if not engagement_enabled:
                        logger.info("  🔧 Enabling engagement tracking...")
                        
                        # Set default engagement settings
                        default_settings = [
                            ('engagement.enabled', '1'),
                            ('engagement.messages_threshold', '10'),
                            ('engagement.days_threshold', '30'),
                            ('engagement.warning_days', '7'),
                            ('engagement.warning_min_messages', '5'),
                        ]
                        
                        for key, value in default_settings:
                            await cursor.execute("""
                                INSERT INTO guild_settings (guild_id, setting_key, setting_value)
                                VALUES (%s, %s, %s)
                                ON DUPLICATE KEY UPDATE setting_value = VALUES(setting_value)
                            """, (guild_id, key, value))
                        
                        await conn.commit()
                        logger.info("  ✅ Engagement tracking enabled!")
                    
                    # Check recent activity
                    await cursor.execute("""
                        SELECT COUNT(DISTINCT user_id) as unique_users,
                               SUM(message_count) as total_messages,
                               MIN(activity_date) as oldest,
                               MAX(activity_date) as newest
                        FROM member_activity_daily
                        WHERE guild_id = %s
                    """, (guild_id,))
                    activity = await cursor.fetchone()
                    
                    if activity and activity['unique_users']:
                        logger.info(f"\n  Activity Summary:")
                        logger.info(f"    Unique users: {activity['unique_users']}")
                        logger.info(f"    Total messages: {activity['total_messages'] or 0}")
                        logger.info(f"    Date range: {activity['oldest']} to {activity['newest']}")
                        
                        # Show top 5 active users
                        await cursor.execute("""
                            SELECT user_id, SUM(message_count) as total_messages
                            FROM member_activity_daily
                            WHERE guild_id = %s
                            GROUP BY user_id
                            ORDER BY total_messages DESC
                            LIMIT 5
                        """, (guild_id,))
                        top_users = await cursor.fetchall()
                        
                        if top_users:
                            logger.info(f"\n  Top 5 Active Users:")
                            for i, user in enumerate(top_users, 1):
                                logger.info(f"    {i}. User {user['user_id']}: {user['total_messages']} messages")
                    else:
                        logger.info("  No activity data found")
                
    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        pool.close()
        await pool.wait_closed()

if __name__ == "__main__":
    asyncio.run(check_and_enable_engagement())
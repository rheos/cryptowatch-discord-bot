#!/usr/bin/env python3
"""
Test engagement tracking to diagnose issues
"""

import asyncio
import logging
import json
import aiomysql
from datetime import datetime, timedelta

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('test_engagement')

async def test_engagement():
    """Test engagement tracking functionality"""
    
    # Load config
    with open('config.development.json', 'r') as f:
        config = json.load(f)
    
    db_config = config['database']
    
    # Connect to database
    pool = await aiomysql.create_pool(
        host=db_config['host'],
        port=db_config['port'],
        user=db_config['user'],
        password=db_config['password'],
        db=db_config['database'],
        minsize=1,
        maxsize=5,
        autocommit=False
    )
    
    try:
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                # Check if tables exist
                logger.info("=== Checking Tables ===")
                await cursor.execute("SHOW TABLES LIKE '%member%'")
                tables = await cursor.fetchall()
                for table in tables:
                    logger.info(f"Found table: {list(table.values())[0]}")
                
                # Check member_activity_daily table structure
                logger.info("\n=== member_activity_daily Structure ===")
                await cursor.execute("DESCRIBE member_activity_daily")
                columns = await cursor.fetchall()
                for col in columns:
                    logger.info(f"  {col['Field']}: {col['Type']}")
                
                # Check if there's any data
                logger.info("\n=== Checking Data ===")
                await cursor.execute("""
                    SELECT COUNT(*) as count, 
                           MIN(activity_date) as oldest, 
                           MAX(activity_date) as newest
                    FROM member_activity_daily
                """)
                result = await cursor.fetchone()
                logger.info(f"Total records: {result['count']}")
                logger.info(f"Date range: {result['oldest']} to {result['newest']}")
                
                # Check recent activity (last 7 days)
                await cursor.execute("""
                    SELECT guild_id, COUNT(DISTINCT user_id) as unique_users,
                           SUM(message_count) as total_messages
                    FROM member_activity_daily
                    WHERE activity_date >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
                    GROUP BY guild_id
                """)
                recent = await cursor.fetchall()
                if recent:
                    logger.info("\n=== Recent Activity (Last 7 Days) ===")
                    for row in recent:
                        logger.info(f"Guild {row['guild_id']}: {row['unique_users']} users, {row['total_messages']} messages")
                else:
                    logger.info("\n=== No recent activity found ===")
                
                # Check engagement settings
                logger.info("\n=== Checking Engagement Settings ===")
                await cursor.execute("""
                    SELECT guild_id, setting_key, setting_value
                    FROM guild_settings
                    WHERE setting_key LIKE 'engagement.%'
                """)
                settings = await cursor.fetchall()
                if settings:
                    guild_settings = {}
                    for row in settings:
                        guild_id = row['guild_id']
                        if guild_id not in guild_settings:
                            guild_settings[guild_id] = {}
                        guild_settings[guild_id][row['setting_key']] = row['setting_value']
                    
                    for guild_id, settings in guild_settings.items():
                        logger.info(f"\nGuild {guild_id}:")
                        for key, value in settings.items():
                            logger.info(f"  {key}: {value}")
                else:
                    logger.info("No engagement settings found in any guild")
                
                # Test inserting a record (to verify table is working)
                logger.info("\n=== Testing Insert ===")
                test_guild_id = 123456789  # Test guild ID
                test_user_id = 987654321   # Test user ID
                
                try:
                    await cursor.execute("""
                        INSERT INTO member_activity_daily 
                        (guild_id, user_id, activity_date, message_count)
                        VALUES (%s, %s, CURDATE(), 1)
                        ON DUPLICATE KEY UPDATE message_count = message_count + 1
                    """, (test_guild_id, test_user_id))
                    await conn.commit()
                    logger.info("✅ Test insert successful")
                    
                    # Clean up test data
                    await cursor.execute("""
                        DELETE FROM member_activity_daily 
                        WHERE guild_id = %s AND user_id = %s
                    """, (test_guild_id, test_user_id))
                    await conn.commit()
                    logger.info("✅ Test data cleaned up")
                    
                except Exception as e:
                    logger.error(f"❌ Test insert failed: {e}")
                    await conn.rollback()
                
    except Exception as e:
        logger.error(f"Error during test: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        pool.close()
        await pool.wait_closed()

if __name__ == "__main__":
    asyncio.run(test_engagement())
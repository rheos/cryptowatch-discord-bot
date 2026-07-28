#!/usr/bin/env python3
"""
Migration: Add active_days_threshold setting to registry
This adds the ability to require a certain number of unique active days for the Active role
"""

import asyncio
import aiomysql
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def migrate(pool):
    """Add active_days_threshold to settings registry"""
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            try:
                # Check if setting already exists
                await cursor.execute("""
                    SELECT setting_id FROM settings_registry 
                    WHERE setting_key = 'active_days_threshold'
                """)
                
                if await cursor.fetchone():
                    logger.info("active_days_threshold already exists in registry")
                    return True
                
                # Add the setting to registry
                await cursor.execute("""
                    INSERT INTO settings_registry 
                    (setting_key, setting_type, default_value, description, section_id, display_order)
                    VALUES (
                        'active_days_threshold', 
                        'integer', 
                        NULL, 
                        'Number of unique active days required for Active role', 
                        4,  -- Member Engagement section
                        3   -- Display after messages and days threshold
                    )
                """)
                
                await conn.commit()
                logger.info("✓ Added active_days_threshold to settings registry")
                return True
                
            except Exception as e:
                logger.error(f"Migration failed: {e}")
                await conn.rollback()
                return False

async def main():
    """Run migration standalone"""
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    
    # Determine environment
    mysql_host = os.getenv('MYSQL_HOST', 'mysql')
    if mysql_host == 'mysql' or os.getenv('ENVIRONMENT') == 'dev':
        # Docker environment
        host = 'mysql'
    else:
        # Production
        host = 'localhost'
    
    pool = await aiomysql.create_pool(
        host=host,
        port=3306,
        user='cwt_user',
        password=os.getenv('MYSQL_PASSWORD', ''),
        db='cryptowatch_bot',
        minsize=1,
        maxsize=2
    )
    
    try:
        success = await migrate(pool)
        if success:
            logger.info("Migration completed successfully")
        else:
            logger.error("Migration failed")
    finally:
        pool.close()
        await pool.wait_closed()

if __name__ == "__main__":
    asyncio.run(main())

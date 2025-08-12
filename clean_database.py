#!/usr/bin/env python3
"""
Clean up old database schema to prepare for V2
"""
import asyncio
import aiomysql
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def clean_database():
    """Drop old tables and prepare for V2 schema"""
    config = {
        'host': os.environ.get('MYSQL_HOST', 'mysql'),
        'port': 3306,
        'user': 'cwt_user',
        'password': 'example_password',
        'db': 'cryptowatch_bot',
        'charset': 'utf8mb4'
    }
    
    conn = await aiomysql.connect(**config)
    
    try:
        async with conn.cursor() as cursor:
            # Get list of all tables
            await cursor.execute("SHOW TABLES")
            tables = await cursor.fetchall()
            
            if tables:
                logger.info(f"Found {len(tables)} tables to drop")
                
                # Disable foreign key checks
                await cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
                
                # Drop all tables
                for (table_name,) in tables:
                    logger.info(f"Dropping table: {table_name}")
                    await cursor.execute(f"DROP TABLE IF EXISTS `{table_name}`")
                
                # Re-enable foreign key checks
                await cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
                
                await conn.commit()
                logger.info("✓ All tables dropped successfully")
            else:
                logger.info("No tables to drop")
                
    finally:
        await conn.ensure_closed()

if __name__ == "__main__":
    asyncio.run(clean_database())
#!/usr/bin/env python3
"""
Test new v2 database schema in development environment
"""
import asyncio
import aiomysql
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_connection():
    """Test database connection and create schema"""
    # Database config for Discord bot
    import os
    config = {
        'host': os.environ.get('MYSQL_HOST', 'mysql'),  # Use mysql hostname in Docker
        'port': 3306,
        'user': 'cwt_user',
        'password': 'example_password',
        'db': 'cryptowatch_bot',  # Discord bot database
        'charset': 'utf8mb4'
    }
    
    try:
        # Create connection
        conn = await aiomysql.connect(**config)
        logger.info("✓ Connected to database")
        
        async with conn.cursor() as cursor:
            # Check if we need to create the database
            await cursor.execute("SHOW DATABASES LIKE 'cryptowatch_bot'")
            result = await cursor.fetchone()
            
            if not result:
                logger.info("Creating cryptowatch_bot database...")
                await cursor.execute("CREATE DATABASE IF NOT EXISTS cryptowatch_bot")
                await cursor.execute("USE cryptowatch_bot")
                logger.info("✓ Database created")
            else:
                await cursor.execute("USE cryptowatch_bot")
                logger.info("✓ Using existing cryptowatch_bot database")
            
            # Check existing tables
            await cursor.execute("SHOW TABLES")
            tables = await cursor.fetchall()
            if tables:
                logger.info(f"Existing tables: {[t[0] for t in tables]}")
            else:
                logger.info("No existing tables found")
        
        await conn.ensure_closed()
        return True
        
    except Exception as e:
        logger.error(f"Connection failed: {e}")
        return False

async def run_test_migration():
    """Run a test to ensure migrations will work"""
    from database import BotDatabase
    import os
    
    config = {
        'database': {
            'host': os.environ.get('MYSQL_HOST', 'mysql'),
            'port': 3306,
            'user': 'cwt_user',
            'password': 'example_password',
            'name': 'cryptowatch_bot'
        }
    }
    
    db = BotDatabase(config)
    
    try:
        logger.info("\n=== Running V2 Migration Test ===")
        await db.connect()
        logger.info("✓ Database connected with V2 schema")
        
        # Test basic operations
        guild_id = 1000000000000000000
        
        # Register guild
        await db.register_guild(guild_id, "Development Test Guild", 123456789)
        logger.info("✓ Guild registered")
        
        # Set a setting
        await db.set_setting(guild_id, 'engagement.enabled', False)
        value = await db.get_setting(guild_id, 'engagement.enabled')
        logger.info(f"✓ Setting stored and retrieved: engagement.enabled = {value}")
        
        # Configure a channel
        await db.configure_guild_channel(
            guild_id,
            'timezone',
            1395417773823361044,
            {'timezone': 'America/Vancouver'},
            'America/Vancouver'
        )
        logger.info("✓ Channel configured")
        
        # Get channels
        channels = await db.get_guild_channels(guild_id)
        logger.info(f"✓ Retrieved {len(channels)} channels")
        
        await db.close()
        logger.info("\n✅ All tests passed! V2 schema is working.")
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
        if db.pool:
            await db.close()

async def main():
    # First test connection
    if await test_connection():
        # Then run migration test
        await run_test_migration()
    else:
        logger.error("Cannot proceed - database connection failed")

if __name__ == "__main__":
    asyncio.run(main())
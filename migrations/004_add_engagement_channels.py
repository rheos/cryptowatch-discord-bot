"""
Migration to add engagement channel settings to the registry
"""
import asyncio
import aiomysql
import json
import os
from datetime import datetime

async def run_migration(pool):
    """Add engagement channel settings to registry"""
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            print("Adding engagement channel settings to registry...")
            
            # Add welcome_channel_id and introductions_channel_id to settings_registry
            settings_to_add = [
                ('welcome_channel_id', 'string', 'Channel ID for welcome messages', None),
                ('introductions_channel_id', 'string', 'Channel ID for introductions', None)
            ]
            
            for setting_key, setting_type, description, default_value in settings_to_add:
                # Check if already exists
                await cursor.execute("""
                    SELECT setting_id FROM settings_registry 
                    WHERE setting_key = %s
                """, (setting_key,))
                
                existing = await cursor.fetchone()
                if not existing:
                    await cursor.execute("""
                        INSERT INTO settings_registry 
                        (setting_key, setting_type, description, default_value)
                        VALUES (%s, %s, %s, %s)
                    """, (setting_key, setting_type, description, default_value))
                    print(f"  ✓ Added {setting_key} to registry")
                else:
                    print(f"  - {setting_key} already exists")
            
            await conn.commit()
            print("✓ Migration completed: engagement channel settings added")

async def main():
    """Run the migration"""
    # Get database credentials - using correct database name!
    db_config = {
        'host': os.getenv('MYSQL_HOST', 'mysql'),
        'port': int(os.getenv('MYSQL_PORT', 3306)),
        'user': os.getenv('MYSQL_USER', 'cwt_user'),
        'password': os.getenv('MYSQL_PASSWORD', ''),
        'db': 'cryptowatch_bot',  # CORRECT database name
    }
    
    # Create connection pool
    pool = await aiomysql.create_pool(**db_config)
    
    try:
        await run_migration(pool)
    finally:
        pool.close()
        await pool.wait_closed()

if __name__ == "__main__":
    asyncio.run(main())

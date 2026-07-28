"""
Migration: Add market display channels table with support for various market data types
Date: 2025-09-02
Purpose: Support voice channel updates with flexible market data (prices and market info)
"""
import asyncio
import aiomysql
import os
from datetime import datetime

async def run_migration(pool):
    """Add market display channels table and settings"""
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            print("Creating market display channels table...")
            
            # Create market_display_channels table following timezone_channels pattern
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS market_display_channels (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    guild_id BIGINT NOT NULL,
                    channel_id BIGINT NOT NULL UNIQUE,
                    display_type ENUM(
                        'coin_price',    -- Uses price API with symbol (BTC, ETH, DOGE, etc.)
                        'market_info'    -- Uses market-info API with symbol as field name
                    ) NOT NULL,
                    symbol VARCHAR(50) NOT NULL COMMENT 'Coin symbol OR market-info field name',
                    custom_label VARCHAR(50) DEFAULT NULL COMMENT 'Optional custom label for display',
                    enabled BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    
                    INDEX idx_guild (guild_id),
                    INDEX idx_guild_enabled (guild_id, enabled),
                    
                    FOREIGN KEY (guild_id) REFERENCES guilds(guild_id) ON DELETE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                COMMENT='Market data display configuration for voice channels'
            """)
            print("  ✓ Created market_display_channels table")
            
            # Add setting to enable/disable the feature
            await cursor.execute("""
                SELECT section_id FROM settings_sections WHERE section_key = 'features'
            """)
            features_section = await cursor.fetchone()
            features_section_id = features_section[0] if features_section else 1
            
            # Add market_display_enabled setting
            await cursor.execute("""
                SELECT setting_id FROM settings_registry 
                WHERE setting_key = 'market_display_enabled'
            """)
            
            if not await cursor.fetchone():
                await cursor.execute("""
                    INSERT INTO settings_registry 
                    (setting_key, setting_type, default_value, description, section_id)
                    VALUES ('market_display_enabled', 'boolean', 'false', 
                            'Enable market data display in voice channels', %s)
                """, (features_section_id,))
                print("  ✓ Added market_display_enabled to settings registry")
            else:
                print("  - market_display_enabled already exists")
            
            # Get channels section ID
            await cursor.execute("""
                SELECT section_id FROM settings_sections WHERE section_key = 'channels'
            """)
            channels_section = await cursor.fetchone()
            channels_section_id = channels_section[0] if channels_section else 2
            
            # Add market_display_interval setting
            await cursor.execute("""
                SELECT setting_id FROM settings_registry 
                WHERE setting_key = 'market_display_interval'
            """)
            
            if not await cursor.fetchone():
                await cursor.execute("""
                    INSERT INTO settings_registry 
                    (setting_key, setting_type, default_value, description, section_id)
                    VALUES ('market_display_interval', 'integer', '5', 
                            'Update interval in minutes for market display (min 5, max 60)', %s)
                """, (channels_section_id,))
                print("  ✓ Added market_display_interval to settings registry")
            else:
                print("  - market_display_interval already exists")
            
            await conn.commit()
            print("✓ Migration completed: market_display_channels table created")

async def main():
    """Run the migration"""
    # Get database credentials
    db_config = {
        'host': os.getenv('MYSQL_HOST', 'mysql'),
        'port': int(os.getenv('MYSQL_PORT', 3306)),
        'user': os.getenv('MYSQL_USER', 'cwt_user'),
        'password': os.getenv('MYSQL_PASSWORD', ''),
        'db': 'cryptowatch_bot',  # Discord bot database
        'autocommit': False
    }
    
    # Create connection pool
    pool = await aiomysql.create_pool(**db_config, minsize=1, maxsize=5)
    
    try:
        await run_migration(pool)
    except Exception as e:
        print(f"Migration failed: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
    finally:
        pool.close()
        await pool.wait_closed()

if __name__ == "__main__":
    asyncio.run(main())

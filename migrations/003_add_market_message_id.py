#!/usr/bin/env python3
"""
Add market_schedule_message_id setting to track the pinned message
"""
import pymysql
from pymysql.cursors import DictCursor
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate():
    """Add market_schedule_message_id setting"""
    
    connection = pymysql.connect(
        host=os.getenv('MYSQL_HOST', 'mysql'),
        port=int(os.getenv('MYSQL_PORT', 3306)),
        user=os.getenv('MYSQL_USER', 'cwt_user'),
        password=os.getenv('MYSQL_PASSWORD', ''),
        database='cryptowatch_bot',
        charset='utf8mb4',
        cursorclass=DictCursor,
        autocommit=True
    )
    
    try:
        with connection.cursor() as cursor:
            # Get channels section ID
            cursor.execute("""
                SELECT section_id FROM settings_sections 
                WHERE section_key = 'channels'
            """)
            channels_section = cursor.fetchone()['section_id']
            
            # Add market_schedule_message_id setting
            cursor.execute("""
                INSERT INTO settings_registry (
                    setting_key, setting_type, default_value, 
                    section_id, display_order, description
                ) VALUES (
                    'market_schedule_message_id', 'string', NULL,
                    %s, 6, 'Message ID for pinned market schedule'
                )
                ON DUPLICATE KEY UPDATE description = VALUES(description)
            """, (channels_section,))
            
            logger.info("✓ Added market_schedule_message_id setting")
            
            # Also ensure market_enabled is properly set for all guilds that have channels configured
            cursor.execute("""
                SELECT DISTINCT guild_id 
                FROM guild_settings gs
                JOIN settings_registry sr ON gs.setting_id = sr.setting_id
                WHERE sr.setting_key IN ('market_countdown', 'market_schedule')
            """)
            
            guilds_with_channels = cursor.fetchall()
            
            for row in guilds_with_channels:
                guild_id = row['guild_id']
                
                # Check if market_enabled is set
                cursor.execute("""
                    SELECT COUNT(*) as count
                    FROM guild_settings gs
                    JOIN settings_registry sr ON gs.setting_id = sr.setting_id
                    WHERE gs.guild_id = %s AND sr.setting_key = 'market_enabled'
                """, (guild_id,))
                
                if cursor.fetchone()['count'] == 0:
                    # Enable market events for this guild
                    cursor.execute("""
                        INSERT INTO guild_settings (guild_id, setting_id, value)
                        SELECT %s, setting_id, 'true'
                        FROM settings_registry
                        WHERE setting_key = 'market_enabled'
                    """, (guild_id,))
                    logger.info(f"✓ Enabled market events for guild {guild_id}")
            
            logger.info("✅ Migration 003 completed successfully")
            
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise
    finally:
        connection.close()

if __name__ == "__main__":
    migrate()

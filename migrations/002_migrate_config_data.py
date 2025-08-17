#!/usr/bin/env python3
"""
Migrate configuration from config.json to new normalized V3 schema
"""
import asyncio
import json
import os
import pymysql
from pymysql.cursors import DictCursor
import logging
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_db_connection():
    """Get database connection"""
    # Note: switch_env.sh sets MYSQL_DATABASE to 'cryptowatch_bot' but we need 'cryptowatchtools'
    # The actual database name is 'cryptowatchtools' on both dev and prod
    return pymysql.connect(
        host=os.getenv('MYSQL_HOST', 'mysql'),
        port=int(os.getenv('MYSQL_PORT', 3306)),
        user=os.getenv('MYSQL_USER', 'cwt_user'),
        password=os.getenv('MYSQL_PASSWORD'),
        database='cryptowatch_bot',  # Discord bot database
        charset='utf8mb4',
        cursorclass=DictCursor,
        autocommit=True
    )

def migrate_config():
    """Migrate config from JSON to normalized database schema"""
    
    # Load config file from environment variable
    config_file = os.environ.get('CONFIG_FILE')
    if not config_file:
        logger.error("CONFIG_FILE environment variable not set!")
        logger.error("Run: source .env  (after using ./switch_env.sh dev|prod)")
        return False
    
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), config_file)
    
    if not os.path.exists(config_path):
        logger.error(f"Config file not found: {config_path}")
        logger.error(f"Make sure {config_file} exists")
        return False
    
    with open(config_path, 'r') as f:
        config_data = json.load(f)
    
    logger.info(f"Loaded config from {config_file}")
    
    # Get guild ID from config file first, then fallback to environment
    guild_id = config_data.get('guild_id')
    
    # If not in config, try environment variable
    if not guild_id:
        guild_id = os.getenv('DISCORD_GUILD_ID')
        if guild_id:
            guild_id = int(guild_id)
    
    # If still not found, try to extract from Discord bot logs
    if not guild_id:
        log_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs', 'discord.log')
        if os.path.exists(log_path):
            with open(log_path, 'r') as f:
                for line in f:
                    if 'Guild ID:' in line:
                        try:
                            guild_id = int(line.split('Guild ID:')[1].strip().split()[0])
                            logger.info(f"Found guild ID from logs: {guild_id}")
                            break
                        except:
                            pass
    
    # Last resort fallback (shouldn't happen)
    if not guild_id:
        logger.error("No guild ID found in config, environment, or logs!")
        raise ValueError("Guild ID is required for migration")
    
    server_name = config_data.get('server_name', 'Unknown')
    
    logger.info(f"=== Migrating Configuration for {server_name} (Guild: {guild_id}) ===")
    
    try:
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                
                # 1. Register the guild
                cursor.execute("""
                    INSERT INTO guilds (guild_id, guild_name)
                    VALUES (%s, %s)
                    ON DUPLICATE KEY UPDATE 
                        guild_name = VALUES(guild_name),
                        is_active = TRUE
                """, (guild_id, server_name))
                logger.info(f"✓ Registered guild: {server_name}")
                
                # 2. Set up subscription (free tier by default)
                cursor.execute("""
                    INSERT INTO guild_subscriptions (guild_id, tier_id, status, trial_ends_at)
                    SELECT %s, tier_id, 'active', DATE_ADD(NOW(), INTERVAL 30 DAY)
                    FROM subscription_tiers 
                    WHERE tier_name = 'free'
                    ON DUPLICATE KEY UPDATE status = VALUES(status)
                """, (guild_id,))
                logger.info("✓ Set up free tier subscription")
                
                # 3. Migrate timezone channels
                if 'timezone_channels' in config_data:
                    for tz_config in config_data['timezone_channels']:
                        timezone = tz_config['timezone']
                        channel_id = tz_config['channel_id']
                        
                        # Determine custom display name
                        display_name = None
                        if timezone == 'America/Halifax':
                            display_name = 'PEI'
                        elif timezone == 'Asia/Kolkata':
                            display_name = 'India'
                        
                        cursor.execute("""
                            INSERT INTO timezone_channels (guild_id, channel_id, timezone, display_name)
                            VALUES (%s, %s, %s, %s)
                            ON DUPLICATE KEY UPDATE 
                                timezone = VALUES(timezone),
                                display_name = VALUES(display_name)
                        """, (guild_id, channel_id, timezone, display_name))
                        
                        logger.info(f"✓ Configured timezone channel: {timezone} -> {channel_id}")
                
                # 4. Migrate channel settings
                # Get section IDs
                cursor.execute("SELECT section_id FROM settings_sections WHERE section_key = 'channels'")
                channels_section = cursor.fetchone()['section_id']
                
                cursor.execute("SELECT section_id FROM settings_sections WHERE section_key = 'features'")
                features_section = cursor.fetchone()['section_id']
                
                cursor.execute("SELECT section_id FROM settings_sections WHERE section_key = 'engagement'")
                engagement_section = cursor.fetchone()['section_id']
                
                # Market event channels (voice countdown and text schedule)
                if 'market_event_channel_id' in config_data:
                    # This is the VOICE channel for countdown
                    cursor.execute("""
                        INSERT INTO guild_settings (guild_id, setting_id, value)
                        SELECT %s, setting_id, %s
                        FROM settings_registry 
                        WHERE section_id = %s AND setting_key = 'market_countdown'
                        ON DUPLICATE KEY UPDATE value = VALUES(value)
                    """, (guild_id, str(config_data['market_event_channel_id']), channels_section))
                    logger.info(f"✓ Configured market countdown channel (voice): {config_data['market_event_channel_id']}")
                
                if 'market_times_message_channel_id' in config_data:
                    # This is the TEXT channel for schedule
                    cursor.execute("""
                        INSERT INTO guild_settings (guild_id, setting_id, value)
                        SELECT %s, setting_id, %s
                        FROM settings_registry 
                        WHERE section_id = %s AND setting_key = 'market_schedule'
                        ON DUPLICATE KEY UPDATE value = VALUES(value)
                    """, (guild_id, str(config_data['market_times_message_channel_id']), channels_section))
                    logger.info(f"✓ Configured market schedule channel (text): {config_data['market_times_message_channel_id']}")
                
                # Enable market events feature if channels are configured
                if 'market_event_channel_id' in config_data or 'market_times_message_channel_id' in config_data:
                    cursor.execute("""
                        INSERT INTO guild_settings (guild_id, setting_id, value)
                        SELECT %s, setting_id, 'true'
                        FROM settings_registry 
                        WHERE section_id = %s AND setting_key = 'market_enabled'
                        ON DUPLICATE KEY UPDATE value = VALUES(value)
                    """, (guild_id, features_section))
                    logger.info("✓ Enabled market events feature")
                
                # Auto update channels
                if 'auto_update_channels' in config_data:
                    channels = config_data['auto_update_channels']
                    
                    if 'funding' in channels:
                        cursor.execute("""
                            INSERT INTO guild_settings (guild_id, setting_id, value)
                            SELECT %s, setting_id, %s
                            FROM settings_registry 
                            WHERE section_id = %s AND setting_key = 'funding_alerts'
                            ON DUPLICATE KEY UPDATE value = VALUES(value)
                        """, (guild_id, str(channels['funding']), channels_section))
                        logger.info(f"✓ Configured funding alerts channel: {channels['funding']}")
                    
                    if 'alerts' in channels:
                        cursor.execute("""
                            INSERT INTO guild_settings (guild_id, setting_id, value)
                            SELECT %s, setting_id, %s
                            FROM settings_registry 
                            WHERE section_id = %s AND setting_key = 'general_alerts'
                            ON DUPLICATE KEY UPDATE value = VALUES(value)
                        """, (guild_id, str(channels['alerts']), channels_section))
                        logger.info(f"✓ Configured general alerts channel: {channels['alerts']}")
                
                # 5. Migrate engagement settings
                if 'engagement' in config_data:
                    eng = config_data['engagement']
                    
                    # Enable engagement
                    if eng.get('enabled', False):
                        cursor.execute("""
                            INSERT INTO guild_settings (guild_id, setting_id, value)
                            SELECT %s, setting_id, 'true'
                            FROM settings_registry 
                            WHERE section_id = %s AND setting_key = 'engagement_enabled'
                            ON DUPLICATE KEY UPDATE value = VALUES(value)
                        """, (guild_id, features_section))
                        logger.info(f"✓ Enabled engagement tracking")
                    
                    # Thresholds
                    if 'thresholds' in eng:
                        thresholds = eng['thresholds']
                        
                        if 'active_messages' in thresholds:
                            cursor.execute("""
                                INSERT INTO guild_settings (guild_id, setting_id, value)
                                SELECT %s, setting_id, %s
                                FROM settings_registry 
                                WHERE section_id = %s AND setting_key = 'messages_threshold'
                                ON DUPLICATE KEY UPDATE value = VALUES(value)
                            """, (guild_id, str(thresholds['active_messages']), engagement_section))
                            logger.info(f"✓ Set messages_threshold = {thresholds['active_messages']}")
                        
                        if 'active_days' in thresholds:
                            cursor.execute("""
                                INSERT INTO guild_settings (guild_id, setting_id, value)
                                SELECT %s, setting_id, %s
                                FROM settings_registry 
                                WHERE section_id = %s AND setting_key = 'days_threshold'
                                ON DUPLICATE KEY UPDATE value = VALUES(value)
                            """, (guild_id, str(thresholds['active_days']), engagement_section))
                            logger.info(f"✓ Set days_threshold = {thresholds['active_days']}")
                    
                    # Warnings
                    if 'warnings' in eng:
                        warnings = eng['warnings']
                        
                        if 'days_before' in warnings:
                            cursor.execute("""
                                INSERT INTO guild_settings (guild_id, setting_id, value)
                                SELECT %s, setting_id, %s
                                FROM settings_registry 
                                WHERE section_id = %s AND setting_key = 'warning_days'
                                ON DUPLICATE KEY UPDATE value = VALUES(value)
                            """, (guild_id, str(warnings['days_before']), engagement_section))
                            logger.info(f"✓ Set warning_days = {warnings['days_before']}")
                        
                        if 'min_messages_warning' in warnings:
                            cursor.execute("""
                                INSERT INTO guild_settings (guild_id, setting_id, value)
                                SELECT %s, setting_id, %s
                                FROM settings_registry 
                                WHERE section_id = %s AND setting_key = 'warning_min_messages'
                                ON DUPLICATE KEY UPDATE value = VALUES(value)
                            """, (guild_id, str(warnings['min_messages_warning']), engagement_section))
                            logger.info(f"✓ Set warning_min_messages = {warnings['min_messages_warning']}")
                        
                        if 'dm_enabled' in warnings:
                            cursor.execute("""
                                INSERT INTO guild_settings (guild_id, setting_id, value)
                                SELECT %s, setting_id, %s
                                FROM settings_registry 
                                WHERE section_id = %s AND setting_key = 'dm_warnings'
                                ON DUPLICATE KEY UPDATE value = VALUES(value)
                            """, (guild_id, 'true' if warnings['dm_enabled'] else 'false', engagement_section))
                            logger.info(f"✓ Set dm_warnings = {warnings['dm_enabled']}")
                
                # 6. Enable timezone feature
                cursor.execute("""
                    INSERT INTO guild_settings (guild_id, setting_id, value)
                    SELECT %s, setting_id, 'true'
                    FROM settings_registry 
                    WHERE section_id = %s AND setting_key = 'timezone_enabled'
                    ON DUPLICATE KEY UPDATE value = VALUES(value)
                """, (guild_id, features_section))
                logger.info("✓ Enabled timezone feature")
                
                # 7. Log the migration
                cursor.execute("""
                    INSERT INTO audit_log (guild_id, user_id, action, entity_type, entity_id, new_value)
                    VALUES (%s, NULL, 'CONFIG_MIGRATION', 'guild', %s, %s)
                """, (guild_id, str(guild_id), f'Migrated configuration from {config_file}'))
                
                logger.info("\n✅ Configuration migration complete!")
                
                # Show summary
                cursor.execute("""
                    SELECT COUNT(*) as count FROM timezone_channels WHERE guild_id = %s
                """, (guild_id,))
                tz_count = cursor.fetchone()['count']
                
                cursor.execute("""
                    SELECT COUNT(*) as count FROM guild_settings WHERE guild_id = %s
                """, (guild_id,))
                settings_count = cursor.fetchone()['count']
                
                logger.info(f"Summary: {tz_count} timezone channels, {settings_count} settings configured")
                
                return True
                
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        return False

if __name__ == "__main__":
    success = migrate_config()
    exit(0 if success else 1)
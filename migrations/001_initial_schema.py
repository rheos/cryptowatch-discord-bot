"""
Initial database schema for Discord bot - Version 2 with improved design
"""

async def up(cursor):
    """Create initial tables with improved schema"""
    
    # Guilds table
    await cursor.execute("""
        CREATE TABLE IF NOT EXISTS guilds (
            guild_id BIGINT PRIMARY KEY,
            guild_name VARCHAR(255),
            owner_id BIGINT,
            subscription_tier ENUM('free', 'basic', 'premium') DEFAULT 'free',
            subscription_expires TIMESTAMP NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            INDEX idx_subscription (subscription_tier, subscription_expires),
            INDEX idx_created (created_at)
        )
    """)
    
    # Settings definitions table
    await cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings_definitions (
            id INT AUTO_INCREMENT PRIMARY KEY,
            setting_key VARCHAR(100) UNIQUE,
            setting_type ENUM('boolean', 'integer', 'string', 'json') NOT NULL,
            default_value TEXT,
            description TEXT,
            category VARCHAR(50),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_category (category)
        )
    """)
    
    # Guild settings (EAV pattern)
    await cursor.execute("""
        CREATE TABLE IF NOT EXISTS guild_settings (
            guild_id BIGINT,
            setting_key VARCHAR(100),
            setting_value TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            updated_by BIGINT,
            PRIMARY KEY (guild_id, setting_key),
            FOREIGN KEY (guild_id) REFERENCES guilds(guild_id) ON DELETE CASCADE,
            FOREIGN KEY (setting_key) REFERENCES settings_definitions(setting_key),
            INDEX idx_updated (updated_at)
        )
    """)
    
    # Member activity - recent daily data (auto-cleanup after 90 days)
    await cursor.execute("""
        CREATE TABLE IF NOT EXISTS member_activity_daily (
            guild_id BIGINT,
            user_id BIGINT,
            activity_date DATE,
            message_count INT DEFAULT 0,
            voice_minutes INT DEFAULT 0,
            PRIMARY KEY (guild_id, user_id, activity_date),
            INDEX idx_guild_date (guild_id, activity_date),
            INDEX idx_user_activity (guild_id, user_id, message_count),
            INDEX idx_cleanup (activity_date)
        )
    """)
    
    # Member activity summary - aggregated data for long-term storage
    await cursor.execute("""
        CREATE TABLE IF NOT EXISTS member_activity_summary (
            guild_id BIGINT,
            user_id BIGINT,
            period_start DATE,
            period_type ENUM('week', 'month') DEFAULT 'month',
            message_count INT DEFAULT 0,
            voice_minutes INT DEFAULT 0,
            active_days INT DEFAULT 0,
            PRIMARY KEY (guild_id, user_id, period_start, period_type),
            INDEX idx_guild_period (guild_id, period_start, period_type),
            INDEX idx_user_stats (guild_id, user_id, period_type, period_start DESC)
        )
    """)
    
    # Member status (without redundant total_messages)
    await cursor.execute("""
        CREATE TABLE IF NOT EXISTS member_status (
            guild_id BIGINT,
            user_id BIGINT,
            current_role ENUM('new_member', 'member', 'active', 'vacation'),
            last_message_at TIMESTAMP,
            vacation_until DATE NULL,
            warned_at TIMESTAMP NULL,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (guild_id, user_id),
            INDEX idx_role (guild_id, current_role),
            INDEX idx_warned (guild_id, warned_at),
            INDEX idx_last_active (guild_id, last_message_at),
            FOREIGN KEY (guild_id) REFERENCES guilds(guild_id) ON DELETE CASCADE
        )
    """)
    
    # Flexible channel configuration
    await cursor.execute("""
        CREATE TABLE IF NOT EXISTS guild_channels (
            id INT AUTO_INCREMENT PRIMARY KEY,
            guild_id BIGINT,
            channel_type VARCHAR(50) NOT NULL,
            channel_subtype VARCHAR(100),
            channel_id BIGINT UNIQUE,
            settings JSON,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            INDEX idx_guild_type (guild_id, channel_type),
            INDEX idx_guild_type_subtype (guild_id, channel_type, channel_subtype),
            INDEX idx_channel (channel_id),
            FOREIGN KEY (guild_id) REFERENCES guilds(guild_id) ON DELETE CASCADE
        )
    """)
    
    # Audit log for tracking changes
    await cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            guild_id BIGINT,
            user_id BIGINT,
            action VARCHAR(100) NOT NULL,
            entity_type VARCHAR(50),
            entity_id VARCHAR(100),
            old_value TEXT,
            new_value TEXT,
            ip_address VARCHAR(45),
            user_agent TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_guild_time (guild_id, timestamp),
            INDEX idx_entity (entity_type, entity_id),
            INDEX idx_user_actions (user_id, timestamp),
            INDEX idx_cleanup (timestamp)
        )
    """)
    
    # Create event to clean up old daily activity data (keep 90 days)
    await cursor.execute("""
        CREATE EVENT IF NOT EXISTS cleanup_old_activity
        ON SCHEDULE EVERY 1 DAY
        DO DELETE FROM member_activity_daily 
        WHERE activity_date < DATE_SUB(CURDATE(), INTERVAL 90 DAY)
    """)
    
    # Create event to clean up old audit logs (keep 180 days)
    await cursor.execute("""
        CREATE EVENT IF NOT EXISTS cleanup_old_audit_logs
        ON SCHEDULE EVERY 1 DAY
        DO DELETE FROM audit_log 
        WHERE timestamp < DATE_SUB(NOW(), INTERVAL 180 DAY)
    """)

async def down(cursor):
    """Drop all tables and events"""
    # Drop events first
    await cursor.execute("DROP EVENT IF EXISTS cleanup_old_activity")
    await cursor.execute("DROP EVENT IF EXISTS cleanup_old_audit_logs")
    
    # Drop tables in reverse order of dependencies
    tables = [
        'audit_log',
        'guild_channels',
        'member_status',
        'member_activity_summary',
        'member_activity_daily',
        'guild_settings',
        'settings_definitions',
        'guilds'
    ]
    
    for table in tables:
        await cursor.execute(f"DROP TABLE IF EXISTS {table}")
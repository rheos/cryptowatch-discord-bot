"""
Initial database schema for Discord bot
"""

async def up(cursor):
    """Create initial tables"""
    
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
    
    # Member activity tracking
    await cursor.execute("""
        CREATE TABLE IF NOT EXISTS member_activity (
            guild_id BIGINT,
            user_id BIGINT,
            date DATE,
            message_count INT DEFAULT 0,
            voice_minutes INT DEFAULT 0,
            PRIMARY KEY (guild_id, user_id, date),
            INDEX idx_guild_date (guild_id, date),
            INDEX idx_user_activity (guild_id, user_id, message_count),
            INDEX idx_date (date)
        )
    """)
    
    # Member status
    await cursor.execute("""
        CREATE TABLE IF NOT EXISTS member_status (
            guild_id BIGINT,
            user_id BIGINT,
            current_role ENUM('new_member', 'member', 'active', 'vacation'),
            last_message_at TIMESTAMP,
            total_messages INT DEFAULT 0,
            vacation_until DATE NULL,
            warned_at TIMESTAMP NULL,
            PRIMARY KEY (guild_id, user_id),
            INDEX idx_role (guild_id, current_role),
            INDEX idx_warned (guild_id, warned_at),
            INDEX idx_last_active (guild_id, last_message_at)
        )
    """)
    
    # Channel configuration
    await cursor.execute("""
        CREATE TABLE IF NOT EXISTS guild_channels (
            guild_id BIGINT,
            channel_type VARCHAR(50),
            channel_id BIGINT,
            settings JSON,
            PRIMARY KEY (guild_id, channel_type),
            INDEX idx_channel_id (channel_id),
            FOREIGN KEY (guild_id) REFERENCES guilds(guild_id) ON DELETE CASCADE
        )
    """)
    
    # Guild settings
    await cursor.execute("""
        CREATE TABLE IF NOT EXISTS guild_settings (
            guild_id BIGINT PRIMARY KEY,
            engagement_enabled BOOLEAN DEFAULT TRUE,
            active_messages_threshold INT DEFAULT 10,
            active_days_threshold INT DEFAULT 30,
            warning_days_before INT DEFAULT 7,
            warning_min_messages INT DEFAULT 7,
            dm_warnings_enabled BOOLEAN DEFAULT TRUE,
            settings JSON,
            FOREIGN KEY (guild_id) REFERENCES guilds(guild_id) ON DELETE CASCADE
        )
    """)

async def down(cursor):
    """Drop all tables"""
    tables = [
        'guild_settings',
        'guild_channels', 
        'member_status',
        'member_activity',
        'guilds'
    ]
    
    for table in tables:
        await cursor.execute(f"DROP TABLE IF EXISTS {table}")
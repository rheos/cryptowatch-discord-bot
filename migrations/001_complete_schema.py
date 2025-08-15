"""
Complete normalized database schema for Discord bot
"""

async def up(cursor):
    """Create complete normalized schema"""
    
    # =====================================================
    # Drop existing tables in correct order (foreign key dependencies)
    # =====================================================
    
    tables_to_drop = [
        'user_watchlist',
        'user_alert_preferences', 
        'alert_history',
        'guild_usage',
        'guild_subscriptions',
        'member_status',
        'member_activity_daily',
        'timezone_channels',
        'guild_settings',
        'settings_registry',
        'settings_sections',
        'timezone_definitions',
        'audit_log',
        'subscription_tiers',
        'guilds',
        'schema_migrations',
    ]
    
    for table in tables_to_drop:
        await cursor.execute(f"DROP TABLE IF EXISTS {table}")
    
    # =====================================================
    # Core Tables
    # =====================================================
    
    # Schema version tracking
    await cursor.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INT PRIMARY KEY,
            description VARCHAR(255),
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Guild registration
    await cursor.execute("""
        CREATE TABLE IF NOT EXISTS guilds (
            guild_id BIGINT PRIMARY KEY,
            guild_name VARCHAR(255) NOT NULL,
            owner_id BIGINT,
            member_count INT DEFAULT 0,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            left_at TIMESTAMP NULL,
            is_active BOOLEAN DEFAULT TRUE,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            INDEX idx_active (is_active),
            INDEX idx_joined (joined_at)
        )
    """)
    
    # =====================================================
    # Subscription & Billing Tables
    # =====================================================
    
    # Subscription tier definitions
    await cursor.execute("""
        CREATE TABLE IF NOT EXISTS subscription_tiers (
            tier_id INT PRIMARY KEY AUTO_INCREMENT,
            tier_name VARCHAR(50) UNIQUE NOT NULL,
            display_name VARCHAR(100),
            price_monthly DECIMAL(10,2),
            price_yearly DECIMAL(10,2),
            -- Feature limits
            max_timezones INT DEFAULT 1,
            max_alert_channels INT DEFAULT 1,
            max_watchlist_items INT DEFAULT 10,
            engagement_enabled BOOLEAN DEFAULT FALSE,
            volatility_enabled BOOLEAN DEFAULT FALSE,
            funding_enabled BOOLEAN DEFAULT FALSE,
            market_events_enabled BOOLEAN DEFAULT FALSE,
            -- AI Chat (Luna) limits
            ai_chat_enabled BOOLEAN DEFAULT FALSE,
            ai_chat_messages_per_day INT DEFAULT 0,
            ai_chat_model VARCHAR(50) DEFAULT 'gpt-3.5-turbo',
            -- Branding & Support
            custom_branding BOOLEAN DEFAULT FALSE,
            priority_support BOOLEAN DEFAULT FALSE,
            -- Alert limits
            volatility_check_interval_min INT DEFAULT 300,
            funding_check_interval_min INT DEFAULT 900,
            max_alerts_per_hour INT DEFAULT 20,
            -- Other limits
            data_retention_days INT DEFAULT 30,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_active (is_active)
        )
    """)
    
    # Guild subscriptions
    await cursor.execute("""
        CREATE TABLE IF NOT EXISTS guild_subscriptions (
            guild_id BIGINT PRIMARY KEY,
            tier_id INT NOT NULL,
            status ENUM('trial', 'active', 'cancelled', 'expired') DEFAULT 'trial',
            trial_ends_at TIMESTAMP NULL,
            current_period_start TIMESTAMP NULL,
            current_period_end TIMESTAMP NULL,
            cancel_at_period_end BOOLEAN DEFAULT FALSE,
            stripe_customer_id VARCHAR(255),
            stripe_subscription_id VARCHAR(255),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (guild_id) REFERENCES guilds(guild_id) ON DELETE CASCADE,
            FOREIGN KEY (tier_id) REFERENCES subscription_tiers(tier_id),
            INDEX idx_status (status),
            INDEX idx_tier (tier_id),
            INDEX idx_trial_ends (trial_ends_at),
            INDEX idx_period_end (current_period_end)
        )
    """)
    
    # Track usage for billing/limits
    await cursor.execute("""
        CREATE TABLE IF NOT EXISTS guild_usage (
            guild_id BIGINT NOT NULL,
            usage_date DATE NOT NULL,
            alerts_sent INT DEFAULT 0,
            api_calls INT DEFAULT 0,
            members_tracked INT DEFAULT 0,
            timezones_active INT DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (guild_id, usage_date),
            FOREIGN KEY (guild_id) REFERENCES guilds(guild_id) ON DELETE CASCADE,
            INDEX idx_date (usage_date)
        )
    """)
    
    # Audit logging
    await cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id INT PRIMARY KEY AUTO_INCREMENT,
            guild_id BIGINT NOT NULL,
            user_id BIGINT,
            action VARCHAR(50) NOT NULL,
            entity_type VARCHAR(50),
            entity_id VARCHAR(100),
            old_value VARCHAR(4000),
            new_value VARCHAR(4000),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_guild (guild_id),
            INDEX idx_user (user_id),
            INDEX idx_action (action),
            INDEX idx_created (created_at)
        )
    """)
    
    # =====================================================
    # Settings Tables (Properly Normalized)
    # =====================================================
    
    # Settings sections for organization
    await cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings_sections (
            section_id INT PRIMARY KEY AUTO_INCREMENT,
            section_key VARCHAR(50) UNIQUE NOT NULL,
            section_name VARCHAR(100) NOT NULL,
            description TEXT,
            display_order INT DEFAULT 999,
            icon VARCHAR(50),
            parent_section_id INT NULL,
            FOREIGN KEY (parent_section_id) REFERENCES settings_sections(section_id),
            INDEX idx_order (display_order)
        )
    """)
    
    # Settings definitions with validation
    await cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings_registry (
            setting_id INT PRIMARY KEY AUTO_INCREMENT,
            setting_key VARCHAR(50) NOT NULL,
            setting_type ENUM('boolean', 'integer', 'decimal', 'string') NOT NULL,
            default_value VARCHAR(255),
            description TEXT,
            section_id INT,
            display_order INT DEFAULT 999,
            is_advanced BOOLEAN DEFAULT FALSE,
            min_value DECIMAL(20,8),
            max_value DECIMAL(20,8),
            validation_regex VARCHAR(500),
            allowed_values TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY uk_section_key (section_id, setting_key),
            FOREIGN KEY (section_id) REFERENCES settings_sections(section_id),
            INDEX idx_key (setting_key),
            INDEX idx_section (section_id),
            INDEX idx_order (display_order)
        )
    """)
    
    # Guild-specific settings
    await cursor.execute("""
        CREATE TABLE IF NOT EXISTS guild_settings (
            guild_id BIGINT NOT NULL,
            setting_id INT NOT NULL,
            value VARCHAR(255) NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (guild_id, setting_id),
            FOREIGN KEY (setting_id) REFERENCES settings_registry(setting_id) ON DELETE CASCADE,
            FOREIGN KEY (guild_id) REFERENCES guilds(guild_id) ON DELETE CASCADE,
            INDEX idx_guild (guild_id),
            INDEX idx_setting (setting_id),
            INDEX idx_updated (updated_at)
        )
    """)
    
    # =====================================================
    # Channel Configuration Tables
    # =====================================================
    
    # Timezone definitions and display names
    await cursor.execute("""
        CREATE TABLE IF NOT EXISTS timezone_definitions (
            id INT PRIMARY KEY AUTO_INCREMENT,
            timezone VARCHAR(50) UNIQUE NOT NULL,
            display_name VARCHAR(50) NOT NULL,
            custom_name VARCHAR(50),
            country_code VARCHAR(2),
            region VARCHAR(50),
            priority INT DEFAULT 2,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_timezone (timezone),
            INDEX idx_country (country_code),
            INDEX idx_region (region),
            INDEX idx_priority (priority)
        )
    """)
    
    # Timezone display channels
    await cursor.execute("""
        CREATE TABLE IF NOT EXISTS timezone_channels (
            id INT PRIMARY KEY AUTO_INCREMENT,
            guild_id BIGINT NOT NULL,
            channel_id BIGINT NOT NULL UNIQUE,
            timezone VARCHAR(50) NOT NULL,
            display_name VARCHAR(50),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (guild_id) REFERENCES guilds(guild_id) ON DELETE CASCADE,
            FOREIGN KEY (timezone) REFERENCES timezone_definitions(timezone) ON DELETE RESTRICT,
            INDEX idx_guild (guild_id),
            INDEX idx_channel (channel_id),
            INDEX idx_timezone (timezone)
        )
    """)
    
    # =====================================================
    # Alert Tracking Tables
    # =====================================================
    
    # Alert history and cooldown tracking
    await cursor.execute("""
        CREATE TABLE IF NOT EXISTS alert_history (
            id INT PRIMARY KEY AUTO_INCREMENT,
            guild_id BIGINT NOT NULL,
            alert_type ENUM('volatility', 'funding', 'price', 'market') NOT NULL,
            symbol VARCHAR(20),
            timeframe VARCHAR(10),
            threshold_value DECIMAL(20,8),
            actual_value DECIMAL(20,8),
            channel_id BIGINT,
            message_id BIGINT,
            alert_count INT DEFAULT 1,
            last_alerted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (guild_id) REFERENCES guilds(guild_id) ON DELETE CASCADE,
            INDEX idx_guild_type (guild_id, alert_type),
            INDEX idx_symbol (symbol),
            INDEX idx_last_alert (last_alerted_at),
            INDEX idx_guild_symbol_type (guild_id, symbol, alert_type),
            INDEX idx_created (created_at)
        )
    """)
    
    # =====================================================
    # Engagement System Tables
    # =====================================================
    
    # Daily member activity tracking
    await cursor.execute("""
        CREATE TABLE IF NOT EXISTS member_activity_daily (
            guild_id BIGINT NOT NULL,
            user_id BIGINT NOT NULL,
            activity_date DATE NOT NULL,
            message_count INT DEFAULT 0,
            voice_minutes INT DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (guild_id, user_id, activity_date),
            FOREIGN KEY (guild_id) REFERENCES guilds(guild_id) ON DELETE CASCADE,
            INDEX idx_guild_date (guild_id, activity_date),
            INDEX idx_user_date (user_id, activity_date),
            INDEX idx_guild_user (guild_id, user_id)
        )
    """)
    
    # Member status tracking
    await cursor.execute("""
        CREATE TABLE IF NOT EXISTS member_status (
            guild_id BIGINT NOT NULL,
            user_id BIGINT NOT NULL,
            engagement_level INT DEFAULT 0,
            last_message_at TIMESTAMP NULL,
            last_warning_at TIMESTAMP NULL,
            vacation_start TIMESTAMP NULL,
            vacation_end TIMESTAMP NULL,
            total_messages INT DEFAULT 0,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (guild_id, user_id),
            FOREIGN KEY (guild_id) REFERENCES guilds(guild_id) ON DELETE CASCADE,
            INDEX idx_level (engagement_level),
            INDEX idx_last_message (last_message_at),
            INDEX idx_guild_level (guild_id, engagement_level),
            INDEX idx_warning (last_warning_at)
        )
    """)
    
    # =====================================================
    # User Preference Tables (Future Features)
    # =====================================================
    
    # User-specific alert preferences
    await cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_alert_preferences (
            user_id BIGINT NOT NULL,
            guild_id BIGINT NOT NULL,
            alert_type ENUM('volatility', 'funding', 'price') NOT NULL,
            enabled BOOLEAN DEFAULT TRUE,
            dm_enabled BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, guild_id, alert_type),
            FOREIGN KEY (guild_id) REFERENCES guilds(guild_id) ON DELETE CASCADE,
            INDEX idx_guild_type (guild_id, alert_type)
        )
    """)
    
    # User watchlists
    await cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_watchlist (
            user_id BIGINT NOT NULL,
            guild_id BIGINT NOT NULL,
            symbol VARCHAR(20) NOT NULL,
            volatility_threshold DECIMAL(5,2),
            funding_threshold DECIMAL(10,6),
            price_alert_above DECIMAL(20,8),
            price_alert_below DECIMAL(20,8),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, guild_id, symbol),
            FOREIGN KEY (guild_id) REFERENCES guilds(guild_id) ON DELETE CASCADE,
            INDEX idx_symbol (symbol),
            INDEX idx_guild (guild_id),
            INDEX idx_user (user_id)
        )
    """)
    
    # =====================================================
    # Initial Data Population
    # =====================================================
    
    # Populate settings sections (without emojis for now - charset issue)
    await cursor.execute("""
        INSERT INTO settings_sections (section_key, section_name, description, display_order) VALUES
        ('features', 'Features & Cogs', 'Enable or disable bot features', 1),
        ('channels', 'Channel Configuration', 'Configure channels for alerts and displays', 2),
        ('alerts', 'Alert Behavior', 'Alert timing and check intervals', 3),
        ('engagement', 'Member Engagement', 'Track and reward member activity', 4),
        ('market', 'Market Events', 'Market countdown and schedule settings', 5),
        ('volatility', 'Volatility Thresholds', 'Price volatility thresholds', 6),
        ('funding', 'Funding Thresholds', 'Funding rate thresholds', 7),
        ('general', 'General Settings', 'Bot behavior and preferences', 10)
    """)
    
    # Populate settings registry
    # Get section IDs first
    await cursor.execute("SELECT section_id, section_key FROM settings_sections")
    sections = {row['section_key']: row['section_id'] for row in await cursor.fetchall()}
    
    # Features & Cogs settings
    features_settings = [
        ('engagement_enabled', 'boolean', 'false', 'Enable engagement tracking', 1),
        ('market_enabled', 'boolean', 'false', 'Enable market event tracking', 2),
        ('volatility_enabled', 'boolean', 'false', 'Enable volatility alerts', 3),
        ('funding_enabled', 'boolean', 'false', 'Enable funding rate alerts', 4),
        ('timezone_enabled', 'boolean', 'true', 'Enable timezone display channels', 5),
    ]
    
    for key, type_, default, desc, order in features_settings:
        await cursor.execute("""
            INSERT INTO settings_registry (setting_key, setting_type, default_value, section_id, display_order, description)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (key, type_, default, sections['features'], order, desc))
    
    # Channel settings
    channel_settings = [
        ('market_countdown', 'string', None, 'Voice channel ID for market countdown', 1),
        ('market_schedule', 'string', None, 'Text channel ID for market schedule', 2),
        ('funding_alerts', 'string', None, 'Text channel ID for funding alerts', 3),
        ('volatility_alerts', 'string', None, 'Text channel ID for volatility alerts', 4),
        ('general_alerts', 'string', None, 'Text channel ID for general alerts', 5),
    ]
    
    for key, type_, default, desc, order in channel_settings:
        await cursor.execute("""
            INSERT INTO settings_registry (setting_key, setting_type, default_value, section_id, display_order, description)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (key, type_, default, sections['channels'], order, desc))
    
    # Alert behavior settings
    alert_settings = [
        ('volatility_check_interval', 'integer', '300', 'Volatility check interval in seconds', 1),
        ('funding_check_interval', 'integer', '900', 'Funding rate check interval in seconds', 2),
        ('market_pre_alert', 'integer', '15', 'Minutes before market event to alert', 3),
        ('cooldown_minutes', 'integer', '60', 'Cooldown between duplicate alerts (minutes)', 4),
    ]
    
    for key, type_, default, desc, order in alert_settings:
        await cursor.execute("""
            INSERT INTO settings_registry (setting_key, setting_type, default_value, section_id, display_order, description, min_value)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (key, type_, default, sections['alerts'], order, desc, 1 if 'interval' in key else 0))
    
    # Engagement settings
    engagement_settings = [
        ('messages_threshold', 'integer', '10', 'Messages required for Active role', 1),
        ('days_threshold', 'integer', '30', 'Days to look back for activity', 2),
        ('min_active_days', 'integer', '5', 'Minimum days with activity required', 3),
        ('warning_days', 'integer', '7', 'Days before losing Active to send warning', 4),
        ('warning_min_messages', 'integer', '7', 'Messages needed to avoid warning', 5),
        ('dm_warnings', 'boolean', 'true', 'Send warnings via DM', 6),
    ]
    
    for key, type_, default, desc, order in engagement_settings:
        await cursor.execute("""
            INSERT INTO settings_registry (setting_key, setting_type, default_value, section_id, display_order, description)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (key, type_, default, sections['engagement'], order, desc))
    
    # Volatility thresholds
    volatility_settings = [
        ('5m', 'decimal', '2.0', '5 minute volatility threshold (%)', 1),
        ('15m', 'decimal', '3.0', '15 minute volatility threshold (%)', 2),
        ('1h', 'decimal', '5.0', '1 hour volatility threshold (%)', 3),
        ('4h', 'decimal', '10.0', '4 hour volatility threshold (%)', 4),
        ('24h', 'decimal', '20.0', '24 hour volatility threshold (%)', 5),
    ]
    
    for key, type_, default, desc, order in volatility_settings:
        await cursor.execute("""
            INSERT INTO settings_registry (setting_key, setting_type, default_value, section_id, display_order, description, min_value, max_value)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (key, type_, default, sections['volatility'], order, desc, 0.1, 100.0))
    
    # Funding thresholds
    funding_settings = [
        ('threshold_positive', 'decimal', '0.01', 'Positive funding rate threshold', 1),
        ('threshold_negative', 'decimal', '-0.01', 'Negative funding rate threshold', 2),
    ]
    
    for key, type_, default, desc, order in funding_settings:
        await cursor.execute("""
            INSERT INTO settings_registry (setting_key, setting_type, default_value, section_id, display_order, description, min_value, max_value)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (key, type_, default, sections['funding'], order, desc, -1.0, 1.0))
    
    # General settings
    general_settings = [
        ('command_prefix', 'string', '!', 'Command prefix for text commands', 1),
        ('auto_sync_commands', 'boolean', 'true', 'Auto-sync slash commands on startup', 2),
    ]
    
    for key, type_, default, desc, order in general_settings:
        await cursor.execute("""
            INSERT INTO settings_registry (setting_key, setting_type, default_value, section_id, display_order, description)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (key, type_, default, sections['general'], order, desc))
    
    # Populate timezone definitions
    # Using executemany for efficiency
    timezones = [
        # Popular timezones (priority 1)
        ('Pacific/Honolulu', 'Honolulu', 'Hawaii', 'US', 'North America', 1),
        ('America/Los_Angeles', 'Los Angeles', None, 'US', 'North America', 1),
        ('America/Vancouver', 'Vancouver', None, 'CA', 'North America', 1),
        ('America/Phoenix', 'Phoenix', None, 'US', 'North America', 1),
        ('America/Denver', 'Denver', None, 'US', 'North America', 1),
        ('America/Chicago', 'Chicago', None, 'US', 'North America', 1),
        ('America/Mexico_City', 'Mexico City', None, 'MX', 'North America', 1),
        ('America/New_York', 'New York', None, 'US', 'North America', 1),
        ('America/Toronto', 'Toronto', None, 'CA', 'North America', 1),
        ('America/Halifax', 'Halifax', 'PEI', 'CA', 'North America', 1),
        ('Europe/London', 'London', None, 'GB', 'Europe', 1),
        ('Europe/Paris', 'Paris', None, 'FR', 'Europe', 1),
        ('Europe/Berlin', 'Berlin', None, 'DE', 'Europe', 1),
        ('Europe/Madrid', 'Madrid', None, 'ES', 'Europe', 1),
        ('Europe/Rome', 'Rome', None, 'IT', 'Europe', 1),
        ('Europe/Moscow', 'Moscow', None, 'RU', 'Europe', 1),
        ('Asia/Dubai', 'Dubai', None, 'AE', 'Asia', 1),
        ('Asia/Kolkata', 'Mumbai', 'India', 'IN', 'Asia', 1),
        ('Asia/Singapore', 'Singapore', None, 'SG', 'Asia', 1),
        ('Asia/Hong_Kong', 'Hong Kong', None, 'HK', 'Asia', 1),
        ('Asia/Shanghai', 'Shanghai', None, 'CN', 'Asia', 1),
        ('Asia/Seoul', 'Seoul', None, 'KR', 'Asia', 1),
        ('Asia/Tokyo', 'Tokyo', None, 'JP', 'Asia', 1),
        ('Australia/Sydney', 'Sydney', None, 'AU', 'Oceania', 1),
        ('Australia/Brisbane', 'Brisbane', None, 'AU', 'Oceania', 1),
        ('Europe/Istanbul', 'Istanbul', None, 'TR', 'Europe', 1),
        ('Pacific/Auckland', 'Auckland', None, 'NZ', 'Oceania', 1),
    ]
    
    await cursor.executemany("""
        INSERT INTO timezone_definitions (timezone, display_name, custom_name, country_code, region, priority)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE timezone = timezone
    """, timezones)
    
    # Add sample subscription tiers
    tiers = [
        ('free', 'Free', 0, 0, 1, 1, 5, False, False, False, False, True, 10, 'gpt-3.5-turbo', False, False, 3600, 3600, 5, 7),
        ('starter', 'Starter', 9.99, 99, 3, 2, 20, True, True, False, False, True, 100, 'gpt-3.5-turbo', False, False, 600, 1800, 20, 30),
        ('pro', 'Professional', 29.99, 299, 10, 5, 100, True, True, True, True, True, 500, 'gpt-4', False, True, 300, 900, 100, 90),
        ('enterprise', 'Enterprise', 99.99, 999, 999, 999, 999, True, True, True, True, True, 9999, 'gpt-4', True, True, 60, 300, 999, 365),
    ]
    
    for tier in tiers:
        await cursor.execute("""
            INSERT INTO subscription_tiers (
                tier_name, display_name, price_monthly, price_yearly,
                max_timezones, max_alert_channels, max_watchlist_items,
                engagement_enabled, volatility_enabled, funding_enabled, market_events_enabled,
                ai_chat_enabled, ai_chat_messages_per_day, ai_chat_model,
                custom_branding, priority_support,
                volatility_check_interval_min, funding_check_interval_min, max_alerts_per_hour,
                data_retention_days
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, tier)
    
    # Record schema version
    await cursor.execute("""
        INSERT INTO schema_migrations (version, description) 
        VALUES (1, 'Complete normalized schema with subscription support - production ready')
    """)

async def down(cursor):
    """Drop all tables"""
    tables = [
        'user_watchlist',
        'user_alert_preferences',
        'alert_history',
        'guild_usage',
        'guild_subscriptions',
        'member_status',
        'member_activity_daily',
        'timezone_channels',
        'guild_settings',
        'settings_registry',
        'settings_sections',
        'timezone_definitions',
        'audit_log',
        'subscription_tiers',
        'guilds',
        'schema_migrations',
    ]
    
    for table in tables:
        await cursor.execute(f"DROP TABLE IF EXISTS {table}")
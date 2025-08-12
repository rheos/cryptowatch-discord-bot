"""
Populate settings definitions and migrate data from config files
"""

async def up(cursor):
    """Populate settings definitions"""
    
    # Define all available settings
    settings = [
        # Engagement settings
        ('engagement.enabled', 'boolean', 'false', 'Enable automatic role assignment based on activity', 'engagement'),
        ('engagement.messages_threshold', 'integer', '10', 'Messages required for Active role', 'engagement'),
        ('engagement.days_threshold', 'integer', '30', 'Days to track for activity', 'engagement'),
        ('engagement.warning_days', 'integer', '7', 'Days before warning about losing Active role', 'engagement'),
        ('engagement.warning_min_messages', 'integer', '7', 'Minimum messages when warning', 'engagement'),
        ('engagement.dm_warnings', 'boolean', 'true', 'Send warnings via DM', 'engagement'),
        
        # Notification settings
        ('notifications.market_events', 'boolean', 'true', 'Enable market event notifications', 'notifications'),
        ('notifications.funding_alerts', 'boolean', 'true', 'Enable funding rate alerts', 'notifications'),
        ('notifications.maintenance', 'boolean', 'true', 'Enable maintenance notifications', 'notifications'),
        
        # Feature toggles
        ('features.ai_chat', 'boolean', 'true', 'Enable AI chat assistant', 'features'),
        ('features.price_commands', 'boolean', 'true', 'Enable price checking commands', 'features'),
        ('features.volatility_tracking', 'boolean', 'true', 'Enable volatility tracking', 'features'),
        
        # Timezone settings
        ('timezone.update_interval', 'integer', '300', 'Seconds between timezone updates', 'timezone'),
        ('timezone.format_24h', 'boolean', 'false', 'Use 24-hour time format', 'timezone'),
        
        # Permission settings
        ('permissions.admin_role', 'string', 'Administrator', 'Role name for admin commands', 'permissions'),
        ('permissions.moderator_role', 'string', 'Moderator', 'Role name for moderator commands', 'permissions'),
    ]
    
    # Insert settings definitions
    for key, type_, default, desc, category in settings:
        await cursor.execute("""
            INSERT INTO settings_definitions (setting_key, setting_type, default_value, description, category)
            VALUES (%s, %s, %s, %s, %s) AS new_values
            ON DUPLICATE KEY UPDATE
                setting_type = new_values.setting_type,
                default_value = new_values.default_value,
                description = new_values.description,
                category = new_values.category
        """, (key, type_, default, desc, category))

async def down(cursor):
    """Remove settings definitions"""
    await cursor.execute("DELETE FROM settings_definitions")
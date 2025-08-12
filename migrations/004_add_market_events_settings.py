"""
Add market events settings
"""

async def up(cursor):
    """Add market events settings"""
    
    # Add market events settings
    settings = [
        ('market_events.enabled', 'boolean', 'false', 'Enable market events countdown and schedule', 'market_events'),
        ('market_events.pinned_message_id', 'string', '', 'ID of the pinned market schedule message', 'market_events'),
        ('market_events.update_interval', 'integer', '300', 'Seconds between market event updates', 'market_events'),
    ]
    
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
    """Remove market events settings"""
    await cursor.execute("""
        DELETE FROM settings_definitions 
        WHERE setting_key IN (
            'market_events.enabled',
            'market_events.pinned_message_id',
            'market_events.update_interval'
        )
    """)
"""
Seed initial channel configuration from config file

This migration is intentionally empty because:
1. Channel IDs are different for each Discord server
2. The bot will populate the database when it connects
3. Use the !setup command to configure channels for each guild
"""

async def up(cursor):
    """No-op - channels will be configured per guild"""
    pass

async def down(cursor):
    """No-op - preserve any configured channels"""
    pass
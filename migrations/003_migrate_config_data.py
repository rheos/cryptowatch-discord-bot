"""
Migrate existing configuration from JSON files to database
"""
import json
import os
import logging

logger = logging.getLogger('migration.config_data')

async def up(cursor):
    """Migrate config data to new schema"""
    
    # Try to load existing config files
    config_files = ['config.json', 'config.development.json', 'config.production.json']
    config_data = {}
    
    for config_file in config_files:
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), config_file)
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    config_data = json.load(f)
                    logger.info(f"Loaded config from {config_file}")
                    break
            except Exception as e:
                logger.error(f"Error loading {config_file}: {e}")
                continue
    
    if not config_data:
        logger.warning("No config file found, skipping migration")
        return
    
    # Extract guild configurations
    if 'guilds' in config_data:
        for guild_id, guild_config in config_data['guilds'].items():
            # Convert guild_id to int
            guild_id = int(guild_id)
            
            # Insert guild if not exists
            guild_name = guild_config.get('name', f'Guild {guild_id}')
            await cursor.execute("""
                INSERT INTO guilds (guild_id, guild_name)
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE guild_name = VALUES(guild_name)
            """, (guild_id, guild_name))
            
            # Migrate channel configurations
            if 'channels' in guild_config:
                channels = guild_config['channels']
                
                # Text channels
                for channel_type in ['alerts', 'market_events', 'funding']:
                    if channel_type in channels:
                        channel_id = int(channels[channel_type])
                        await cursor.execute("""
                            INSERT INTO guild_channels (guild_id, channel_type, channel_id, settings)
                            VALUES (%s, %s, %s, %s)
                        """, (guild_id, channel_type, channel_id, '{}'))
                
                # Timezone channels (voice channels)
                for key, channel_id in channels.items():
                    if key.startswith('timezone_'):
                        timezone = key.replace('timezone_', '').replace('_', '/')
                        channel_id = int(channel_id)
                        settings = json.dumps({'timezone': timezone})
                        
                        await cursor.execute("""
                            INSERT INTO guild_channels (guild_id, channel_type, channel_subtype, channel_id, settings)
                            VALUES (%s, %s, %s, %s, %s)
                        """, (guild_id, 'timezone', timezone, channel_id, settings))
            
            # Migrate engagement settings
            if 'engagement' in guild_config:
                eng = guild_config['engagement']
                
                # Map old config to new settings
                settings_map = {
                    'enabled': ('engagement.enabled', str(eng.get('enabled', False)).lower()),
                    'active_threshold': ('engagement.messages_threshold', str(eng.get('active_threshold', 10))),
                    'tracking_days': ('engagement.days_threshold', str(eng.get('tracking_days', 30))),
                    'warning_days': ('engagement.warning_days', str(eng.get('warning_days', 7))),
                    'warning_threshold': ('engagement.warning_min_messages', str(eng.get('warning_threshold', 7))),
                    'dm_warnings': ('engagement.dm_warnings', str(eng.get('dm_warnings', True)).lower())
                }
                
                for old_key, (new_key, value) in settings_map.items():
                    if old_key in eng:
                        await cursor.execute("""
                            INSERT INTO guild_settings (guild_id, setting_key, setting_value)
                            VALUES (%s, %s, %s)
                            ON DUPLICATE KEY UPDATE setting_value = VALUES(setting_value)
                        """, (guild_id, new_key, value))
            
            # Migrate feature flags
            if 'features' in guild_config:
                features = guild_config['features']
                feature_map = {
                    'ai_chat': 'features.ai_chat',
                    'price_commands': 'features.price_commands',
                    'volatility': 'features.volatility_tracking'
                }
                
                for old_key, new_key in feature_map.items():
                    if old_key in features:
                        value = str(features[old_key]).lower()
                        await cursor.execute("""
                            INSERT INTO guild_settings (guild_id, setting_key, setting_value)
                            VALUES (%s, %s, %s)
                            ON DUPLICATE KEY UPDATE setting_value = VALUES(setting_value)
                        """, (guild_id, new_key, value))

async def down(cursor):
    """Remove migrated data"""
    # This is a data migration, so we don't remove data on rollback
    pass
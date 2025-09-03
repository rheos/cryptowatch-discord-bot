"""
Migration to add enforce_engagement setting and engagement_log_channel_id
"""

import logging

logger = logging.getLogger('migration')

async def up(pool):
    """Add enforce_engagement setting and engagement_log_channel_id"""
    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                # 1. Add enforce_engagement setting
                await cursor.execute("""
                    SELECT COUNT(*) 
                    FROM settings_registry 
                    WHERE setting_key = 'enforce_engagement'
                """)
                (count,) = await cursor.fetchone()
                
                if count == 0:
                    # Get the Engagement section ID
                    await cursor.execute("""
                        SELECT section_id 
                        FROM settings_sections 
                        WHERE section_key = 'engagement'
                    """)
                    result = await cursor.fetchone()
                    
                    if result:
                        section_id = result[0]
                        
                        # Add enforce_engagement setting
                        await cursor.execute("""
                            INSERT INTO settings_registry (
                                section_id, 
                                setting_key, 
                                setting_type, 
                                default_value, 
                                description, 
                                display_order
                            ) VALUES (
                                %s, 
                                'enforce_engagement', 
                                'boolean', 
                                'false', 
                                'Enforce role removal for inactive members', 
                                10
                            )
                        """, (section_id,))
                        
                        logger.info("✅ Added enforce_engagement setting to registry")
                    else:
                        logger.warning("⚠️ Engagement section not found - setting may need manual creation")
                else:
                    logger.info("ℹ️ enforce_engagement setting already exists")
                
                # 2. Add engagement_log_channel_id setting
                await cursor.execute("""
                    SELECT COUNT(*) 
                    FROM settings_registry 
                    WHERE setting_key = 'engagement_log_channel_id'
                """)
                (count,) = await cursor.fetchone()
                
                if count == 0:
                    # Get the Channels section ID
                    await cursor.execute("""
                        SELECT section_id 
                        FROM settings_sections 
                        WHERE section_key = 'channels'
                    """)
                    result = await cursor.fetchone()
                    
                    if result:
                        channels_section_id = result[0]
                        
                        # Add engagement_log_channel_id setting
                        await cursor.execute("""
                            INSERT INTO settings_registry (
                                section_id, 
                                setting_key, 
                                setting_type, 
                                default_value, 
                                description, 
                                display_order
                            ) VALUES (
                                %s, 
                                'engagement_log_channel_id', 
                                'string', 
                                NULL, 
                                'Channel for engagement activity logs', 
                                8
                            )
                        """, (channels_section_id,))
                        
                        logger.info("✅ Added engagement_log_channel_id setting to registry")
                    else:
                        logger.warning("⚠️ Channels section not found - setting may need manual creation")
                else:
                    logger.info("ℹ️ engagement_log_channel_id setting already exists")
                
                await conn.commit()
                    
    except Exception as e:
        logger.error(f"❌ Failed to add enforce_engagement setting: {e}")
        raise

async def down(pool):
    """Remove enforce_engagement and engagement_log_channel_id settings"""
    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                # Remove the settings from registry
                await cursor.execute("""
                    DELETE FROM settings_registry 
                    WHERE setting_key IN ('enforce_engagement', 'engagement_log_channel_id')
                """)
                
                # Remove any guild-specific values
                await cursor.execute("""
                    DELETE FROM guild_settings 
                    WHERE setting_key IN ('enforce_engagement', 'engagement_log_channel_id')
                """)
                
                await conn.commit()
                logger.info("✅ Removed enforce_engagement and engagement_log_channel_id settings")
                
    except Exception as e:
        logger.error(f"❌ Failed to remove enforce_engagement setting: {e}")
        raise
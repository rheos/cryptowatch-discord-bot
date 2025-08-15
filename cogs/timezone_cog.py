"""
Timezone Cog - Handles timezone channel updates
"""
import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta
from pytz import timezone
import asyncio
import logging

logger = logging.getLogger('discord-bot.timezone')

class TimezoneCog(commands.Cog):
    def __init__(self, bot, config):
        self.bot = bot
        self.config = config
        # Don't use config channels anymore - will get from database
        self.update_timezone_channels.start()
    
    def cog_unload(self):
        self.update_timezone_channels.cancel()
    
    def format_time(self, city_tz):
        """Format time for a specific timezone"""
        now = datetime.now(timezone(city_tz))
        
        # Round to nearest 5-minute interval
        minute = round(now.minute / 5) * 5
        if minute == 60:
            # If rounding up to 60, we need to add an hour
            rounded_time = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        else:
            rounded_time = now.replace(minute=minute, second=0, microsecond=0)
        
        hour = rounded_time.strftime('%-I')
        minute_str = rounded_time.strftime('%M')
        period = rounded_time.strftime('%p').lower()
        
        # Get city name and format it nicely
        city_name = city_tz.split("/")[1].replace("_", " ").title()
        
        # Special replacements
        if city_name == "Halifax":
            city_name = "PEI"
        elif city_name == "Kolkata":
            city_name = "India"
        
        return f"{city_name} {hour}:{minute_str}{period}"
    
    @tasks.loop(minutes=5)  # Run every 5 minutes
    async def update_timezone_channels(self):
        """Update timezone channel names at 5-minute marks"""
        try:
            # Add a small delay to ensure we're past the exact minute mark
            await asyncio.sleep(2)
            
            logger.info("Starting timezone channel updates...")
            updates_made = 0
            updates_attempted = 0
            
            # Collect all channels to update across all guilds
            all_channels_to_update = []
            
            for guild in self.bot.guilds:
                # Check if timezone feature is enabled
                enabled = await self.bot.db.get_setting(guild.id, 'timezone_enabled')
                if not enabled:
                    continue
                
                # Get timezone channels from database using raw SQL
                async with self.bot.db.pool.acquire() as conn:
                    async with conn.cursor() as cursor:
                        await cursor.execute("""
                            SELECT channel_id, timezone, display_name
                            FROM timezone_channels
                            WHERE guild_id = %s
                        """, (guild.id,))
                        
                        channels = await cursor.fetchall()
                        
                        for row in channels:
                            channel_id = row[0]
                            tz_name = row[1]
                            channel = self.bot.get_channel(channel_id)
                            
                            if channel:
                                new_name = self.format_time(tz_name)
                                # Only add to update list if name needs changing
                                if channel.name != new_name:
                                    all_channels_to_update.append({
                                        'channel': channel,
                                        'new_name': new_name,
                                        'tz_name': tz_name
                                    })
                                else:
                                    logger.debug(f"{tz_name} already showing {new_name}, skipping")
                            else:
                                logger.error(f"Channel {channel_id} not found for {tz_name}")
            
            # Now update all channels that need updating
            # Discord allows 2 updates per channel per 10 minutes
            # Since we run every 5 minutes, each channel will only be updated once per run
            for update_info in all_channels_to_update:
                channel = update_info['channel']
                new_name = update_info['new_name']
                tz_name = update_info['tz_name']
                
                try:
                    updates_attempted += 1
                    await channel.edit(name=new_name)
                    logger.info(f"Updated {tz_name} → {new_name}")
                    updates_made += 1
                    
                    # Small delay to avoid hammering the API
                    if len(all_channels_to_update) > 10:
                        await asyncio.sleep(0.5)  # Half second delay for large batches
                        
                except discord.errors.HTTPException as e:
                    if e.status == 429:  # Rate limited
                        logger.warning(f"Rate limited updating {tz_name}, will retry next cycle")
                        # Don't break - other channels might still be updateable
                    else:
                        logger.error(f"HTTP error updating {tz_name}: {e}", exc_info=True)
                except Exception as e:
                    logger.error(f"Unexpected error updating {tz_name}: {e}", exc_info=True)
            
            if updates_made > 0:
                logger.info(f"Updated {updates_made}/{updates_attempted} timezone channels")
            elif len(all_channels_to_update) == 0:
                logger.info("All timezone channels already up to date")
            else:
                logger.warning(f"Failed to update {updates_attempted} channels - check logs for errors")
                
        except Exception as e:
            logger.error(f"Critical error in timezone update loop: {e}", exc_info=True)
    
    @update_timezone_channels.before_loop
    async def before_timezone_update(self):
        """Wait for bot to be ready and sync to 5-minute marks"""
        await self.bot.wait_until_ready()
        
        # Wait until next 5-minute mark for first update
        now = datetime.now()
        minutes_to_wait = 5 - (now.minute % 5)
        if minutes_to_wait == 5:
            minutes_to_wait = 0
        seconds_to_wait = minutes_to_wait * 60 - now.second
        
        if seconds_to_wait > 0:
            logger.info(f"Waiting {seconds_to_wait} seconds until next 5-minute mark for first timezone update...")
            await asyncio.sleep(seconds_to_wait)
        else:
            # We're exactly on a 5-minute mark, wait a couple seconds to avoid conflicts
            await asyncio.sleep(2)

async def setup(bot):
    # This function is called by the bot to load the cog
    pass
"""
Timezone Cog - Handles timezone channel updates
"""
import discord
from discord.ext import commands, tasks
from datetime import datetime
from pytz import timezone
import asyncio
import logging

logger = logging.getLogger('discord-bot.timezone')

class TimezoneCog(commands.Cog):
    def __init__(self, bot, config):
        self.bot = bot
        self.config = config
        self.channels = config.get("timezone_channels", config.get("channels", []))
        self.update_timezone_channels.start()
    
    def cog_unload(self):
        self.update_timezone_channels.cancel()
    
    def format_time(self, city_tz):
        """Format time for a specific timezone"""
        now = datetime.now(timezone(city_tz))
        
        # Round down to last 5-minute interval
        minute = now.minute - (now.minute % 5)
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
    
    @tasks.loop(minutes=5)
    async def update_timezone_channels(self):
        """Update timezone channel names every 5 minutes"""
        try:
            logger.info("Updating timezone channels...")
            updates_made = 0
            
            for entry in self.channels:
                tz_name = entry["timezone"]
                channel_id = entry["channel_id"]
                channel = self.bot.get_channel(channel_id)
                
                if channel:
                    try:
                        new_name = self.format_time(tz_name)
                        current_name = channel.name
                        logger.debug(f"{tz_name}: Current='{current_name}', Expected='{new_name}'")
                        
                        # Only update if the name is different
                        if channel.name != new_name:
                            await channel.edit(name=new_name)
                            logger.info(f"Updated {tz_name} → {new_name}")
                            updates_made += 1
                        else:
                            logger.debug(f"{tz_name} already showing {new_name}, skipping update")
                    except discord.errors.HTTPException as e:
                        if e.status == 429:  # Rate limited
                            logger.warning(f"Rate limited updating {tz_name}, will retry next cycle")
                        else:
                            logger.error(f"HTTP error updating {tz_name}: {e}", exc_info=True)
                    except Exception as e:
                        logger.error(f"Unexpected error updating {tz_name}: {e}", exc_info=True)
                else:
                    logger.error(f"Channel {channel_id} not found for {tz_name}")
            
            if updates_made == 0:
                logger.info("All timezone channels already up to date")
        except Exception as e:
            logger.error(f"Critical error in timezone update loop: {e}", exc_info=True)
    
    @update_timezone_channels.before_loop
    async def before_timezone_update(self):
        """Wait for bot to be ready and do immediate update"""
        await self.bot.wait_until_ready()
        
        # Do an immediate update first
        logger.info("Performing immediate timezone update...")
        await self.update_timezone_channels()
        
        # Then wait until next 5-minute mark
        now = datetime.now()
        minutes_to_wait = 5 - (now.minute % 5)
        if minutes_to_wait == 5:
            minutes_to_wait = 0
        seconds_to_wait = minutes_to_wait * 60 - now.second
        
        if seconds_to_wait > 0:
            logger.info(f"Waiting {seconds_to_wait} seconds until next 5-minute mark...")
            await asyncio.sleep(seconds_to_wait)

async def setup(bot):
    # This function is called by the bot to load the cog
    pass
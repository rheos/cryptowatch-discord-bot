"""
Timezone Cog - Handles timezone channel updates
"""
import discord
from discord.ext import commands, tasks
from datetime import datetime
from pytz import timezone
import logging

logger = logging.getLogger('discord-bot.timezone')

class TimezoneCog(commands.Cog):
    def __init__(self, bot, config):
        self.bot = bot
        self.config = config
        self.channels = config.get("channels", [])
        self.update_timezone_channels.start()
    
    def cog_unload(self):
        self.update_timezone_channels.cancel()
    
    def format_time(self, city_tz):
        """Format time for a specific timezone"""
        now = datetime.now(timezone(city_tz))
        hour = now.strftime('%-I')
        minute = now.strftime('%M')
        period = now.strftime('%p').lower()
        
        # Get city name and format it nicely
        city_name = city_tz.split("/")[1].replace("_", " ").title()
        
        # Special replacements
        if city_name == "Halifax":
            city_name = "PEI"
        
        return f"{city_name} {hour}:{minute}{period}"
    
    @tasks.loop(minutes=5)
    async def update_timezone_channels(self):
        """Update timezone channel names every 5 minutes"""
        logger.info("Updating timezone channels...")
        
        for entry in self.channels:
            tz_name = entry["timezone"]
            channel_id = entry["channel_id"]
            channel = self.bot.get_channel(channel_id)
            
            if channel:
                try:
                    new_name = self.format_time(tz_name)
                    await channel.edit(name=new_name)
                    logger.info(f"Updated {tz_name} → {new_name}")
                except Exception as e:
                    logger.error(f"Error updating {tz_name}: {e}")
            else:
                logger.error(f"Channel {channel_id} not found for {tz_name}")
    
    @update_timezone_channels.before_loop
    async def before_timezone_update(self):
        """Wait for bot to be ready and sync to 5-minute intervals"""
        await self.bot.wait_until_ready()
        
        # Wait until next 5-minute mark
        now = datetime.now()
        minutes_to_wait = 5 - (now.minute % 5)
        if minutes_to_wait == 5:
            minutes_to_wait = 0
        seconds_to_wait = minutes_to_wait * 60 - now.second
        
        logger.info(f"Waiting {seconds_to_wait} seconds until next 5-minute mark...")
        await asyncio.sleep(seconds_to_wait)

async def setup(bot):
    # This function is called by the bot to load the cog
    pass
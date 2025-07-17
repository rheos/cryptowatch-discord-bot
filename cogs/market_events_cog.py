"""
Market Events Cog - Handles market open/close countdowns and schedules
"""
import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta
from pytz import timezone
import logging
import os

logger = logging.getLogger('discord-bot.market-events')

class MarketEventsCog(commands.Cog):
    def __init__(self, bot, config):
        self.bot = bot
        self.config = config
        self.market_event_channel_id = config.get("market_event_channel_id")
        self.market_times_channel_id = config.get("market_times_message_channel_id")
        self.message_id_file = "data/market_message.id"
        
        # Market events configuration
        self.market_events = [
            {"label": "London Open", "hour": 7, "minute": 0},
            {"label": "NY Open", "hour": 13, "minute": 30},
            {"label": "NY Close", "hour": 20, "minute": 0},
            {"label": "Asia Open", "hour": 0, "minute": 0},
            {"label": "Daily Close", "hour": 0, "minute": 0}
        ]
        
        # Start update task
        self.update_market_events.start()
    
    def cog_unload(self):
        self.update_market_events.cancel()
    
    def get_next_market_event(self, now_utc=None):
        """Calculate the next upcoming market event and time remaining"""
        if now_utc is None:
            now_utc = datetime.now(timezone('UTC'))
        
        current_weekday = now_utc.weekday()
        is_weekend = current_weekday >= 5
        
        # Check if any event is happening right now
        for event in self.market_events:
            if is_weekend and event["label"] not in ["Daily Close", "Asia Open"]:
                continue
                
            event_time = now_utc.replace(
                hour=event["hour"], 
                minute=event["minute"], 
                second=0, 
                microsecond=0
            )
            
            time_diff = abs((event_time - now_utc).total_seconds())
            if time_diff < 300:  # Within 5 minutes
                if "Close" in event['label']:
                    if event['label'] == "NY Close":
                        return "🎯 NY Closing Now"
                    else:
                        return "🎯 Daily Closing Now"
                else:
                    label_parts = event['label'].split()
                    if label_parts[-1] == "Open":
                        label_parts[-1] = "Opening Now"
                    else:
                        label_parts.append("Opening Now")
                    return f"🎯 {' '.join(label_parts)}"
        
        # Find next event
        next_event = None
        min_time_diff = float('inf')
        
        for event in self.market_events:
            if is_weekend and event["label"] not in ["Daily Close", "Asia Open"]:
                continue
                
            event_time = now_utc.replace(
                hour=event["hour"], 
                minute=event["minute"], 
                second=0, 
                microsecond=0
            )
            
            if event_time <= now_utc:
                event_time += timedelta(days=1)
                
            if event_time.weekday() >= 5 and event["label"] not in ["Daily Close", "Asia Open"]:
                days_until_monday = 7 - event_time.weekday()
                event_time += timedelta(days=days_until_monday)
            
            time_diff = (event_time - now_utc).total_seconds()
            
            if time_diff < min_time_diff:
                min_time_diff = time_diff
                next_event = (event["label"], event_time)
        
        if next_event:
            label, event_time = next_event
            time_remaining = event_time - now_utc
            
            total_seconds = time_remaining.total_seconds()
            hours = int(total_seconds // 3600)
            minutes = int(round((total_seconds % 3600) / 60))
            
            if minutes == 60:
                hours += 1
                minutes = 0
            
            if hours > 0:
                if minutes > 0:
                    countdown = f"{hours}h {minutes}m"
                else:
                    countdown = f"{hours}h"
            else:
                countdown = f"{minutes}m"
            
            return f"🎯 {label} in {countdown}"
        
        return "🎯 No upcoming events"
    
    def format_market_times_message(self, now_utc=None):
        """Create formatted message showing all market event times"""
        utc_tz = timezone('UTC')
        if now_utc is None:
            now_utc = datetime.now(utc_tz)
        
        current_weekday = now_utc.weekday()
        is_weekend = current_weekday >= 5
        
        # Get current times in major markets
        ny_tz = timezone('America/New_York')
        london_tz = timezone('Europe/London')
        tokyo_tz = timezone('Asia/Tokyo')
        
        now_ny = datetime.now(ny_tz)
        now_london = datetime.now(london_tz)
        now_tokyo = datetime.now(tokyo_tz)
        
        # Create message
        message = "📊 **Market Hours (UTC)**\n"
        message += "━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        # Current times
        message += f"🌍 **Current Time**\n"
        message += f"UTC: {now_utc.strftime('%I:%M %p')}\n"
        message += f"New York: {now_ny.strftime('%I:%M %p')}\n"
        message += f"London: {now_london.strftime('%I:%M %p')}\n"
        message += f"Tokyo: {now_tokyo.strftime('%I:%M %p')}\n\n"
        
        # Market events
        message += "📈 **Today's Schedule**\n"
        
        for event in self.market_events:
            if is_weekend and event["label"] not in ["Daily Close", "Asia Open"]:
                continue
                
            event_utc = now_utc.replace(
                hour=event["hour"], 
                minute=event["minute"], 
                second=0, 
                microsecond=0
            )
            
            if event_utc <= now_utc:
                event_utc += timedelta(days=1)
                
            if event_utc.weekday() >= 5 and event["label"] not in ["Daily Close", "Asia Open"]:
                days_until_monday = 7 - event_utc.weekday()
                event_utc += timedelta(days=days_until_monday)
            
            # Calculate countdown
            time_remaining = event_utc - now_utc
            total_seconds = time_remaining.total_seconds()
            hours = int(total_seconds // 3600)
            minutes = int(round((total_seconds % 3600) / 60))
            
            if minutes == 60:
                hours += 1
                minutes = 0
            
            if hours > 0:
                if minutes > 0:
                    countdown = f"in {hours}h {minutes}m"
                else:
                    countdown = f"in {hours}h"
            else:
                countdown = f"in {minutes}m"
            
            time_str = event_utc.strftime('%I:%M %p')
            message += f"\n**{event['label']}** - {time_str} UTC ({countdown})"
        
        message += "\n\n━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        message += f"_Updated every 5 minutes_"
        
        return message
    
    def load_message_id(self):
        """Load saved message ID from file"""
        try:
            if os.path.exists(self.message_id_file):
                with open(self.message_id_file, "r") as f:
                    return int(f.read().strip())
        except:
            pass
        return None
    
    def save_message_id(self, message_id):
        """Save message ID to file"""
        os.makedirs(os.path.dirname(self.message_id_file), exist_ok=True)
        with open(self.message_id_file, "w") as f:
            f.write(str(message_id))
    
    @tasks.loop(minutes=5)
    async def update_market_events(self):
        """Update market event countdown and pinned message"""
        now_utc = datetime.now(timezone('UTC'))
        
        # Update countdown channel
        if self.market_event_channel_id:
            channel = self.bot.get_channel(self.market_event_channel_id)
            if channel:
                try:
                    new_name = self.get_next_market_event(now_utc)
                    await channel.edit(name=new_name)
                    logger.info(f"Updated market event channel → {new_name}")
                except Exception as e:
                    logger.error(f"Error updating market event channel: {e}")
        
        # Update pinned message
        if self.market_times_channel_id:
            channel = self.bot.get_channel(self.market_times_channel_id)
            if channel:
                try:
                    message_id = self.load_message_id()
                    message_updated = False
                    
                    if message_id:
                        try:
                            message = await channel.fetch_message(message_id)
                            new_content = self.format_market_times_message(now_utc)
                            await message.edit(content=new_content)
                            logger.info("Updated pinned market times message")
                            message_updated = True
                        except discord.NotFound:
                            logger.info("Message not found, will create new one")
                        except discord.Forbidden:
                            logger.info("Cannot edit message, will create new one")
                    
                    if not message_updated:
                        new_content = self.format_market_times_message(now_utc)
                        message = await channel.send(new_content)
                        await message.pin()
                        self.save_message_id(message.id)
                        logger.info(f"Created new pinned message with ID: {message.id}")
                        
                except Exception as e:
                    logger.error(f"Error handling pinned message: {e}")
    
    @update_market_events.before_loop
    async def before_market_update(self):
        """Wait for bot to be ready and sync to 5-minute intervals"""
        await self.bot.wait_until_ready()
        
        now = datetime.now()
        minutes_to_wait = 5 - (now.minute % 5)
        if minutes_to_wait == 5:
            minutes_to_wait = 0
        seconds_to_wait = minutes_to_wait * 60 - now.second
        
        logger.info(f"Waiting {seconds_to_wait} seconds until next 5-minute mark...")
        await asyncio.sleep(seconds_to_wait)

async def setup(bot):
    pass
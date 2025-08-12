"""
Market Events Cog V2 - Database-aware version with per-guild settings
"""
import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta
from pytz import timezone
import asyncio
import logging

logger = logging.getLogger('discord-bot.market-events')

class MarketEventsCog(commands.Cog):
    def __init__(self, bot, config):
        self.bot = bot
        self.config = config
        
        # Market events configuration
        self.market_events = [
            {"label": "London Open", "hour": 7, "minute": 0},
            {"label": "NY Open", "hour": 13, "minute": 30},
            {"label": "NY Close", "hour": 20, "minute": 0},
            {"label": "Asia Open", "hour": 0, "minute": 0},
            {"label": "Daily Close", "hour": 0, "minute": 0}
        ]
        
        # Track if initial update has run to avoid conflicts
        self.initial_update_done = False
        
        # Run initial update on startup
        self.bot.loop.create_task(self.initial_update())
        
        # Start update task
        self.update_market_events.start()
    
    def cog_unload(self):
        self.update_market_events.cancel()
    
    async def initial_update(self):
        """Run initial update immediately when bot starts"""
        await self.bot.wait_until_ready()
        await asyncio.sleep(2)  # Give database time to connect
        
        logger.info("Running initial market events update on startup")
        
        try:
            await self._update_all_guilds()
            self.initial_update_done = True
        except Exception as e:
            logger.error(f"Error in initial update: {e}", exc_info=True)
    
    async def _update_all_guilds(self):
        """Update market events for all guilds"""
        now_utc = datetime.now(timezone('UTC'))
        logger.info(f"Updating market events at {now_utc.strftime('%H:%M:%S UTC')}")
        
        # Process each guild
        for guild in self.bot.guilds:
            try:
                # Check if market events are enabled for this guild
                enabled = await self.bot.db.get_setting(guild.id, 'market_events.enabled')
                logger.debug(f"Market events enabled for {guild.name}: {enabled}")
                if not enabled:
                    continue
                
                # Get configured channels
                channels = await self.bot.db.get_guild_channels(guild.id)
                logger.debug(f"Found {len(channels)} channels configured for {guild.name}")
                
                # Update countdown channel
                market_event_channel = None
                market_times_channel = None
                
                for channel_config in channels:
                    if channel_config['channel_type'] == 'market_events':
                        channel_id = channel_config['channel_id']
                        market_event_channel = guild.get_channel(channel_id)
                        logger.debug(f"Found market_events channel: {market_event_channel}")
                    elif channel_config['channel_type'] == 'market_times':
                        channel_id = channel_config['channel_id']
                        market_times_channel = guild.get_channel(channel_id)
                        logger.debug(f"Found market_times channel: {market_times_channel}")
                
                # Update countdown channel name
                if market_event_channel:
                    logger.info(f"Attempting to update channel name for {guild.name}")
                    try:
                        new_name = self.get_next_market_event(now_utc)
                        if market_event_channel.name != new_name:
                            logger.info(f"Channel name change needed: '{market_event_channel.name}' → '{new_name}'")
                            # Add timeout to prevent hanging
                            await asyncio.wait_for(
                                market_event_channel.edit(name=new_name),
                                timeout=10.0
                            )
                            logger.info(f"Updated market event channel for {guild.name} → {new_name}")
                        else:
                            logger.info(f"Channel name already correct: {new_name}")
                    except asyncio.TimeoutError:
                        logger.error(f"Timeout updating channel name for {guild.name} - Discord API may be slow")
                    except discord.errors.HTTPException as e:
                        if e.status == 429:
                            logger.warning(f"Rate limited updating market event channel for {guild.name}")
                        else:
                            logger.error(f"Error updating market event channel for {guild.name}: {e}")
                    except Exception as e:
                        logger.error(f"Unexpected error updating channel: {e}", exc_info=True)
                
                # Update pinned message (removed lock - not needed for single guild)
                if market_times_channel:
                    logger.info(f"Attempting to update pinned message for {guild.name}")
                    try:
                        logger.info("Getting or creating message...")
                        message = await self.get_or_create_message(guild.id, market_times_channel)
                        logger.info("Formatting new content...")
                        new_content = self.format_market_times_message(now_utc)
                        
                        # Always log for debugging
                        logger.info(f"Checking market times message at {now_utc.strftime('%H:%M:%S')}")
                        
                        # Always update the message to ensure footer time is current
                        await message.edit(content=new_content)
                        logger.info(f"Updated market times message for {guild.name} at {now_utc.strftime('%H:%M:%S')}")
                    except Exception as e:
                        logger.error(f"Error updating market times message for {guild.name}: {e}", exc_info=True)
                        
            except Exception as e:
                logger.error(f"Error processing market events for guild {guild.name}: {e}")
    
    def get_next_market_event(self, now_utc=None):
        """Calculate the next upcoming market event and time remaining"""
        if now_utc is None:
            now_utc = datetime.now(timezone('UTC'))
        
        # Round down to last 5-minute interval for consistent countdown display
        display_minute = (now_utc.minute // 5) * 5
        countdown_base = now_utc.replace(minute=display_minute, second=0, microsecond=0)
        
        current_weekday = now_utc.weekday()
        is_weekend = current_weekday >= 5
        
        # Check if any event is happening right now
        for event in self.market_events:
            if is_weekend and event["label"] not in ["Daily Close", "Asia Open"]:
                continue
                
            event_time = countdown_base.replace(
                hour=event["hour"], 
                minute=event["minute"], 
                second=0, 
                microsecond=0
            )
            
            # Check if event is happening now (within 1 minute window)
            if abs((event_time - countdown_base).total_seconds()) < 60:
                # Use flags for market events
                event_flags = {
                    "London Open": "🇬🇧",
                    "London Close": "🇬🇧",
                    "NY Open": "🇺🇸",
                    "NY Close": "🇺🇸",
                    "Asia Open": "🇯🇵",
                    "Asia Close": "🇯🇵",
                    "Daily Close": "🌍"
                }
                emoji = event_flags.get(event['label'], "📊")
                return f"{emoji} {event['label']} NOW"
        
        # Find next event
        next_event = None
        min_time_until = timedelta(days=7)
        
        for event in self.market_events:
            # Skip weekday-only events on weekends
            if is_weekend and event["label"] not in ["Daily Close", "Asia Open"]:
                continue
                
            event_time = countdown_base.replace(
                hour=event["hour"], 
                minute=event["minute"], 
                second=0, 
                microsecond=0
            )
            
            # If event already passed today, check tomorrow
            if event_time <= countdown_base:
                event_time += timedelta(days=1)
                
                # Adjust for weekend
                if event_time.weekday() >= 5 and event["label"] not in ["Daily Close", "Asia Open"]:
                    days_until_monday = 7 - event_time.weekday()
                    event_time += timedelta(days=days_until_monday)
            
            time_until = event_time - countdown_base
            
            if time_until < min_time_until:
                min_time_until = time_until
                next_event = event
        
        if next_event:
            hours = int(min_time_until.total_seconds() // 3600)
            minutes = int((min_time_until.total_seconds() % 3600) // 60)
            
            if hours > 0:
                countdown = f"{hours}h {minutes}m"
            else:
                countdown = f"{minutes}m"
            
            # Use flags for market events
            event_flags = {
                "London Open": "🇬🇧",
                "London Close": "🇬🇧",
                "NY Open": "🇺🇸",
                "NY Close": "🇺🇸",
                "Asia Open": "🇯🇵",
                "Asia Close": "🇯🇵",
                "Daily Close": "🌍"
            }
            
            emoji = event_flags.get(next_event['label'], "📊")
            return f"{emoji} {next_event['label']} in {countdown}"
        
        return "📊 Market Events"
    
    def format_market_times_message(self, now_utc=None):
        """Format the pinned market times message"""
        if now_utc is None:
            now_utc = datetime.now(timezone('UTC'))
        
        # Round down to last 5-minute interval for display AND countdown calculations
        display_minute = (now_utc.minute // 5) * 5
        display_time = now_utc.replace(minute=display_minute, second=0, microsecond=0)
        
        # Use display_time for ALL countdown calculations to ensure clean intervals
        countdown_base = display_time
        
        # Debug logging
        logger.info(f"Time calculation - now_utc: {now_utc.strftime('%H:%M:%S')}, display_minute: {display_minute}, display_time: {display_time.strftime('%H:%M:%S')}")
        
        # Define time zones for current time display
        timezones = {
            "UTC": timezone('UTC'),
            "New York": timezone('America/New_York'),
            "London": timezone('Europe/London'),
            "Tokyo": timezone('Asia/Tokyo')
        }
        
        # Build message
        message = "📊 **Market Hours** (UTC)\n"
        message += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        # Current Time section - use 5-minute interval
        message += "🌍 **Current Time**\n"
        for tz_name, tz in timezones.items():
            current_time = display_time.astimezone(tz)
            if tz_name == "UTC":
                message += f"{tz_name}: {current_time.strftime('%I:%M %p')}\n"
            else:
                message += f"{tz_name}: {current_time.strftime('%I:%M %p')}\n"
        
        message += "\n"
        
        # Define market sessions
        sessions = [
            {
                "name": "Asia",
                "emoji": "🇯🇵",  # Changed from earth to Japan flag
                "open": 0,
                "close": 8,
                "days": [0, 1, 2, 3, 4]  # Mon-Fri
            },
            {
                "name": "London",
                "emoji": "🇬🇧",
                "open": 7,
                "close": 16,
                "days": [0, 1, 2, 3, 4]
            },
            {
                "name": "NY",
                "emoji": "🇺🇸",
                "open": 13.5,  # 13:30
                "close": 20,
                "days": [0, 1, 2, 3, 4]
            }
        ]
        
        current_weekday = countdown_base.weekday()
        is_weekend = current_weekday >= 5
        
        # Market Sessions
        message += "💹 **Market Sessions**\n"
        
        for session in sessions:
            # Check if session is active
            current_hour = countdown_base.hour + countdown_base.minute / 60
            is_active = (session["open"] <= current_hour < session["close"] and 
                        current_weekday in session["days"])
            
            # Format times
            open_hour = int(session["open"])
            open_min = int((session["open"] % 1) * 60)
            close_hour = int(session["close"])
            close_min = int((session["close"] % 1) * 60)
            
            open_time = f"{open_hour:02d}:{open_min:02d}"
            close_time = f"{close_hour:02d}:{close_min:02d}"
            
            # Build line
            if is_active:
                status = "🟢 **OPEN**"
                line = f"**{session['emoji']} {session['name']}: {open_time} - {close_time} {status}**"
            else:
                status = "⚫ Closed"
                line = f"{session['emoji']} {session['name']}: {open_time} - {close_time} {status}"
            
            message += line + "\n"
        
        message += "\n"
        
        # Today's Schedule with countdowns
        message += "📅 **Today's Schedule**\n\n"
        
        for event in self.market_events:
            event_hour = event["hour"]
            event_min = event["minute"]
            event_label = event["label"]
            
            # Format event time
            event_time_str = f"{event_hour:02d}:{event_min:02d} UTC"
            
            # Daily Close is always active (24-hour cycle)
            if event_label == "Daily Close":
                # Calculate time until daily close
                daily_close_time = countdown_base.replace(hour=0, minute=0, second=0, microsecond=0)
                if countdown_base.hour >= 0:  # After midnight
                    daily_close_time += timedelta(days=1)
                
                time_until = daily_close_time - countdown_base
                hours = int(time_until.total_seconds() // 3600)
                minutes = int((time_until.total_seconds() % 3600) // 60)
                
                if hours > 0:
                    countdown = f"(in {hours}h {minutes}m)"
                else:
                    countdown = f"(in {minutes}m)"
                
                message += f"**{event_label}** - {event_time_str} {countdown}\n"
                continue
            
            # Skip weekday-only events on weekends
            if is_weekend and event_label not in ["Asia Open"]:
                message += f"{event_label} - {event_time_str} (Weekend - Closed)\n"
                continue
            
            # Calculate next occurrence of the event
            event_time = countdown_base.replace(hour=event_hour, minute=event_min, second=0, microsecond=0)
            
            # If event already passed today, calculate next occurrence
            if event_time <= countdown_base:
                # Only cross out if it happened within last 3 hours
                hours_since = (countdown_base - event_time).total_seconds() / 3600
                
                if hours_since < 3:
                    # Recently passed - show as crossed out
                    message += f"~~{event_label} - {event_time_str}~~ ✓\n"
                else:
                    # Calculate next occurrence
                    next_event_time = event_time + timedelta(days=1)
                    
                    # Adjust for weekend if needed
                    while next_event_time.weekday() >= 5 and event_label not in ["Asia Open"]:
                        next_event_time += timedelta(days=1)
                    
                    time_until = next_event_time - countdown_base
                    hours = int(time_until.total_seconds() // 3600)
                    minutes = int((time_until.total_seconds() % 3600) // 60)
                    
                    if hours >= 24:
                        days = hours // 24
                        hours = hours % 24
                        countdown = f"(in {days}d {hours}h)"
                    elif hours > 0:
                        countdown = f"(in {hours}h {minutes}m)"
                    else:
                        countdown = f"(in {minutes}m)"
                    
                    message += f"**{event_label}** - {event_time_str} {countdown}\n"
            else:
                # Event is later today
                time_until = event_time - countdown_base
                hours = int(time_until.total_seconds() // 3600)
                minutes = int((time_until.total_seconds() % 3600) // 60)
                
                if hours > 0:
                    countdown = f"(in {hours}h {minutes}m)"
                else:
                    countdown = f"(in {minutes}m)"
                
                message += f"**{event_label}** - {event_time_str} {countdown}\n"
        
        message += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        
        # Footer - show the rounded update time for consistency
        message += f"*Updated every 5 minutes* ({display_time.strftime('%H:%M UTC')})"
        
        return message
    
    async def get_or_create_message(self, guild_id: int, channel: discord.TextChannel):
        """Get existing message or create new one"""
        # Try to get stored message ID - ALWAYS fetch fresh from DB
        message_id_str = await self.bot.db.get_setting(guild_id, 'market_events.pinned_message_id')
        logger.info(f"Retrieved stored message ID from database: '{message_id_str}' (type: {type(message_id_str)}) for guild {guild_id}")
        
        if message_id_str and message_id_str != '':  # Check for empty string too
            try:
                message_id = int(message_id_str)
                logger.info(f"Looking for existing message ID: {message_id} in channel {channel.name} ({channel.id})")
                message = await channel.fetch_message(message_id)
                logger.info(f"Found existing message {message.id}, will edit it")
                return message
            except (ValueError, discord.NotFound, discord.HTTPException) as e:
                # Message doesn't exist, we need to clear and recreate
                logger.error(f"Stored message {message_id_str} not found: {type(e).__name__}: {e}")
                logger.info(f"Message deleted, will create a new one")
                # Don't try to clear here - just fall through to create new
                pass
        
        # Create new message
        content = self.format_market_times_message()
        message = await channel.send(content)
        
        # Try to pin it
        try:
            await message.pin()
            logger.info(f"Created and pinned new market times message in {channel.name}")
        except discord.HTTPException:
            logger.warning(f"Could not pin market times message in {channel.name}")
        
        # Store the new message ID - this should overwrite any old value
        await self.bot.db.set_setting(guild_id, 'market_events.pinned_message_id', str(message.id))
        logger.info(f"Stored new message ID: {message.id}")
        
        # Force a small delay to ensure database write completes
        await asyncio.sleep(0.2)
        
        # Verify it was stored correctly
        verify_id = await self.bot.db.get_setting(guild_id, 'market_events.pinned_message_id')
        logger.info(f"Verification: stored ID {message.id}, retrieved ID {verify_id}")
        
        return message
    
    @tasks.loop(seconds=60)  # Check every minute
    async def update_market_events(self):
        """Update market event countdown and pinned message for all guilds"""
        now_utc = datetime.now(timezone('UTC'))
        
        # Only run on 5-minute intervals
        if now_utc.minute % 5 != 0:
            return
        
        # Skip if initial update just ran (within 10 seconds)
        if not self.initial_update_done:
            logger.info("Skipping scheduled update - initial update in progress")
            return
        
        # Use shared update logic
        await self._update_all_guilds()
    
    @update_market_events.before_loop
    async def before_update_market_events(self):
        """Wait until bot is ready and sync to minute boundaries"""
        await self.bot.wait_until_ready()
        
        # Calculate seconds until next minute
        now = datetime.now(timezone('UTC'))
        seconds = now.second
        
        # Wait until next minute boundary
        if seconds > 0:
            seconds_to_wait = 60 - seconds
            logger.info(f"Waiting {seconds_to_wait} seconds to sync with minute boundaries (current time: {now.strftime('%H:%M:%S')})")
            await asyncio.sleep(seconds_to_wait)
        
        logger.info(f"Market events update loop started at {datetime.now(timezone('UTC')).strftime('%H:%M:%S UTC')}")

async def setup(bot):
    # Pass the bot and config to the cog
    await bot.add_cog(MarketEventsCog(bot, bot.config))
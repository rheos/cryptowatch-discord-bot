import json
import discord
from discord.ext import tasks
from datetime import datetime, timedelta
from pytz import timezone
import asyncio
import logging
from logging.handlers import RotatingFileHandler

# Set up logging
logger = logging.getLogger('discord-timezone-bot')
logger.setLevel(logging.INFO)

# Create rotating file handler (max 10MB, keep 5 backups)
handler = RotatingFileHandler(
    'bot.log',
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5
)
handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)

# Also suppress discord.py's verbose logging
discord_logger = logging.getLogger('discord')
discord_logger.setLevel(logging.WARNING)

# Load configuration from JSON
with open("config.json", "r") as f:
    config = json.load(f)

TOKEN = config["bot_token"]
CHANNELS = config["channels"]
MARKET_EVENT_CHANNEL_ID = config.get("market_event_channel_id")
MARKET_TIMES_MESSAGE_CHANNEL_ID = config.get("market_times_message_channel_id")
MARKET_TIMES_MESSAGE_ID = config.get("market_times_message_id")

# Market events configuration
MARKET_EVENTS = [
    {"label": "London Open", "hour": 7, "minute": 0},
    {"label": "US Open", "hour": 13, "minute": 30},
    {"label": "NYSE Close", "hour": 20, "minute": 0},
    {"label": "Asia Open", "hour": 0, "minute": 0},
    {"label": "Daily Close", "hour": 0, "minute": 0}
]

# Create intents with guilds and members enabled
intents = discord.Intents.default()
intents.guilds = True
intents.members = True  # Need this to track member joins
client = discord.Client(intents=intents)

def format_time(city_tz):
    now = datetime.now(timezone(city_tz))
    hour = now.strftime('%-I')  # Use '%#I' on Windows if needed
    minute = now.strftime('%M')
    period = now.strftime('%p').lower()
    
    # Get city name and format it nicely
    city_name = city_tz.split("/")[1].replace("_", " ")
    
    # Properly capitalize city names
    city_name = city_name.title()
    
    # Replace Halifax with PEI
    if city_name == "Halifax":
        city_name = "PEI"
    
    # Format like "Tokyo 12:45pm" with actual spaces
    return f"{city_name} {hour}:{minute}{period}"

def get_next_market_event():
    """Calculate the next upcoming market event and time remaining"""
    now_utc = datetime.now(timezone('UTC'))
    current_time = now_utc.time()
    current_weekday = now_utc.weekday()  # 0 = Monday, 6 = Sunday
    
    # Skip weekends for stock market events
    is_weekend = current_weekday >= 5
    
    next_event = None
    min_time_diff = float('inf')
    
    for event in MARKET_EVENTS:
        # Skip stock market events on weekends (but keep crypto events like Daily Close)
        if is_weekend and event["label"] not in ["Daily Close", "Asia Open"]:
            continue
            
        event_time = datetime.now(timezone('UTC')).replace(
            hour=event["hour"], 
            minute=event["minute"], 
            second=0, 
            microsecond=0
        )
        
        # If event already passed today, schedule for tomorrow
        if event_time <= now_utc:
            event_time += timedelta(days=1)
            
        # For weekend stock market events, skip to Monday
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
        
        # Format the countdown
        hours = int(time_remaining.total_seconds() // 3600)
        minutes = int((time_remaining.total_seconds() % 3600) // 60)
        
        if hours > 0:
            countdown = f"{hours}h {minutes}m"
        else:
            countdown = f"{minutes}m"
        
        return f"🎯 {label} in {countdown}"
    
    return "🎯 No upcoming events"

def format_market_times_message():
    """Create a formatted message showing all market event times in major timezones"""
    utc_tz = timezone('UTC')
    ny_tz = timezone('America/New_York')
    london_tz = timezone('Europe/London')
    tokyo_tz = timezone('Asia/Tokyo')
    
    now_utc = datetime.now(utc_tz)
    current_weekday = now_utc.weekday()
    is_weekend = current_weekday >= 5
    
    # Create header
    message = "📊 **Market Hours Reference**\n"
    message += "━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    
    # Add current times
    message += "🌍 **Current Time**\n"
    message += f"• UTC: {now_utc.strftime('%I:%M %p')}\n"
    message += f"• New York: {now_utc.astimezone(ny_tz).strftime('%I:%M %p')}\n"
    message += f"• London: {now_utc.astimezone(london_tz).strftime('%I:%M %p')}\n"
    message += f"• Tokyo: {now_utc.astimezone(tokyo_tz).strftime('%I:%M %p')}\n\n"
    
    # Add market events with countdowns
    message += "📈 **Market Events (Daily)**\n"
    
    for event in MARKET_EVENTS:
        # Skip stock market events on weekends (but keep crypto events)
        if is_weekend and event["label"] not in ["Daily Close", "Asia Open"]:
            continue
            
        # Create event time in UTC for today
        event_utc = now_utc.replace(hour=event["hour"], minute=event["minute"], second=0, microsecond=0)
        
        # If event already passed today, schedule for tomorrow
        if event_utc <= now_utc:
            event_utc += timedelta(days=1)
            
        # For weekend stock market events, skip to Monday
        if event_utc.weekday() >= 5 and event["label"] not in ["Daily Close", "Asia Open"]:
            days_until_monday = 7 - event_utc.weekday()
            event_utc += timedelta(days=days_until_monday)
        
        # Calculate countdown
        time_remaining = event_utc - now_utc
        hours = int(time_remaining.total_seconds() // 3600)
        minutes = int((time_remaining.total_seconds() % 3600) // 60)
        
        if hours > 0:
            countdown = f" ⏱️ **{hours}h {minutes}m**"
        else:
            countdown = f" ⏱️ **{minutes}m**"
        
        # Convert to other timezones
        event_ny = event_utc.astimezone(ny_tz)
        event_london = event_utc.astimezone(london_tz)
        event_tokyo = event_utc.astimezone(tokyo_tz)
        
        message += f"\n**{event['label']}**{countdown}\n"
        message += f"• UTC: {event_utc.strftime('%I:%M %p')}\n"
        message += f"• NY: {event_ny.strftime('%I:%M %p')}\n"
        message += f"• London: {event_london.strftime('%I:%M %p')}\n"
        message += f"• Tokyo: {event_tokyo.strftime('%I:%M %p')}\n"
    
    # Add footer
    message += "\n━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    message += f"_Last updated: {now_utc.strftime('%Y-%m-%d %H:%M UTC')}_"
    
    return message

@client.event
async def on_ready():
    logger.info(f"Logged in as {client.user}")
    # Wait until the next 5-minute mark before starting
    now = datetime.now()
    minutes_to_wait = 5 - (now.minute % 5)
    if minutes_to_wait == 5:
        minutes_to_wait = 0
    seconds_to_wait = minutes_to_wait * 60 - now.second
    
    logger.info(f"Waiting {seconds_to_wait} seconds until next 5-minute mark...")
    await asyncio.sleep(seconds_to_wait)
    
    update_channel_names.start()

@client.event
async def on_member_join(member):
    # Configure the role name to assign
    ROLE_NAME = "Member"  # Change this to your role name
    
    try:
        # Find the role by name
        role = discord.utils.get(member.guild.roles, name=ROLE_NAME)
        
        if role:
            # Assign the role to the new member
            await member.add_roles(role)
            logger.info(f"Assigned {ROLE_NAME} role to new member: {member.name} in {member.guild.name}")
        else:
            logger.warning(f"Role '{ROLE_NAME}' not found in {member.guild.name}")
            
    except Exception as e:
        logger.error(f"Error assigning role to {member.name}: {e}")

@tasks.loop(minutes=5)
async def update_channel_names():
    # Update timezone channels
    for entry in CHANNELS:
        tz_name = entry["timezone"]
        channel_id = entry["channel_id"]
        channel = client.get_channel(channel_id)
        if channel:
            try:
                new_name = format_time(tz_name)
                logger.info(f"Attempting to update channel {channel.name} (ID: {channel_id}) in guild {channel.guild.name}")
                await channel.edit(name=new_name)
                logger.info(f"Updated {tz_name} → {new_name}")
            except Exception as e:
                logger.error(f"Error updating {tz_name}: {e}")
                logger.error(f"Channel type: {type(channel).__name__}, Guild: {channel.guild.name if channel else 'None'}")
        else:
            logger.error(f"Channel {channel_id} not found for {tz_name}")
    
    # Update market event countdown channel
    if MARKET_EVENT_CHANNEL_ID:
        channel = client.get_channel(MARKET_EVENT_CHANNEL_ID)
        if channel:
            try:
                new_name = get_next_market_event()
                await channel.edit(name=new_name)
                logger.info(f"Updated market event channel → {new_name}")
            except Exception as e:
                logger.error(f"Error updating market event channel: {e}")
        else:
            logger.error(f"Market event channel {MARKET_EVENT_CHANNEL_ID} not found")
    
    # Update pinned market times message
    if MARKET_TIMES_MESSAGE_CHANNEL_ID and MARKET_TIMES_MESSAGE_ID:
        try:
            channel = client.get_channel(MARKET_TIMES_MESSAGE_CHANNEL_ID)
            if channel:
                message = await channel.fetch_message(MARKET_TIMES_MESSAGE_ID)
                if message:
                    new_content = format_market_times_message()
                    await message.edit(content=new_content)
                    logger.info("Updated pinned market times message")
                else:
                    logger.error(f"Message {MARKET_TIMES_MESSAGE_ID} not found")
            else:
                logger.error(f"Channel {MARKET_TIMES_MESSAGE_CHANNEL_ID} not found")
        except Exception as e:
            logger.error(f"Error updating pinned message: {e}")

client.run(TOKEN)

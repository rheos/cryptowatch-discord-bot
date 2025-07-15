import json
import discord
from discord.ext import tasks
from datetime import datetime
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

client.run(TOKEN)

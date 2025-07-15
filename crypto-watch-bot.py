import json
import discord
from discord.ext import tasks
from datetime import datetime
from pytz import timezone
import asyncio

# Load configuration from JSON
with open("config.json", "r") as f:
    config = json.load(f)

TOKEN = config["bot_token"]
CHANNELS = config["channels"]

client = discord.Client(intents=discord.Intents.default())

def format_time(city_tz):
    now = datetime.now(timezone(city_tz))
    hour = now.strftime('%-I')  # Use '%#I' on Windows if needed
    minute = now.strftime('%M')
    period = now.strftime('%p').lower()
    
    # Get city name and format it nicely
    city_name = city_tz.split("/")[1].replace("_", " ")
    if city_name.lower() == "halifax":
        city_name = "PEI"  # Show PEI instead of Halifax
    
    # Format like "Tokyo 12:35am" with actual spaces
    return f"{city_name} {hour}:{minute}{period}"

@client.event
async def on_ready():
    print(f"Logged in as {client.user}")
    # Wait until the next 5-minute mark before starting
    now = datetime.now()
    minutes_to_wait = 5 - (now.minute % 5)
    if minutes_to_wait == 5:
        minutes_to_wait = 0
    seconds_to_wait = minutes_to_wait * 60 - now.second
    
    print(f"Waiting {seconds_to_wait} seconds until next 5-minute mark...")
    await asyncio.sleep(seconds_to_wait)
    
    update_channel_names.start()

@tasks.loop(minutes=5)
async def update_channel_names():
    for entry in CHANNELS:
        tz_name = entry["timezone"]
        channel_id = entry["channel_id"]
        channel = client.get_channel(channel_id)
        if channel:
            try:
                new_name = format_time(tz_name)
                await channel.edit(name=new_name)
                print(f"Updated {tz_name} → {new_name}")
            except Exception as e:
                print(f"Error updating {tz_name}: {e}")

client.run(TOKEN)

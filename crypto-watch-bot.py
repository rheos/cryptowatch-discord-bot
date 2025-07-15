import json
import discord
from discord.ext import tasks
from datetime import datetime
from pytz import timezone

# Load configuration from JSON
with open("config.json", "r") as f:
    config = json.load(f)

TOKEN = config["bot_token"]
CHANNELS = config["channels"]

client = discord.Client(intents=discord.Intents.default())

def format_time(city_tz):
    now = datetime.now(timezone(city_tz))
    hour = now.strftime('%-I').lower()  # Use '%#I' on Windows if needed
    minute = now.strftime('%M')
    period = now.strftime('%p').lower()
    city_name = city_tz.split("/")[1].lower()
    
    # Create a Discord-friendly channel name (lowercase, no spaces)
    return f"🕒{city_name}-{hour}{minute}{period}"

@client.event
async def on_ready():
    print(f"Logged in as {client.user}")
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

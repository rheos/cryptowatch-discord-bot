#!/usr/bin/env python3
import json
import discord
from datetime import datetime
from pytz import timezone
import asyncio
import sys

# Load configuration from JSON
with open("config.json", "r") as f:
    config = json.load(f)

TOKEN = config["bot_token"]
CHANNELS = config["channels"]

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

async def update_channels():
    # Create client with minimal intents
    intents = discord.Intents.default()
    client = discord.Client(intents=intents)
    
    @client.event
    async def on_ready():
        print(f"Connected as {client.user}")
        
        # Update all channels
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
        
        # Disconnect after updating
        await client.close()
    
    # Run the client
    await client.start(TOKEN)

# Run the update
if __name__ == "__main__":
    asyncio.run(update_channels())
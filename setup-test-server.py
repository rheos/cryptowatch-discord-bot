"""
Helper script to get channel IDs from your test Discord server
Run this after creating your test server and channels
"""
import discord
import json
import asyncio

# You'll run this with your bot token
TOKEN = input("Enter your bot token: ")

intents = discord.Intents.default()
intents.guilds = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f"\nBot connected as {client.user}")
    print("\nAvailable servers:")
    
    for i, guild in enumerate(client.guilds):
        print(f"{i+1}. {guild.name} (ID: {guild.id})")
    
    # Get test server
    server_choice = int(input("\nSelect test server number: ")) - 1
    test_guild = client.guilds[server_choice]
    
    print(f"\nChannels in {test_guild.name}:")
    
    # Categorize channels
    voice_channels = []
    text_channels = []
    
    for channel in test_guild.channels:
        if isinstance(channel, discord.VoiceChannel):
            voice_channels.append(channel)
            print(f"  🔊 {channel.name} (Voice) - ID: {channel.id}")
        elif isinstance(channel, discord.TextChannel):
            text_channels.append(channel)
            print(f"  💬 {channel.name} (Text) - ID: {channel.id}")
    
    # Generate config
    print("\n" + "="*50)
    print("GENERATED CONFIG FOR config.test.json:")
    print("="*50)
    
    config = {
        "bot_token": TOKEN,
        "test_guild_name": test_guild.name,
        "test_guild_id": test_guild.id,
        "channels": [],
        "market_event_channel_id": None,
        "market_times_message_channel_id": None,
        "auto_update_channels": {
            "funding": None,
            "alerts": None
        }
    }
    
    # Match timezone channels
    timezone_keywords = {
        "vancouver": "America/Vancouver",
        "pei": "America/Halifax",
        "halifax": "America/Halifax",
        "istanbul": "Europe/Istanbul",
        "brisbane": "Australia/Brisbane"
    }
    
    for channel in voice_channels:
        name_lower = channel.name.lower()
        for keyword, timezone in timezone_keywords.items():
            if keyword in name_lower:
                config["channels"].append({
                    "timezone": timezone,
                    "channel_id": channel.id
                })
                break
    
    # Match special channels
    for channel in voice_channels:
        name_lower = channel.name.lower()
        if "market" in name_lower or "event" in name_lower:
            config["market_event_channel_id"] = channel.id
    
    for channel in text_channels:
        name_lower = channel.name.lower()
        if "market" in name_lower and "time" in name_lower:
            config["market_times_message_channel_id"] = channel.id
        elif "funding" in name_lower and "update" in name_lower:
            config["auto_update_channels"]["funding"] = channel.id
        elif "alert" in name_lower:
            config["auto_update_channels"]["alerts"] = channel.id
    
    # Save config
    with open("config.test.json", "w") as f:
        json.dump(config, f, indent=2)
    
    print("\n✅ Config saved to config.test.json")
    print("\nNext steps:")
    print("1. Review config.test.json and adjust if needed")
    print("2. Run: ./switch-env.sh test")
    print("3. Start bot: ./start-bot-new.sh")
    
    await client.close()

client.run(TOKEN)
"""
CryptoWatch Discord Bot - Main Entry Point
Combines timezone updates, market events, and crypto data
"""
import discord
from discord.ext import commands
import json
import logging
from logging.handlers import RotatingFileHandler
import asyncio
import os
import sys

# Import cogs
from cogs.timezone_cog import TimezoneCog
from cogs.market_events_cog import MarketEventsCog
from cogs.crypto_data_cog import CryptoDataCog

# Set up logging
def setup_logging():
    logger = logging.getLogger('discord-bot')
    logger.setLevel(logging.INFO)
    
    # Rotating file handler
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
    
    return logger

# Load configuration
def load_config():
    with open("config.json", "r") as f:
        return json.load(f)

class CryptoWatchBot(commands.Bot):
    def __init__(self, config):
        # Set up intents
        intents = discord.Intents.default()
        intents.guilds = True
        intents.message_content = True  # For crypto commands
        
        super().__init__(
            command_prefix='!',
            intents=intents,
            description="CryptoWatch Bot - Timezones, Market Events & Crypto Data"
        )
        
        self.config = config
        self.logger = logging.getLogger('discord-bot')
    
    async def setup_hook(self):
        """Load all cogs during setup"""
        # Initialize cogs with config
        await self.add_cog(TimezoneCog(self, self.config))
        await self.add_cog(MarketEventsCog(self, self.config))
        await self.add_cog(CryptoDataCog(self, self.config))
        
        self.logger.info("All cogs loaded successfully")
    
    async def on_ready(self):
        """Bot is ready and connected"""
        self.logger.info(f"Logged in as {self.user} (ID: {self.user.id})")
        self.logger.info(f"Connected to {len(self.guilds)} guild(s)")
        
        # Set bot status
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="crypto markets | !help"
            )
        )

def write_pid():
    """Write process ID to file for management scripts"""
    with open('bot.pid', 'w') as f:
        f.write(str(os.getpid()))

async def main():
    """Main entry point"""
    # Setup
    logger = setup_logging()
    config = load_config()
    write_pid()
    
    # Create and run bot
    bot = CryptoWatchBot(config)
    
    try:
        await bot.start(config["bot_token"])
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot crashed: {e}")
    finally:
        await bot.close()

if __name__ == "__main__":
    asyncio.run(main())
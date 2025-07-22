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
from cogs.auto_updates_cog import AutoUpdatesCog
from cogs.volatility_cog import VolatilityCog
from cogs.engagement_cog import EngagementCog

# Set up logging
def setup_logging():
    # Ensure logs directory exists
    os.makedirs('logs', exist_ok=True)
    
    # Main bot logger
    logger = logging.getLogger('discord-bot')
    logger.setLevel(logging.INFO)
    
    # Main bot log file
    handler = RotatingFileHandler(
        'logs/bot.log',
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(handler)
    
    # Console handler for immediate feedback
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(console_handler)
    
    # Set up separate loggers for each cog with their own files
    cog_loggers = ['timezone', 'market-events', 'crypto', 'auto-updates', 'engagement']
    for cog_name in cog_loggers:
        cog_logger = logging.getLogger(f'discord-bot.{cog_name}')
        cog_logger.setLevel(logging.DEBUG)  # More verbose for debugging
        
        # Individual file for each cog
        cog_handler = RotatingFileHandler(
            f'logs/{cog_name}.log',
            maxBytes=5*1024*1024,  # 5MB per cog
            backupCount=3
        )
        cog_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        cog_logger.addHandler(cog_handler)
        
        # Also add to main console
        cog_logger.addHandler(console_handler)
    
    # Error-only log file
    error_handler = RotatingFileHandler(
        'logs/errors.log',
        maxBytes=5*1024*1024,
        backupCount=5
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s\n%(exc_info)s'))
    logging.getLogger().addHandler(error_handler)
    
    # Suppress discord.py's verbose logging
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
        intents.members = True  # For member events (privileged)
        intents.presences = True  # For presence updates (privileged)
        
        super().__init__(
            command_prefix='!',
            intents=intents,
            description="CryptoWatch Bot - Timezones, Market Events & Crypto Data",
            help_command=None  # Disable default help
        )
        
        self.config = config
        self.logger = logging.getLogger('discord-bot')
    
    async def setup_hook(self):
        """Load all cogs during setup"""
        # Initialize cogs with config
        await self.add_cog(TimezoneCog(self, self.config))
        await self.add_cog(MarketEventsCog(self, self.config))
        await self.add_cog(CryptoDataCog(self, self.config))
        await self.add_cog(AutoUpdatesCog(self, self.config))
        await self.add_cog(VolatilityCog(self, self.config))
        await self.add_cog(EngagementCog(self, self.config))
        
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
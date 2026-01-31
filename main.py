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

# Load environment variables from .env file if it exists
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # dotenv not installed, assume environment is already configured
    pass

# Import database
from database import BotDatabase
import json

# Import cogs
from cogs.timezone_cog import TimezoneCog
from cogs.market_events_cog import MarketEventsCog
from cogs.market_display_cog import MarketDisplayCog
from cogs.crypto_data_cog import CryptoDataCog
from cogs.auto_updates_cog import AutoUpdatesCog
from cogs.volatility_cog import VolatilityCog
from cogs.engagement_cog import EngagementCog
from cogs.ai_chat_cog import AIChatCog
# from cogs.setup_cog import SetupCog  # Removed - using slash commands only
# Slash commands imported dynamically in setup_hook

# Set up logging
def setup_logging():
    # Ensure logs directory exists
    os.makedirs('logs', exist_ok=True)
    
    # Console handler for immediate feedback (startup/shutdown messages)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    
    # Set up separate loggers for each cog with their own files
    cog_loggers = ['timezone', 'market-events', 'crypto', 'auto-updates', 'engagement', 'ai_chat', 'crypto_commands', 'slash_commands', 'market_display', 'volatility']
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
        
        # Also add console handler for debugging certain cogs
        if cog_name in ['crypto_commands', 'slash_commands', 'market_display']:
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
    
    # Create a simple logger for startup/shutdown messages
    startup_logger = logging.getLogger('startup')
    startup_logger.setLevel(logging.INFO)
    startup_logger.addHandler(console_handler)
    
    return startup_logger

# Import config loader
from config_loader import load_config

class CryptoWatchBot(commands.Bot):
    def __init__(self, config):
        # Set up intents
        intents = discord.Intents.default()
        intents.guilds = True
        intents.message_content = True  # For crypto commands
        intents.members = True  # For member events (privileged)
        intents.presences = True  # For presence updates (privileged)
        
        super().__init__(
            command_prefix=commands.when_mentioned,  # Only respond to @mentions, effectively disabling ! commands
            intents=intents,
            description="CryptoWatch Bot - Timezones, Market Events & Crypto Data",
            help_command=None  # Disable default help
        )
        
        self.config = config
        self.logger = logging.getLogger('startup')
        self.db = BotDatabase(config)
    
    async def setup_hook(self):
        """Load all cogs during setup"""
        # Connect to database and run migrations
        self.logger.info("Connecting to database...")
        await self.db.connect()
        self.logger.info("Database connected and migrations completed")
        
        # Initialize cogs with config
        # await self.add_cog(SetupCog(self, self.config))  # Removed - using slash commands only
        await self.add_cog(TimezoneCog(self, self.config))
        await self.add_cog(MarketEventsCog(self, self.config))
        await self.add_cog(MarketDisplayCog(self, self.config))
        await self.add_cog(CryptoDataCog(self, self.config))
        
        # Load AutoUpdatesCog with error handling
        try:
            await self.add_cog(AutoUpdatesCog(self, self.config))
            self.logger.info("AutoUpdatesCog loaded successfully")
        except Exception as e:
            self.logger.error(f"Failed to load AutoUpdatesCog: {e}", exc_info=True)
        
        try:
            await self.add_cog(VolatilityCog(self, self.config))
            self.logger.info("VolatilityCog loaded successfully")
        except Exception as e:
            self.logger.error(f"Failed to load VolatilityCog: {e}", exc_info=True)
        await self.add_cog(EngagementCog(self, self.config))
        await self.add_cog(AIChatCog(self, self.config))

        # Load TradingView signals cog
        try:
            from cogs.tradingview_signals_cog import TradingViewSignalsCog
            await self.add_cog(TradingViewSignalsCog(self))
            self.logger.info("TradingViewSignalsCog loaded successfully")
        except Exception as e:
            self.logger.error(f"Failed to load TradingViewSignalsCog: {e}", exc_info=True)
        # Load modular slash commands
        from cogs.slash_commands import CryptoCommands, UserCommands
        from cogs.slash_commands.admin_commands import AdminCommands
        from cogs.slash_commands.setup_commands import SetupCommands
        from cogs.slash_commands.market_display_commands import MarketDisplayCommands
        await self.add_cog(CryptoCommands(self))
        await self.add_cog(UserCommands(self))
        await self.add_cog(AdminCommands(self))
        await self.add_cog(SetupCommands(self))
        await self.add_cog(MarketDisplayCommands(self))
        
        self.logger.info("All cogs loaded successfully")
    
    async def on_ready(self):
        """Bot is ready and connected"""
        self.logger.info(f"Logged in as {self.user} (ID: {self.user.id})")
        self.logger.info(f"Connected to {len(self.guilds)} guild(s)")
        
        # Sync slash commands
        try:
            # Clear existing commands first to force full re-sync
            # This ensures Discord updates its cache with our new autocomplete
            for guild in self.guilds:
                guild_obj = discord.Object(id=guild.id)
                
                # Clear guild commands first
                self.tree.clear_commands(guild=guild_obj)
                
                # Copy all global commands to this guild
                self.tree.copy_global_to(guild=guild_obj)
                
                synced = await self.tree.sync(guild=guild_obj)
                self.logger.info(f"Synced {len(synced)} slash commands to guild {guild.name}")
                
            # TODO: When ready for multi-guild, switch to global commands only:
            # synced = await self.tree.sync()
            # self.logger.info(f"Synced {len(synced)} slash commands globally")
        except Exception as e:
            self.logger.error(f"Failed to sync slash commands: {e}", exc_info=True)
        
        # Register all connected guilds
        for guild in self.guilds:
            await self.db.register_guild(guild.id, guild.name, guild.owner_id)
            
            # Try to auto-configure from config file if this is the primary guild
            # and no settings exist yet
            await self._auto_configure_guild(guild)
        
        # Set bot status
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="crypto markets | /help"
            )
        )
    
    async def _auto_configure_guild(self, guild):
        """Auto-configure guild channels from config file"""
        # Only auto-configure if we have channel IDs in config
        # This works for single-server bots where config has the actual IDs
        try:
            # Check if config has channel IDs (not just names)
            if 'market_event_channel_id' in self.config or 'timezone_channels' in self.config:
                self.logger.info(f"Auto-configuring channels for guild {guild.name} from config file")
                
                async with self.db.pool.acquire() as conn:
                    async with conn.cursor() as cursor:
                        # Configure timezone channels in timezone_channels table
                        for tz_config in self.config.get('timezone_channels', []):
                            channel = guild.get_channel(tz_config['channel_id'])
                            if channel:
                                await cursor.execute("""
                                    INSERT INTO timezone_channels (guild_id, channel_id, timezone)
                                    VALUES (%s, %s, %s)
                                    ON DUPLICATE KEY UPDATE timezone = VALUES(timezone)
                                """, (
                                    guild.id,
                                    tz_config['channel_id'],
                                    tz_config['timezone']
                                ))
                        
                        # Configure market channels using guild_settings
                        if 'market_event_channel_id' in self.config:
                            await self.db.set_setting(guild.id, 'market_countdown', str(self.config['market_event_channel_id']))
                        
                        if 'market_times_message_channel_id' in self.config:
                            await self.db.set_setting(guild.id, 'market_schedule', str(self.config['market_times_message_channel_id']))
                        
                        await conn.commit()
                        self.logger.info(f"Auto-configuration complete for guild {guild.name}")
        except Exception as e:
            self.logger.error(f"Error auto-configuring guild {guild.name}: {e}")
    
    async def on_guild_join(self, guild):
        """Register new guild when bot joins"""
        self.logger.info(f"Joined new guild: {guild.name} ({guild.id})")
        await self.db.register_guild(guild.id, guild.name, guild.owner_id)
        
        # Send welcome message to the first available text channel
        for channel in guild.text_channels:
            if channel.permissions_for(guild.me).send_messages:
                embed = discord.Embed(
                    title="👋 Thanks for adding CryptoWatch Bot!",
                    description=(
                        "I'm here to help you track crypto markets and keep your community engaged.\n\n"
                        "**Getting Started:**\n"
                        "1. Run `!setup` to see configuration options\n"
                        "2. Set up timezone channels with `!setup_timezone`\n"
                        "3. Configure market tracking channels\n"
                        "4. Enable engagement tracking (optional)\n\n"
                        "**Need Help?**\n"
                        "• Use `!help` to see all commands\n"
                        "• Visit [our website](https://example.com)\n"
                        "• Join our [support server](https://discord.gg/your-invite)\n\n"
                        "_Note: Administrator permissions required for setup_"
                    ),
                    color=discord.Color.blue()
                )
                embed.set_footer(text="CryptoWatch Bot • example.com")
                
                try:
                    await channel.send(embed=embed)
                    break
                except:
                    continue
    
    async def close(self):
        """Clean up database connection on shutdown"""
        if hasattr(self, 'db'):
            await self.db.close()
        await super().close()

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
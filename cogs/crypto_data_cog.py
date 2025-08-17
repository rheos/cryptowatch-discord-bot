"""
Crypto Data Cog - Manages session and provides crypto API access
This cog now serves as a session provider for other crypto-related functionality
All commands have been moved to slash commands in crypto_commands.py
"""
import discord
from discord.ext import commands
import aiohttp
import logging
from utils.crypto_api import CryptoAPI

logger = logging.getLogger('discord-bot.crypto')

class CryptoDataCog(commands.Cog):
    """
    Manages the crypto API session and provides shared access to crypto data
    
    This cog:
    - Maintains a single aiohttp session for all crypto API calls
    - Provides a CryptoAPI instance that other cogs can use
    - Ensures proper cleanup of resources
    """
    
    def __init__(self, bot, config):
        self.bot = bot
        self.config = config
        # API base URL is static - always use production API
        self.api_base = 'https://example.com/api'
        self.session = None
        self.crypto_api = None
    
    async def cog_load(self):
        """Initialize session and API client when cog loads"""
        self.session = aiohttp.ClientSession()
        self.crypto_api = CryptoAPI(self.api_base, self.session)
        logger.info("Crypto data cog loaded - session initialized")
    
    async def cog_unload(self):
        """Cleanup when cog is unloaded"""
        if self.session:
            await self.session.close()
            self.session = None
        self.crypto_api = None
        logger.info("Crypto data cog unloaded - session closed")
    
    def get_api_client(self) -> CryptoAPI:
        """
        Get the shared CryptoAPI client instance
        
        Returns:
            CryptoAPI instance with active session
        """
        if not self.crypto_api:
            # Create a new instance if needed
            self.crypto_api = CryptoAPI(self.api_base, self.session)
        return self.crypto_api

async def setup(bot):
    # This allows the cog to be loaded dynamically
    pass
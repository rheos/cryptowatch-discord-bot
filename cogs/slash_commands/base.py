"""
Base class for slash command cogs with shared utilities
"""
import discord
from discord.ext import commands
import logging
import aiohttp
from typing import Optional, Dict, Any, List
import os
import sys

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

logger = logging.getLogger('discord-bot.slash_commands')

class SlashCommandBase(commands.Cog):
    """Base class with shared functionality for slash commands"""
    
    def __init__(self, bot):
        self.bot = bot
        self.config = getattr(bot, 'config', {})
        # Use API URL from config, fallback to environment variable, then default
        self.api_base_url = self.config.get('api_base_url', 
                                           os.getenv('API_BASE_URL', 'http://app:5173/api'))
        logger.info(f"Using API base URL: {self.api_base_url}")
    
    async def fetch_json(self, url: str, timeout: int = 10) -> Optional[Dict[str, Any]]:
        """Fetch JSON data from a URL with error handling"""
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        logger.error(f"HTTP {response.status} from {url}")
                        return None
            except aiohttp.ClientError as e:
                logger.error(f"Error fetching {url}: {e}")
                return None
            except Exception as e:
                logger.error(f"Unexpected error fetching {url}: {e}")
                return None
    
    def format_number(self, num: float, decimals: int = 2) -> str:
        """Format number with appropriate decimals and commas"""
        if num >= 1000:
            return f"{num:,.{decimals}f}"
        elif num >= 1:
            return f"{num:.{decimals}f}"
        else:
            # For small numbers, show more decimals
            return f"{num:.6f}".rstrip('0').rstrip('.')
    
    def parse_timeframe(self, timeframe: str) -> int:
        """Parse timeframe string to hours (e.g., '1h' -> 1, '24h' -> 24)"""
        if timeframe.endswith('h'):
            return int(timeframe[:-1])
        return 1  # Default to 1 hour
    
    def get_price_emoji(self, change: float) -> str:
        """Get emoji based on price change"""
        if change > 0:
            return "📈"
        elif change < 0:
            return "📉"
        else:
            return "➡️"
    
    def get_funding_emoji(self, rate: float) -> str:
        """Get emoji based on funding rate"""
        if rate < -0.5:
            return "🔴"  # Very negative
        elif rate < -0.1:
            return "🟠"  # Negative
        elif rate > 0.5:
            return "🟢"  # Very positive
        elif rate > 0.1:
            return "🟡"  # Positive
        else:
            return "⚪"  # Neutral
    
    async def create_error_embed(self, title: str, description: str) -> discord.Embed:
        """Create a standardized error embed"""
        return discord.Embed(
            title=f"❌ {title}",
            description=description,
            color=discord.Color.red()
        )
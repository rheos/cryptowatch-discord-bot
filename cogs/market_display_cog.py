"""
Market Display Cog - Updates voice channel names with market data
Supports any coin price and market info fields (BTC dominance, Fear & Greed, etc.)
"""
import discord
from discord.ext import commands, tasks
import logging
import asyncio
from typing import Dict, Optional, Any
from datetime import datetime

logger = logging.getLogger('discord-bot.market_display')

class MarketDisplayCog(commands.Cog):
    """Updates voice channels with live market data"""
    
    def __init__(self, bot, config):
        self.bot = bot
        self.config = config
        self.cached_market_info = {}  # Cache market info data
        self.cached_prices = {}  # Cache price data
        self.update_market_channels.start()
    
    def cog_unload(self):
        """Cleanup when cog is unloaded"""
        self.update_market_channels.cancel()
    
    def format_channel_name(self, display_type: str, symbol: str, value: Any, custom_label: Optional[str] = None) -> str:
        """Format the channel name based on display type and value"""
        
        if display_type == 'coin_price':
            # Format coin prices
            if custom_label:
                label = custom_label
            else:
                label = symbol.upper()
            
            if value is None:
                return f"{label}: ---"
            
            price = float(value)
            if price >= 10000:
                return f"{label}: ${price/1000:.1f}k"
            elif price >= 1000:
                return f"{label}: ${price:,.0f}"
            elif price >= 100:
                return f"{label}: ${price:.1f}"
            elif price >= 1:
                return f"{label}: ${price:.2f}"
            else:
                return f"{label}: ${price:.4f}"
        
        elif display_type == 'market_info':
            # Handle different market info fields
            if symbol == 'btc_dominance':
                label = custom_label or "BTC.D"
                if value is None:
                    return f"{label}: --%"
                return f"{label}: {float(value):.1f}%"
            
            elif symbol == 'eth_dominance':
                label = custom_label or "ETH.D"
                if value is None:
                    return f"{label}: --%"
                return f"{label}: {float(value):.1f}%"
            
            elif symbol == 'fear_greed' or symbol == 'fear_greed.value':
                if value is None:
                    return "F&G: ---"
                
                # If it's a dict, extract the value
                if isinstance(value, dict):
                    fg_value = value.get('value', 0)
                    classification = value.get('classification', 'Unknown')
                else:
                    fg_value = value
                    classification = self.get_fear_greed_classification(fg_value)
                
                emoji = self.get_fear_greed_emoji(classification)
                label = custom_label or "F&G"
                return f"{emoji} {label}: {fg_value}"
            
            elif symbol == 'total_market_cap':
                label = custom_label or "MCap"
                if value is None:
                    return f"{label}: ---"
                
                mcap = float(value)
                if mcap >= 1e12:
                    return f"{label}: ${mcap/1e12:.2f}T"
                elif mcap >= 1e9:
                    return f"{label}: ${mcap/1e9:.0f}B"
                else:
                    return f"{label}: ${mcap/1e6:.0f}M"
            
            elif symbol == 'total_volume_24h':
                label = custom_label or "Vol24h"
                if value is None:
                    return f"{label}: ---"
                
                vol = float(value)
                if vol >= 1e9:
                    return f"{label}: ${vol/1e9:.1f}B"
                else:
                    return f"{label}: ${vol/1e6:.0f}M"
            
            else:
                # Generic handling for other fields
                label = custom_label or symbol.replace('_', ' ').title()
                if value is None:
                    return f"{label}: ---"
                
                # Try to format as number if possible
                try:
                    num_value = float(value)
                    if '.' in str(value):
                        return f"{label}: {num_value:.2f}"
                    else:
                        return f"{label}: {num_value:,.0f}"
                except:
                    return f"{label}: {value}"
        
        return "Invalid Config"
    
    def get_fear_greed_classification(self, value: int) -> str:
        """Get Fear & Greed classification from value"""
        if value <= 25:
            return "Extreme Fear"
        elif value <= 45:
            return "Fear"
        elif value <= 55:
            return "Neutral"
        elif value <= 75:
            return "Greed"
        else:
            return "Extreme Greed"
    
    def get_fear_greed_emoji(self, classification: str) -> str:
        """Get emoji for Fear & Greed classification"""
        emojis = {
            "Extreme Fear": "😱",
            "Fear": "😨",
            "Neutral": "😐",
            "Greed": "🤑",
            "Extreme Greed": "🤯"
        }
        return emojis.get(classification, "📊")
    
    def extract_nested_value(self, data: Dict, path: str) -> Any:
        """Extract value from nested dict using dot notation (e.g., 'fear_greed.value')"""
        keys = path.split('.')
        value = data
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return None
        return value
    
    async def fetch_market_data(self) -> None:
        """Fetch all required market data and cache it"""
        try:
            # Get the crypto API client
            crypto_cog = self.bot.get_cog('CryptoDataCog')
            if not crypto_cog:
                logger.error("CryptoDataCog not found")
                return
            
            api_client = crypto_cog.get_api_client()
            
            # Fetch market info once (for all market_info type channels)
            market_info = await api_client.get_market_info()
            if market_info and market_info.get('success'):
                self.cached_market_info = market_info.get('data', {})
                logger.debug(f"Cached market info with keys: {list(self.cached_market_info.keys())}")
            
            # Get list of unique coins we need prices for
            coins_needed = set()
            async with self.bot.db.pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        SELECT DISTINCT symbol 
                        FROM market_display_channels 
                        WHERE display_type = 'coin_price' AND enabled = TRUE
                    """)
                    
                    rows = await cursor.fetchall()
                    for row in rows:
                        coins_needed.add(row[0])
            
            # Fetch prices for needed coins
            for symbol in coins_needed:
                price_data = await api_client.get_price(symbol)
                if price_data:
                    self.cached_prices[symbol.upper()] = price_data.get('price', 0)
                    logger.debug(f"Cached price for {symbol}: {self.cached_prices[symbol.upper()]}")
            
        except Exception as e:
            logger.error(f"Error fetching market data: {e}")
    
    @tasks.loop(minutes=5)  # Update every 5 minutes by default
    async def update_market_channels(self):
        """Update market display channels"""
        try:
            # Add small delay to avoid conflicts
            await asyncio.sleep(3)
            
            logger.info("Starting market display channel updates...")
            
            # Fetch fresh data once for all guilds
            await self.fetch_market_data()
            
            if not self.cached_market_info and not self.cached_prices:
                logger.warning("No market data available, skipping update")
                return
            
            updates_made = 0
            updates_attempted = 0
            
            # Process all guilds
            for guild in self.bot.guilds:
                # Check if feature is enabled
                enabled = await self.bot.db.get_setting(guild.id, 'market_display_enabled')
                if not enabled:
                    continue
                
                # Get configured channels from database
                async with self.bot.db.pool.acquire() as conn:
                    async with conn.cursor() as cursor:
                        await cursor.execute("""
                            SELECT channel_id, display_type, symbol, custom_label
                            FROM market_display_channels
                            WHERE guild_id = %s AND enabled = TRUE
                        """, (guild.id,))
                        
                        channels = await cursor.fetchall()
                        
                        for row in channels:
                            channel_id, display_type, symbol, custom_label = row
                            channel = self.bot.get_channel(channel_id)
                            
                            if not channel:
                                logger.warning(f"Channel {channel_id} not found")
                                continue
                            
                            updates_attempted += 1
                            
                            # Get the value based on type
                            value = None
                            if display_type == 'coin_price':
                                value = self.cached_prices.get(symbol.upper())
                            elif display_type == 'market_info':
                                value = self.extract_nested_value(self.cached_market_info, symbol)
                            
                            # Format the channel name
                            new_name = self.format_channel_name(display_type, symbol, value, custom_label)
                            
                            # Only update if name changed
                            if channel.name != new_name:
                                try:
                                    await channel.edit(name=new_name)
                                    updates_made += 1
                                    logger.info(f"Updated {guild.name}/{channel.name} → {new_name}")
                                except discord.errors.Forbidden:
                                    logger.error(f"No permission to edit channel {channel.name}")
                                except discord.errors.HTTPException as e:
                                    if e.status == 429:  # Rate limited
                                        logger.warning(f"Rate limited updating {channel.name}")
                                        await asyncio.sleep(10)
                                    else:
                                        logger.error(f"Failed to update {channel.name}: {e}")
                            else:
                                logger.debug(f"Channel {channel.name} already up to date")
            
            logger.info(f"Market display updates complete: {updates_made}/{updates_attempted} channels updated")
            
        except Exception as e:
            logger.error(f"Error in market display update loop: {e}", exc_info=True)
    
    @update_market_channels.before_loop
    async def before_market_update(self):
        """Wait for bot to be ready before starting the loop"""
        await self.bot.wait_until_ready()
        logger.info("Market display cog ready, starting update loop")
        
        # Check if custom interval is set
        # Note: This checks the first guild's settings - you might want to make this global
        if self.bot.guilds:
            interval = await self.bot.db.get_setting(self.bot.guilds[0].id, 'market_display_interval')
            if interval and 5 <= interval <= 60:
                self.update_market_channels.change_interval(minutes=interval)
                logger.info(f"Market display update interval set to {interval} minutes")

async def setup(bot):
    # This allows the cog to be loaded dynamically
    pass
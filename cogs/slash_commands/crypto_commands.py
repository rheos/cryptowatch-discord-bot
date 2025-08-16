"""
Cryptocurrency-related slash commands: /price, /funding, /volatility
Thin wrapper that delegates to CryptoDataCog methods
"""
import discord
from discord import app_commands
from discord.ext import commands
import logging
import asyncio
from datetime import datetime
from typing import Optional, List, Dict, Any
from .base import SlashCommandBase
from .utils.formatters import format_funding_list, format_volatility_list, format_price_info
from utils.crypto_api import CryptoAPI
import aiohttp

logger = logging.getLogger('discord-bot.crypto_commands')
logger.setLevel(logging.DEBUG)

# Configuration for each funding mode - defines display properties for each funding analysis type
# This config is used to customize embed titles, colors, and messages for different modes
FUNDING_CONFIGS = {
    'negative': {
        'endpoint': '/most-negative',
        'title': '🔻 Most Negative Funding Rates',
        'description': 'Showing top {limit} coins with negative funding on BloFin',
        'color': discord.Color.red(),
        'empty_message': 'No coins with negative funding rates found.',
        'show_change': True,
        'show_rank': True
    },
    'improving': {
        'endpoint': '/improving-negative',
        'title': '📈 Improving Negative Rates',
        'description': 'Coins becoming less negative (potential reversal)',
        'color': discord.Color.green(),
        'empty_message': 'No improving negative rates found.',
        'change_emoji': '📈',
        'show_rank': True
    },
    'worsening': {
        'endpoint': '/worsening-negative',
        'title': '📉 Worsening Negative Rates',
        'description': 'Coins becoming more negative',
        'color': discord.Color.orange(),
        'empty_message': 'No worsening negative rates found.',
        'change_emoji': '📉',
        'show_rank': True
    },
    'turned': {
        'endpoint': '/turned-positive',
        'title': '✅ Recently Turned Positive',
        'description': 'Coins that flipped from negative to positive funding',
        'color': discord.Color.blue(),
        'empty_message': 'No coins recently turned positive.',
        'show_rank': True
    },
    'scanner': {
        'endpoint': '/scanner-summary',
        'title': '📊 Funding Rate Scanner Overview',
        'description': 'Summary of current funding rate trends',
        'color': discord.Color.blue(),
        'empty_message': 'No data available.',
        'is_summary': True
    },
    'check': {
        'endpoint': '/check',
        'title': '🔍 Funding Rate Check',
        'description': 'Current funding rate for {symbol}',
        'color': discord.Color.blue(),
        'empty_message': 'Funding rate data not available.',
        'is_single': True
    }
}

class CryptoCommands(SlashCommandBase):
    """
    Cryptocurrency-related slash commands - delegates to CryptoDataCog
    
    This class provides Discord slash commands for cryptocurrency data:
    - /price - Get current price of a cryptocurrency
    - /funding - Analyze BloFin funding rates
    - /volatility - Track price volatility and top movers
    
    It acts as a thin wrapper, reusing the existing CryptoDataCog's session
    and calling the same API endpoints that the prefix commands (!) use.
    """
    
    def __init__(self, bot):
        """
        Initialize the crypto commands cog
        
        Args:
            bot: The Discord bot instance
        """
        super().__init__(bot)
        # Reference to CryptoDataCog to reuse its session and methods
        self.crypto_cog = None
        # API client instance
        self.api_client = None
    
    async def cog_load(self):
        """
        Initialize API client when cog loads
        Attempts to find and reference the CryptoDataCog for API client reuse
        """
        # Try to find the CryptoDataCog if it's loaded
        # This allows us to reuse its API client and session
        for cog_name, cog in self.bot.cogs.items():
            if 'CryptoDataCog' in cog.__class__.__name__:
                self.crypto_cog = cog
                logger.info("Found CryptoDataCog for delegation")
                break
        
        # Get or create API client
        if self.crypto_cog and hasattr(self.crypto_cog, 'get_api_client'):
            self.api_client = self.crypto_cog.get_api_client()
        else:
            # Create our own API client if CryptoDataCog not available
            self.api_client = CryptoAPI(self.api_base_url)
    
    async def cog_unload(self):
        """
        Cleanup when cog unloads
        Properly closes the API client if we own it
        """
        # Only close if we created our own client
        if self.api_client and not self.crypto_cog:
            await self.api_client.close()
    
    @app_commands.command(name="price", description="Get the current price of a cryptocurrency")
    @app_commands.describe(symbol="The cryptocurrency symbol (e.g., BTC, ETH)")
    async def price_command(self, interaction: discord.Interaction, symbol: str):
        """
        Get cryptocurrency price from either our API cache or Binance directly
        
        Args:
            interaction: Discord interaction object
            symbol: Cryptocurrency symbol (e.g., BTC, ETH)
        """
        # Defer response since API calls might take time
        await interaction.response.defer()
        
        try:
            # Get price data using the API client
            price_data = await self.api_client.get_symbol_price(symbol)
            
            if price_data:
                # Format and send the price info
                embed = format_price_info(symbol.upper().replace('USDT', '').strip(), price_data)
                await interaction.followup.send(embed=embed)
            else:
                # Symbol not found
                await interaction.followup.send(f"❌ Could not find price data for **{symbol}**")
                
        except Exception as e:
            logger.error(f"Error fetching price for {symbol}: {e}")
            await interaction.followup.send(f"❌ Error fetching price data for **{symbol}**")
    
    @app_commands.command(name="funding", description="BloFin funding rate analysis tools")
    @app_commands.describe(
        mode="Type of funding analysis to perform",
        limit="Number of results to show (default: 10)",
        symbol="Symbol to check (only for 'check' mode)"
    )
    @app_commands.choices(mode=[
        app_commands.Choice(name="Most Negative", value="negative"),
        app_commands.Choice(name="Scanner (Overview)", value="scanner"),
        app_commands.Choice(name="Improving (Less Negative)", value="improving"),
        app_commands.Choice(name="Worsening (More Negative)", value="worsening"),
        app_commands.Choice(name="Recently Turned Positive", value="turned"),
        app_commands.Choice(name="Check Specific Symbol", value="check"),
    ])
    async def funding_rates(self, interaction: discord.Interaction, 
                           mode: str, 
                           limit: Optional[int] = 10,
                           symbol: Optional[str] = None):
        """
        Get funding rate information from BloFin exchange
        
        Funding rates indicate the sentiment of perpetual futures traders:
        - Negative rates: More shorts than longs (bearish sentiment)
        - Positive rates: More longs than shorts (bullish sentiment)
        
        Args:
            interaction: Discord interaction object
            mode: Type of analysis (negative, scanner, improving, worsening, turned, check)
            limit: Number of results to display (default 10)
            symbol: Specific symbol to check (only for 'check' mode)
        """
        logger.info(f"Funding command invoked - mode: {mode}, limit: {limit}, symbol: {symbol}")
        await interaction.response.defer()
        
        try:
            # Scanner mode: Fetch all 4 funding categories and show overview
            # This gives a comprehensive market snapshot
            if mode == 'scanner':
                # Get comprehensive scanner data using API client
                results = await self.api_client.get_funding_scanner_data()
                
                # Create overview embed with all categories
                embed = discord.Embed(
                    title="🔍 Funding Scanner Overview",
                    description="Current market funding rates",
                    color=discord.Color.gold(),
                    timestamp=datetime.utcnow()
                )
                
                # Add Most Negative section - coins with extreme negative funding
                # These are potential short squeeze candidates
                if results.get('most_negative'):
                    most_neg = results['most_negative'][:5]  # Top 5 only for overview
                    if most_neg:
                        value = "\n".join([
                            f"**{self.api_client.format_symbol(r['instId'])}**: {self.api_client.format_percentage(float(r['currentRate']))}"
                            for r in most_neg
                        ])
                        embed.add_field(name="🔴 Most Negative", value=value, inline=False)
                
                # Add Turned Positive section - recently flipped from negative to positive
                # These indicate potential trend reversals
                if results.get('turned_positive'):
                    turned = results['turned_positive'][:5]
                    if turned:
                        value = "\n".join([
                            f"**{self.api_client.format_symbol(r['instId'])}**: {self.api_client.format_percentage(float(r['currentRate']))}"
                            for r in turned
                        ])
                        embed.add_field(name="🟢 Turned Positive", value=value, inline=False)
                
                # Add Worsening section - becoming more negative
                # Indicates increasing short interest
                if results.get('worsening'):
                    worse = results['worsening'][:5]
                    if worse:
                        value = "\n".join([
                            f"**{self.api_client.format_symbol(r['instId'])}**: {self.api_client.format_percentage(float(r['currentRate']))}"
                            for r in worse
                        ])
                        embed.add_field(name="🟠 Worsening", value=value, inline=False)
                
                # Add Improving section - becoming less negative
                # Shorts may be closing, potential bullish signal
                if results.get('improving'):
                    improving = results['improving'][:5]
                    if improving:
                        value = "\n".join([
                            f"**{self.api_client.format_symbol(r['instId'])}**: {self.api_client.format_percentage(float(r['currentRate']))}"
                            for r in improving
                        ])
                        embed.add_field(name="🟡 Improving", value=value, inline=False)
                
                embed.set_footer(text="Use /funding with specific modes for detailed views")
                await interaction.followup.send(embed=embed)
                return
            
            # For non-scanner modes: Use appropriate API method
            if mode == 'negative':
                rates = await self.api_client.get_most_negative_rates(limit)
            elif mode == 'turned':
                rates = await self.api_client.get_turned_positive_rates(limit)
            elif mode == 'improving':
                rates = await self.api_client.get_improving_negative_rates(limit)
            elif mode == 'worsening':
                rates = await self.api_client.get_worsening_negative_rates(limit)
            else:
                await interaction.followup.send("❌ Invalid mode selected")
                return
            
            if rates:
                # Create mode-specific embed based on the type of analysis
                if mode == 'negative':
                    # Most negative funding rates - extreme short interest
                    embed = discord.Embed(
                        title="🔴 Most Negative",
                        description=f"Top {len(rates)} coins with extreme negative funding rates",
                        color=discord.Color.red(),
                        timestamp=datetime.utcnow()
                    )
                    
                    # Display as numbered list with funding percentages
                    for i, rate in enumerate(rates, 1):
                        symbol = self.api_client.format_symbol(rate['instId'])
                        funding_pct = self.api_client.format_percentage(float(rate['currentRate']), 4)
                        embed.add_field(
                            name=f"{i}. {symbol}",
                            value=funding_pct,
                            inline=True
                        )
                
                elif mode == 'turned':
                    # Recently turned positive - potential trend reversal
                    embed = discord.Embed(
                        title="🟢 Turned Positive",
                        description="Recently flipped from negative to positive funding",
                        color=discord.Color.green(),
                        timestamp=datetime.utcnow()
                    )
                    
                    # Show current vs previous rates to highlight the change
                    for rate in rates:
                        symbol = self.api_client.format_symbol(rate['instId'])
                        current_pct = self.api_client.format_percentage(float(rate['currentRate']))
                        previous_pct = self.api_client.format_percentage(self.api_client.get_previous_rate(rate))
                        
                        embed.add_field(
                            name=symbol,
                            value=f"Now: {current_pct}\nWas: {previous_pct}",
                            inline=True
                        )
                
                elif mode == 'improving':
                    # Improving negative rates - shorts closing
                    embed = discord.Embed(
                        title="🟡 Improving Negative",
                        description="Still negative but getting better",
                        color=discord.Color.orange(),
                        timestamp=datetime.utcnow()
                    )
                    
                    # Show rate with improvement indicator
                    for rate in rates:
                        symbol = self.api_client.format_symbol(rate['instId'])
                        current_pct = self.api_client.format_percentage(float(rate['currentRate']))
                        change_pct = self.api_client.format_percentage(self.api_client.get_rate_change(rate))
                        
                        embed.add_field(
                            name=symbol,
                            value=f"{current_pct}\n↗️ +{change_pct}",
                            inline=True
                        )
                
                elif mode == 'worsening':
                    # Worsening negative rates - shorts building
                    embed = discord.Embed(
                        title="🟠 Worsening Negative",
                        description="Getting more negative - shorts building",
                        color=discord.Color.dark_red(),
                        timestamp=datetime.utcnow()
                    )
                    
                    # Show rate with deterioration indicator
                    for rate in rates:
                        symbol = self.api_client.format_symbol(rate['instId'])
                        current_pct = self.api_client.format_percentage(float(rate['currentRate']))
                        change_pct = self.api_client.format_percentage(self.api_client.get_rate_change(rate))
                        
                        embed.add_field(
                            name=symbol,
                            value=f"{current_pct}\n↘️ {change_pct}",
                            inline=True
                        )
                    
                # Add footer with data source info
                embed.set_footer(text="Data from BloFin • Updates every 30 minutes")
                await interaction.followup.send(embed=embed)
            else:
                await interaction.followup.send("❌ Failed to fetch funding rates")
                    
        except Exception as e:
            logger.error(f"Error in funding command: {e}")
            await interaction.followup.send("❌ An error occurred")
    
    @app_commands.command(name="volatility", description="Track price volatility and top movers")
    @app_commands.describe(
        mode="Type of volatility analysis",
        timeframe="Time period for analysis",
        limit="Number of results to show",
        symbol="Symbol to check (only for 'Check Specific Symbol' mode)"
    )
    @app_commands.choices(
        mode=[
            app_commands.Choice(name="Scanner (Top Movers)", value="scanner"),
            app_commands.Choice(name="Most Volatile", value="movers"),
            app_commands.Choice(name="Check Specific Symbol", value="check"),
        ],
        timeframe=[
            app_commands.Choice(name="5 minutes", value="5m"),
            app_commands.Choice(name="15 minutes", value="15m"),
            app_commands.Choice(name="1 hour", value="1h"),
            app_commands.Choice(name="4 hours", value="4h"),
            app_commands.Choice(name="24 hours", value="24h"),
        ]
    )
    async def volatility_command(self, interaction: discord.Interaction,
                                mode: str,
                                timeframe: str = "1h",
                                limit: Optional[int] = 10,
                                symbol: Optional[str] = None):
        """
        Get volatility information to identify coins with significant price movements
        
        Volatility tracking helps identify:
        - Potential breakout opportunities
        - High-momentum trades
        - Market manipulation or news-driven moves
        
        Args:
            interaction: Discord interaction object
            mode: Type of analysis (scanner, movers, check)
            timeframe: Time period to analyze (5m, 15m, 1h, 4h, 24h)
            limit: Number of results to show
            symbol: Specific symbol to check (only for 'check' mode)
        """
        logger.info(f"Volatility command invoked - mode: {mode}, timeframe: {timeframe}, limit: {limit}, symbol: {symbol}")
        # Debug: Log all interaction data options
        logger.debug(f"Interaction data: {interaction.data}")
        await interaction.response.defer()
        
        try:
            # Check mode: Analyze specific symbol's volatility
            if mode == "check":
                if not symbol:
                    await interaction.followup.send(
                        "❌ Please provide a symbol to check\n"
                        "Example: `/volatility check symbol:BTC`"
                    )
                    return
                
                # Normalize symbol
                symbol = symbol.upper().replace('USDT', '').strip()
                await self._handle_volatility_check(interaction, symbol, timeframe)
            
            # Scanner or movers mode: Find volatile coins across the market
            elif mode == "scanner" or mode == "movers":
                # Define volatility thresholds for each timeframe
                # Shorter timeframes have lower thresholds since price moves are smaller
                default_thresholds = {
                    '5m': 2,      # 2% in 5 minutes is significant
                    '15m': 3,     # 3% in 15 minutes
                    '30m': 4,     # 4% in 30 minutes
                    '1h': 5,      # 5% in 1 hour
                    '2h': 7,      # 7% in 2 hours
                    '3h': 10,     # 10% in 3 hours
                    '4h': 12,     # 12% in 4 hours
                    '6h': 15,     # 15% in 6 hours
                    '12h': 20,    # 20% in 12 hours
                    '24h': 25,    # 25% in 24 hours
                    '48h': 30     # 30% in 48 hours
                }
                
                # Volatility scanning is a read-only feature, no need to restrict it
                # In the future, we could check for custom thresholds here
                # volatility_enabled check removed - feature available to all guilds by default
                
                if mode == "scanner":
                    # Scanner mode: Show overview across multiple timeframes
                    scanner_timeframes = {
                        '5m': 2,
                        '15m': 3,
                        '1h': 5,
                        '4h': 12,
                        '24h': 25,
                        '48h': 30
                    }
                    
                    # Get and format data using API client
                    raw_results = await self.api_client.get_volatility_scanner_multi(scanner_timeframes)
                    if not raw_results:
                        await interaction.followup.send("❌ Failed to fetch volatility data")
                        return
                    
                    # Let the API client handle all the formatting
                    formatted_data = self.api_client.format_volatility_summary(raw_results, scanner_timeframes)
                    
                    # Create embed
                    embed = discord.Embed(
                        title="📊 Volatility Scanner - All Timeframes",
                        description="High volatility coins across different periods",
                        color=discord.Color.blue(),
                        timestamp=datetime.utcnow()
                    )
                    
                    # Just add the formatted fields
                    for tf in ['5m', '15m', '1h', '4h', '24h', '48h']:
                        if tf in formatted_data:
                            data = formatted_data[tf]
                            embed.add_field(
                                name=f"⏱️ {tf} (≥{data['threshold']}%)",
                                value="\n".join(data['formatted_lines']),
                                inline=True
                            )
                    
                    embed.set_footer(text="Use /volatility movers for detailed view of specific timeframe")
                    await interaction.followup.send(embed=embed)
                    
                else:  # mode == "movers"
                    # Movers mode: Detailed list for specific timeframe
                    threshold = default_thresholds.get(timeframe, 5)
                    
                    # Get raw data
                    data = await self.api_client.get_volatility_scanner(timeframe, threshold)
                    if not data or not data.get('success'):
                        await interaction.followup.send("❌ Failed to fetch volatility data")
                        return
                    
                    # Find matching timeframe data
                    threshold_data = None
                    for t in data.get('thresholds', []):
                        hours = t.get('hours', 0)
                        tf = f"{int(hours * 60)}m" if hours < 1 else f"{int(hours)}h"
                        if tf == timeframe:
                            threshold_data = t
                            break
                    
                    if not threshold_data or not threshold_data.get('coins'):
                        await interaction.followup.send(f"No coins found with ≥{threshold}% movement in {timeframe}")
                        return
                    
                    # Let API client handle formatting
                    formatted_coins = self.api_client.format_detailed_movers(threshold_data['coins'], limit)
                    
                    # Create embed
                    embed = discord.Embed(
                        title=f"💹 Top Movers - {timeframe}",
                        description=f"Most volatile symbols (≥{threshold}% movement)",
                        color=discord.Color.blue(),
                        timestamp=datetime.utcnow()
                    )
                    
                    # Add formatted fields
                    for coin_data in formatted_coins:
                        embed.add_field(
                            name=f"{coin_data['chart_emoji']} {coin_data['symbol']}",
                            value=f"{coin_data['action_emoji']} {coin_data['percent_str']}\n{coin_data['price_str']}",
                            inline=True
                        )
                    
                    if not formatted_coins:
                        embed.description = "No significant movers found"
                    
                    await interaction.followup.send(embed=embed)
                
        except Exception as e:
            logger.error(f"Error in volatility command: {e}")
            await interaction.followup.send("❌ An error occurred while fetching volatility data")
    
    async def _handle_volatility_check(self, interaction: discord.Interaction, symbol: str, timeframe: str):
        """
        Handle checking volatility for a specific symbol (DRY - delegates to API client)
        """
        # Use API client to get symbol volatility
        data = await self.api_client.get_symbol_volatility(symbol, timeframe)
        
        if not data:
            await interaction.followup.send(f"❌ Failed to fetch volatility data")
            return
        
        if not data.get('found'):
            # Symbol not volatile enough, try to show price data
            price_data = await self.api_client.get_symbol_price(symbol)
            if price_data:
                embed = discord.Embed(
                    title=f"📊 {symbol.upper()} - {timeframe}",
                    description=f"No significant volatility in {timeframe}",
                    color=discord.Color.blue()
                )
                embed.add_field(
                    name="Current Price",
                    value=f"${price_data.get('price', 0):.4f}",
                    inline=True
                )
                embed.add_field(
                    name="24h Change",
                    value=f"{price_data.get('priceChangePercent', 0):+.2f}%",
                    inline=True
                )
                await interaction.followup.send(embed=embed)
            else:
                await interaction.followup.send(f"❌ No data found for **{symbol.upper()}**")
            return
        
        # Create embed with volatility data
        percent_change = data['percentChange']
        color = discord.Color.green() if percent_change > 0 else discord.Color.red()
        emoji = "📈" if percent_change > 0 else "📉"
        
        embed = discord.Embed(
            title=f"{emoji} {data['symbol']} - {timeframe}",
            color=color,
            timestamp=datetime.utcnow()
        )
        
        embed.add_field(
            name="Price Change",
            value=f"{percent_change:+.2f}%",
            inline=True
        )
        
        embed.add_field(
            name="Current Price",
            value=f"${data['currentPrice']:.4f}",
            inline=True
        )
        
        embed.add_field(
            name="Start Price",
            value=f"${data['startPrice']:.4f}",
            inline=True
        )
        
        await interaction.followup.send(embed=embed)

async def setup(bot):
    """
    Setup function called by Discord.py to load this cog
    
    Args:
        bot: The Discord bot instance
    """
    await bot.add_cog(CryptoCommands(bot))
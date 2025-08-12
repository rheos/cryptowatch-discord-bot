"""
Cryptocurrency-related slash commands: /price, /funding, /volatility
"""
import discord
from discord import app_commands
from discord.ext import commands
import logging
from typing import Optional, List, Dict, Any
from .base import SlashCommandBase
from .utils.formatters import format_funding_list, format_volatility_list, format_price_info

logger = logging.getLogger('discord-bot.crypto_commands')

# Configuration for each funding mode
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
    """Cryptocurrency-related slash commands"""
    
    @app_commands.command(name="price", description="Get the current price of a cryptocurrency")
    @app_commands.describe(symbol="The cryptocurrency symbol (e.g., BTC, ETH)")
    async def price_command(self, interaction: discord.Interaction, symbol: str):
        """Get cryptocurrency price"""
        await interaction.response.defer()
        
        # Clean up symbol
        symbol = symbol.upper().replace('USDT', '').strip()
        
        try:
            # Try primary endpoint first
            url = f"{self.api_base_url}/api/volatility-scanner/price-data"
            data = await self.fetch_json(url, timeout=5)
            
            if data and 'symbols' in data:
                # Look for the symbol in the data
                symbol_data = None
                for sym, info in data['symbols'].items():
                    if sym.replace('-USDT', '').replace('USDT', '') == symbol:
                        symbol_data = info
                        break
                
                if symbol_data:
                    embed = format_price_info(symbol, symbol_data)
                    await interaction.followup.send(embed=embed)
                    return
            
            # If not found, try Binance API directly
            binance_url = f"https://api.binance.com/api/v3/ticker/24hr?symbol={symbol}USDT"
            ticker_data = await self.fetch_json(binance_url, timeout=5)
            
            if ticker_data:
                price_data = {
                    'price': float(ticker_data.get('lastPrice', 0)),
                    'priceChangePercent': float(ticker_data.get('priceChangePercent', 0)),
                    'volume': float(ticker_data.get('volume', 0))
                }
                embed = format_price_info(symbol, price_data)
                await interaction.followup.send(embed=embed)
            else:
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
        """Get funding rate information from BloFin"""
        await interaction.response.defer()
        
        config = FUNDING_CONFIGS.get(mode, FUNDING_CONFIGS['negative'])
        
        # Handle single symbol check
        if mode == 'check':
            if not symbol:
                await interaction.followup.send("❌ Please provide a symbol to check (e.g., `/funding check symbol:BTC`)")
                return
            
            symbol = symbol.upper().replace('USDT', '').strip()
            url = f"{self.api_base_url}/api/funding-rates{config['endpoint']}/{symbol}"
        else:
            # Construct URL for list endpoints
            url = f"{self.api_base_url}/api/funding-rates{config['endpoint']}"
            if limit and limit != 10:
                url += f"?limit={limit}"
        
        try:
            data = await self.fetch_json(url)
            
            if not data:
                embed = await self.create_error_embed(
                    "API Error",
                    "Failed to fetch funding rate data. Please try again later."
                )
                await interaction.followup.send(embed=embed)
                return
            
            # Handle scanner summary mode
            if config.get('is_summary'):
                embed = self._create_scanner_embed(data)
            # Handle single symbol check
            elif config.get('is_single'):
                embed = self._create_single_funding_embed(symbol, data, config)
            # Handle list modes
            else:
                embed = self._create_funding_list_embed(data, config, limit)
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in funding command: {e}")
            embed = await self.create_error_embed(
                "Command Error",
                "An error occurred while processing the funding rates."
            )
            await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="volatility", description="Track price volatility and top movers")
    @app_commands.describe(
        mode="Type of volatility analysis",
        timeframe="Time period for analysis",
        limit="Number of results to show"
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
        """Get volatility information"""
        await interaction.response.defer()
        
        try:
            if mode == "check":
                if not symbol:
                    await interaction.followup.send(
                        "❌ Please provide a symbol to check\n"
                        "Example: `/volatility check symbol:BTC`"
                    )
                    return
                
                symbol = symbol.upper().replace('USDT', '').strip()
                await self._handle_volatility_check(interaction, symbol, timeframe)
            
            elif mode == "scanner":
                url = f"{self.api_base_url}/api/volatility-scanner/summary?timeframe={timeframe}"
                data = await self.fetch_json(url)
                
                if not data:
                    await interaction.followup.send("❌ Failed to fetch volatility data")
                    return
                
                embed = self._create_volatility_scanner_embed(data, timeframe)
                await interaction.followup.send(embed=embed)
            
            elif mode == "movers":
                url = f"{self.api_base_url}/api/volatility-scanner/top-movers?timeframe={timeframe}&limit={limit}"
                data = await self.fetch_json(url)
                
                if not data or 'movers' not in data:
                    await interaction.followup.send("❌ Failed to fetch volatility data")
                    return
                
                embed = self._create_movers_embed(data['movers'], timeframe, limit)
                await interaction.followup.send(embed=embed)
                
        except Exception as e:
            logger.error(f"Error in volatility command: {e}")
            await interaction.followup.send("❌ An error occurred while fetching volatility data")
    
    # Helper methods for creating embeds
    def _create_scanner_embed(self, data: Dict[str, Any]) -> discord.Embed:
        """Create scanner summary embed"""
        embed = discord.Embed(
            title="📊 BloFin Funding Rate Scanner",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )
        
        # Add summary fields
        if 'summary' in data:
            summary = data['summary']
            embed.add_field(
                name="Negative Funding",
                value=f"{summary.get('negativeCount', 0)} coins",
                inline=True
            )
            embed.add_field(
                name="Most Negative",
                value=f"{summary.get('mostNegative', 'N/A')}",
                inline=True
            )
            embed.add_field(
                name="Avg Negative Rate",
                value=f"{summary.get('avgNegativeRate', 0):.3f}%",
                inline=True
            )
        
        # Add trends
        if 'recentTrends' in data:
            trends = data['recentTrends']
            trend_text = []
            if trends.get('improving'):
                trend_text.append(f"📈 {len(trends['improving'])} improving")
            if trends.get('worsening'):
                trend_text.append(f"📉 {len(trends['worsening'])} worsening")
            if trends.get('turnedPositive'):
                trend_text.append(f"✅ {len(trends['turnedPositive'])} turned positive")
            
            if trend_text:
                embed.add_field(
                    name="Recent Trends",
                    value="\n".join(trend_text),
                    inline=False
                )
        
        return embed
    
    def _create_single_funding_embed(self, symbol: str, data: Dict[str, Any], config: Dict[str, Any]) -> discord.Embed:
        """Create embed for single symbol funding check"""
        if 'error' in data:
            return discord.Embed(
                title=f"❌ {symbol} Not Found",
                description=data['error'],
                color=discord.Color.red()
            )
        
        rate = data.get('fundingRate', 0) * 100  # Convert to percentage
        color = discord.Color.red() if rate < 0 else discord.Color.green()
        
        embed = discord.Embed(
            title=f"{self.get_funding_emoji(rate)} {symbol} Funding Rate",
            color=color
        )
        
        embed.add_field(name="Current Rate", value=f"{rate:.4f}%", inline=True)
        embed.add_field(name="Interval", value="8 hours", inline=True)
        
        # Add annualized rate
        annualized = rate * 3 * 365  # 3 times per day
        embed.add_field(
            name="Annualized",
            value=f"{annualized:.2f}%",
            inline=True
        )
        
        return embed
    
    def _create_funding_list_embed(self, data: Dict[str, Any], config: Dict[str, Any], limit: int) -> discord.Embed:
        """Create embed for funding rate lists"""
        rates = data.get('rates', [])
        
        if not rates:
            return discord.Embed(
                title=config['title'],
                description=config['empty_message'],
                color=config['color']
            )
        
        embed = discord.Embed(
            title=config['title'],
            description=config['description'].format(limit=min(len(rates), limit)),
            color=config['color'],
            timestamp=datetime.utcnow()
        )
        
        # Format the list
        lines = format_funding_list(rates, limit)
        
        # Join lines and add to embed
        if lines:
            embed.add_field(
                name="Current Rates",
                value="\n".join(lines),
                inline=False
            )
        
        return embed
    
    def _create_volatility_scanner_embed(self, data: Dict[str, Any], timeframe: str) -> discord.Embed:
        """Create volatility scanner summary embed"""
        embed = discord.Embed(
            title=f"📊 Volatility Scanner - {timeframe}",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )
        
        if 'summary' in data:
            summary = data['summary']
            embed.add_field(
                name="Average Volatility",
                value=f"{summary.get('avgVolatility', 0):.2f}%",
                inline=True
            )
            embed.add_field(
                name="Highest Volatility",
                value=f"{summary.get('maxVolatility', 0):.2f}%",
                inline=True
            )
            embed.add_field(
                name="Active Symbols",
                value=f"{summary.get('totalSymbols', 0)}",
                inline=True
            )
        
        if 'topMovers' in data and data['topMovers']:
            top_5 = data['topMovers'][:5]
            movers_text = []
            for i, mover in enumerate(top_5, 1):
                symbol = mover['symbol']
                change = mover['priceChangePercent']
                emoji = "📈" if change > 0 else "📉"
                movers_text.append(f"{i}. {emoji} **{symbol}** `{change:+.1f}%`")
            
            embed.add_field(
                name="Top Movers",
                value="\n".join(movers_text),
                inline=False
            )
        
        return embed
    
    def _create_movers_embed(self, movers: List[Dict[str, Any]], timeframe: str, limit: int) -> discord.Embed:
        """Create embed for top movers"""
        embed = discord.Embed(
            title=f"💹 Top Movers - {timeframe}",
            description=f"Most volatile symbols by price movement",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )
        
        if not movers:
            embed.description = "No significant movers found"
            return embed
        
        # Format movers list
        lines = format_volatility_list(movers, limit)
        
        if lines:
            embed.add_field(
                name=f"Top {len(lines)} Movers",
                value="\n".join(lines),
                inline=False
            )
        
        return embed
    
    async def _handle_volatility_check(self, interaction: discord.Interaction, symbol: str, timeframe: str):
        """Handle checking volatility for a specific symbol"""
        url = f"{self.api_base_url}/api/volatility-scanner/symbol/{symbol}?timeframe={timeframe}"
        data = await self.fetch_json(url)
        
        if not data or 'error' in data:
            await interaction.followup.send(f"❌ No volatility data found for **{symbol}**")
            return
        
        embed = discord.Embed(
            title=f"📊 {symbol} Volatility - {timeframe}",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="Volatility",
            value=f"{data.get('volatility', 0):.2f}%",
            inline=True
        )
        embed.add_field(
            name="Price Change",
            value=f"{data.get('priceChangePercent', 0):+.2f}%",
            inline=True
        )
        embed.add_field(
            name="High/Low Range",
            value=f"{data.get('range', 0):.2f}%",
            inline=True
        )
        
        await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(CryptoCommands(bot))
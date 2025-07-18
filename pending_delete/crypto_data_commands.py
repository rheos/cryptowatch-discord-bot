"""
Crypto data commands module for the Discord bot
Fetches data from CryptoWatchTools API
"""
import aiohttp
import discord
from datetime import datetime
import asyncio

class CryptoDataCommands:
    def __init__(self, bot):
        self.bot = bot
        self.api_base = "https://cryptowatchtools.com/api"
        self.session = None
    
    async def setup(self):
        """Initialize the aiohttp session"""
        self.session = aiohttp.ClientSession()
    
    async def cleanup(self):
        """Clean up resources"""
        if self.session:
            await self.session.close()
    
    async def on_message(self, message):
        """Handle crypto data commands"""
        if message.author == self.bot.user:
            return
        
        # Only respond to commands with prefix
        if not message.content.startswith('!'):
            return
        
        command = message.content.lower().split()[0]
        
        if command == '!funding':
            await self.show_funding_rates(message)
        elif command == '!turned':
            await self.show_turned_positive(message)
        elif command == '!improving':
            await self.show_improving_rates(message)
        elif command == '!watchlist':
            await self.show_watchlist(message)
        elif command == '!help':
            await self.show_help(message)
    
    async def show_funding_rates(self, message):
        """Show most negative funding rates"""
        try:
            async with self.session.get(f"{self.api_base}/most-negative") as response:
                if response.status == 200:
                    data = await response.json()
                    rates = data.get('rates', [])[:10]
                    
                    embed = discord.Embed(
                        title="🔴 Most Negative Funding Rates",
                        description="Top 10 coins with most negative funding",
                        color=discord.Color.red(),
                        timestamp=datetime.utcnow()
                    )
                    
                    for i, rate in enumerate(rates, 1):
                        inst_id = rate['inst_id'].replace('-USDT', '')
                        funding = rate['current_rate'] * 100  # Convert to percentage
                        embed.add_field(
                            name=f"{i}. {inst_id}",
                            value=f"{funding:.4f}%",
                            inline=True
                        )
                    
                    embed.set_footer(text="Data from BloFin • Updates every 8 hours")
                    await message.channel.send(embed=embed)
                else:
                    await message.channel.send("❌ Failed to fetch funding rates")
                    
        except Exception as e:
            await message.channel.send(f"❌ Error: {str(e)}")
    
    async def show_turned_positive(self, message):
        """Show coins that turned positive from negative"""
        try:
            async with self.session.get(f"{self.api_base}/turned-positive") as response:
                if response.status == 200:
                    data = await response.json()
                    rates = data.get('rates', [])[:10]
                    
                    if not rates:
                        await message.channel.send("📊 No coins have turned positive recently")
                        return
                    
                    embed = discord.Embed(
                        title="🟢 Turned Positive",
                        description="Coins that flipped from negative to positive funding",
                        color=discord.Color.green(),
                        timestamp=datetime.utcnow()
                    )
                    
                    for rate in rates:
                        inst_id = rate['inst_id'].replace('-USDT', '')
                        current = rate['current_rate'] * 100
                        previous = rate.get('prev_rate', 0) * 100
                        change = rate.get('rate_change', 0) * 100
                        
                        embed.add_field(
                            name=inst_id,
                            value=f"Now: {current:.3f}%\nWas: {previous:.3f}%\n∆ +{change:.3f}%",
                            inline=True
                        )
                    
                    embed.set_footer(text="Potential short squeeze candidates")
                    await message.channel.send(embed=embed)
                else:
                    await message.channel.send("❌ Failed to fetch data")
                    
        except Exception as e:
            await message.channel.send(f"❌ Error: {str(e)}")
    
    async def show_improving_rates(self, message):
        """Show negative rates that are improving"""
        try:
            async with self.session.get(f"{self.api_base}/improving-negative") as response:
                if response.status == 200:
                    data = await response.json()
                    rates = data.get('rates', [])[:10]
                    
                    if not rates:
                        await message.channel.send("📊 No improving negative rates found")
                        return
                    
                    embed = discord.Embed(
                        title="📈 Improving Negative Rates",
                        description="Still negative but moving toward positive",
                        color=discord.Color.orange(),
                        timestamp=datetime.utcnow()
                    )
                    
                    for rate in rates:
                        inst_id = rate['inst_id'].replace('-USDT', '')
                        current = rate['current_rate'] * 100
                        change = rate.get('rate_change', 0) * 100
                        
                        embed.add_field(
                            name=inst_id,
                            value=f"Rate: {current:.3f}%\n∆ +{change:.3f}%",
                            inline=True
                        )
                    
                    embed.set_footer(text="Watch for potential reversal")
                    await message.channel.send(embed=embed)
                else:
                    await message.channel.send("❌ Failed to fetch data")
                    
        except Exception as e:
            await message.channel.send(f"❌ Error: {str(e)}")
    
    async def show_watchlist(self, message):
        """Show exchange watchlist"""
        parts = message.content.split()
        exchange = parts[1].lower() if len(parts) > 1 else "blofin"
        
        valid_exchanges = ["blofin", "binance", "bybit", "mexc", "kucoin", "kraken"]
        if exchange not in valid_exchanges:
            await message.channel.send(f"❌ Invalid exchange. Use: {', '.join(valid_exchanges)}")
            return
        
        try:
            async with self.session.get(f"{self.api_base}/watchlist/{exchange}") as response:
                if response.status == 200:
                    data = await response.json()
                    symbols = data.get('symbols', [])
                    
                    # Split into chunks for Discord's field limit
                    chunks = [symbols[i:i+30] for i in range(0, len(symbols), 30)]
                    
                    embed = discord.Embed(
                        title=f"📋 {exchange.upper()} Watchlist",
                        description=f"Total: {len(symbols)} trading pairs",
                        color=discord.Color.blue(),
                        timestamp=datetime.utcnow()
                    )
                    
                    # Show first 30 symbols
                    if chunks:
                        embed.add_field(
                            name="Symbols (first 30)",
                            value=", ".join(chunks[0]),
                            inline=False
                        )
                    
                    embed.set_footer(text="Use on TradingView for multi-exchange charts")
                    await message.channel.send(embed=embed)
                else:
                    await message.channel.send(f"❌ Failed to fetch {exchange} watchlist")
                    
        except Exception as e:
            await message.channel.send(f"❌ Error: {str(e)}")
    
    async def show_help(self, message):
        """Show available commands"""
        embed = discord.Embed(
            title="📚 CryptoWatch Bot Commands",
            description="Real-time crypto funding rates and market data",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="Funding Rate Commands",
            value=(
                "`!funding` - Most negative funding rates\n"
                "`!turned` - Coins that turned positive\n"
                "`!improving` - Negative but improving rates"
            ),
            inline=False
        )
        
        embed.add_field(
            name="Other Commands",
            value=(
                "`!watchlist [exchange]` - Get exchange symbols\n"
                "`!help` - Show this help message"
            ),
            inline=False
        )
        
        embed.add_field(
            name="Exchanges",
            value="blofin, binance, bybit, mexc, kucoin, kraken",
            inline=False
        )
        
        embed.set_footer(text="Data updates every 30 minutes • Powered by CryptoWatchTools.com")
        await message.channel.send(embed=embed)
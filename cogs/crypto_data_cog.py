"""
Crypto Data Cog - Handles funding rates and market data commands
"""
import discord
from discord.ext import commands
import aiohttp
from datetime import datetime
import logging

logger = logging.getLogger('discord-bot.crypto')

class CryptoDataCog(commands.Cog):
    def __init__(self, bot, config):
        self.bot = bot
        self.config = config
        self.api_base = "https://example.com/api"
        self.session = None
    
    async def cog_load(self):
        """Called when cog is loaded"""
        self.session = aiohttp.ClientSession()
        logger.info("Crypto data cog loaded")
    
    async def cog_unload(self):
        """Cleanup when cog is unloaded"""
        if self.session:
            await self.session.close()
    
    @commands.command(name='funding', aliases=['f'])
    async def funding_rates(self, ctx, limit: int = 10):
        """Show most negative funding rates
        Usage: !funding [limit]
        """
        try:
            async with self.session.get(f"{self.api_base}/most-negative") as response:
                if response.status == 200:
                    data = await response.json()
                    rates = data.get('rates', [])[:limit]
                    
                    embed = discord.Embed(
                        title="🔴 Most Negative Funding Rates",
                        description=f"Top {len(rates)} coins with most negative funding",
                        color=discord.Color.red(),
                        timestamp=datetime.utcnow()
                    )
                    
                    for i, rate in enumerate(rates, 1):
                        symbol = rate['instId'].replace('-USDT', '')
                        funding = float(rate['currentRate']) * 100
                        embed.add_field(
                            name=f"{i}. {symbol}",
                            value=f"{funding:.4f}%",
                            inline=True
                        )
                    
                    embed.set_footer(text="Data from BloFin • Updates every 30 minutes")
                    await ctx.send(embed=embed)
                else:
                    await ctx.send("❌ Failed to fetch funding rates")
                    
        except Exception as e:
            logger.error(f"Error in funding command: {e}")
            await ctx.send("❌ An error occurred")
    
    @commands.command(name='turned', aliases=['t'])
    async def turned_positive(self, ctx, limit: int = 6):
        """Show coins that turned positive
        Usage: !turned [limit]
        """
        try:
            async with self.session.get(f"{self.api_base}/turned-positive") as response:
                if response.status == 200:
                    data = await response.json()
                    rates = data.get('rates', [])[:limit]
                    
                    if not rates:
                        await ctx.send("📊 No coins have turned positive recently")
                        return
                    
                    embed = discord.Embed(
                        title="🟢 Turned Positive",
                        description="Funding flipped from negative to positive",
                        color=discord.Color.green(),
                        timestamp=datetime.utcnow()
                    )
                    
                    for rate in rates:
                        symbol = rate['instId'].replace('-USDT', '')
                        current = float(rate['currentRate']) * 100
                        previous = float(rate.get('prevRate', 0)) * 100
                        
                        embed.add_field(
                            name=symbol,
                            value=f"Now: {current:.3f}%\nWas: {previous:.3f}%",
                            inline=True
                        )
                    
                    embed.set_footer(text="Potential short squeeze candidates")
                    await ctx.send(embed=embed)
                else:
                    await ctx.send("❌ Failed to fetch data")
                    
        except Exception as e:
            logger.error(f"Error in turned command: {e}")
            await ctx.send("❌ An error occurred")
    
    @commands.command(name='improving', aliases=['i'])
    async def improving_rates(self, ctx, limit: int = 6):
        """Show improving negative rates
        Usage: !improving [limit]
        """
        try:
            async with self.session.get(f"{self.api_base}/improving-negative") as response:
                if response.status == 200:
                    data = await response.json()
                    rates = data.get('rates', [])[:limit]
                    
                    if not rates:
                        await ctx.send("📊 No improving negative rates found")
                        return
                    
                    embed = discord.Embed(
                        title="📈 Improving Negative Rates",
                        description="Still negative but moving up",
                        color=discord.Color.orange(),
                        timestamp=datetime.utcnow()
                    )
                    
                    for rate in rates:
                        symbol = rate['instId'].replace('-USDT', '')
                        current = float(rate['currentRate']) * 100
                        change = float(rate.get('rateChange', 0)) * 100
                        
                        embed.add_field(
                            name=symbol,
                            value=f"{current:.3f}%\n↗️ +{change:.3f}%",
                            inline=True
                        )
                    
                    embed.set_footer(text="Watch for potential reversal")
                    await ctx.send(embed=embed)
                else:
                    await ctx.send("❌ Failed to fetch data")
                    
        except Exception as e:
            logger.error(f"Error in improving command: {e}")
            await ctx.send("❌ An error occurred")
    
    @commands.command(name='scanner', aliases=['scan'])
    async def funding_scanner(self, ctx):
        """Show comprehensive funding scanner data
        Usage: !scanner
        """
        try:
            async with self.session.get(f"{self.api_base}/funding-scanner-data") as response:
                if response.status == 200:
                    data = await response.json()
                    
                    embed = discord.Embed(
                        title="🔍 Funding Scanner Overview",
                        description="Complete market funding analysis",
                        color=discord.Color.gold(),
                        timestamp=datetime.utcnow()
                    )
                    
                    # Add statistics if available
                    stats = data.get('stats')
                    if stats:
                        embed.add_field(
                            name="📊 Market Stats",
                            value=(
                                f"Total Coins: {stats.get('total_coins', 0)}\n"
                                f"Negative: {stats.get('negative_count', 0)}\n"
                                f"Extreme (<-0.1%): {stats.get('extreme_negative', 0)}"
                            ),
                            inline=True
                        )
                    
                    # Top movers
                    rates = data.get('rates', [])
                    if rates:
                        # Most negative
                        top_negative = sorted(rates, key=lambda x: float(x.get('currentRate', 0)))[:3]
                        if top_negative:
                            value = "\n".join([
                                f"{r['instId'].replace('-USDT', '')}: {float(r['currentRate'])*100:.3f}%"
                                for r in top_negative
                            ])
                            embed.add_field(name="🔴 Most Negative", value=value, inline=True)
                        
                        # Biggest changes
                        biggest_changes = sorted(rates, 
                            key=lambda x: abs(float(x.get('rateChange', 0))), 
                            reverse=True
                        )[:3]
                        if biggest_changes:
                            value = "\n".join([
                                f"{r['instId'].replace('-USDT', '')}: {float(r.get('rateChange', 0))*100:+.3f}%"
                                for r in biggest_changes
                            ])
                            embed.add_field(name="🚀 Biggest Moves", value=value, inline=True)
                    
                    embed.set_footer(text="Use specific commands for detailed views")
                    await ctx.send(embed=embed)
                else:
                    await ctx.send("❌ Failed to fetch scanner data")
                    
        except Exception as e:
            logger.error(f"Error in scanner command: {e}")
            await ctx.send("❌ An error occurred")
    
    @commands.command(name='worsening', aliases=['w'])
    async def worsening_rates(self, ctx, limit: int = 6):
        """Show worsening negative rates
        Usage: !worsening [limit]
        """
        try:
            async with self.session.get(f"{self.api_base}/worsening-negative") as response:
                if response.status == 200:
                    data = await response.json()
                    rates = data.get('rates', [])[:limit]
                    
                    if not rates:
                        await ctx.send("📊 No worsening negative rates found")
                        return
                    
                    embed = discord.Embed(
                        title="📉 Worsening Negative Rates",
                        description="Getting more negative - potential shorts building",
                        color=discord.Color.dark_red(),
                        timestamp=datetime.utcnow()
                    )
                    
                    for rate in rates:
                        symbol = rate['instId'].replace('-USDT', '')
                        current = float(rate['currentRate']) * 100
                        change = float(rate.get('rateChange', 0)) * 100
                        
                        embed.add_field(
                            name=symbol,
                            value=f"{current:.3f}%\n↘️ {change:.3f}%",
                            inline=True
                        )
                    
                    embed.set_footer(text="More shorts entering = potential squeeze later")
                    await ctx.send(embed=embed)
                else:
                    await ctx.send("❌ Failed to fetch data")
                    
        except Exception as e:
            logger.error(f"Error in worsening command: {e}")
            await ctx.send("❌ An error occurred")
    
    @commands.command(name='cryptohelp', aliases=['ch'])
    async def crypto_help(self, ctx):
        """Show crypto commands help"""
        embed = discord.Embed(
            title="📊 Crypto Data Commands",
            description="Real-time funding rates from CryptoWatchTools",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="Commands",
            value=(
                "`!scanner` - Full market overview\n"
                "`!funding [n]` - Top n most negative rates\n"
                "`!turned [n]` - Coins that turned positive\n"
                "`!improving [n]` - Negative but improving\n"
                "`!worsening [n]` - Getting more negative\n"
            ),
            inline=False
        )
        
        embed.add_field(
            name="Aliases",
            value="`!scan` = scanner, `!f` = funding, `!t` = turned, `!i` = improving, `!w` = worsening",
            inline=False
        )
        
        embed.set_footer(text="Data updates every 30 minutes")
        await ctx.send(embed=embed)

async def setup(bot):
    # This allows the cog to be loaded dynamically
    pass
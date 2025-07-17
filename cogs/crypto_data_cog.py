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
        self.api_base = "https://cryptowatchtools.com/api"
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
                        symbol = rate['inst_id'].replace('-USDT', '')
                        funding = rate['current_rate'] * 100
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
                        symbol = rate['inst_id'].replace('-USDT', '')
                        current = rate['current_rate'] * 100
                        previous = rate.get('prev_rate', 0) * 100
                        
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
                        symbol = rate['inst_id'].replace('-USDT', '')
                        current = rate['current_rate'] * 100
                        change = rate.get('rate_change', 0) * 100
                        
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
                "`!funding [n]` - Top n most negative rates\n"
                "`!turned [n]` - Coins that turned positive\n"
                "`!improving [n]` - Negative but improving\n"
            ),
            inline=False
        )
        
        embed.add_field(
            name="Aliases",
            value="`!f` = funding, `!t` = turned, `!i` = improving",
            inline=False
        )
        
        embed.set_footer(text="Data updates every 30 minutes")
        await ctx.send(embed=embed)

async def setup(bot):
    # This allows the cog to be loaded dynamically
    pass
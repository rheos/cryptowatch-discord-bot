import discord
from discord.ext import commands, tasks
import aiohttp
import json
from datetime import datetime

# Bot configuration
bot = commands.Bot(command_prefix='!')
API_BASE_URL = "https://cryptowatchtools.com/api"  # Your production URL

class CryptoData(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.session = None
        
    async def cog_load(self):
        self.session = aiohttp.ClientSession()
        
    async def cog_unload(self):
        if self.session:
            await self.session.close()
    
    @commands.command(name='funding')
    async def get_funding_rates(self, ctx, limit: int = 5):
        """Get most negative funding rates"""
        try:
            async with self.session.get(f"{API_BASE_URL}/most-negative") as response:
                if response.status == 200:
                    data = await response.json()
                    rates = data.get('rates', [])[:limit]
                    
                    embed = discord.Embed(
                        title="🔴 Most Negative Funding Rates",
                        color=discord.Color.red(),
                        timestamp=datetime.utcnow()
                    )
                    
                    for rate in rates:
                        embed.add_field(
                            name=f"{rate['inst_id']}",
                            value=f"Rate: {rate['current_rate']:.4%}",
                            inline=True
                        )
                    
                    await ctx.send(embed=embed)
                else:
                    await ctx.send("Failed to fetch funding rates")
                    
        except Exception as e:
            await ctx.send(f"Error: {str(e)}")
    
    @commands.command(name='turned')
    async def get_turned_positive(self, ctx, limit: int = 5):
        """Get coins that turned positive from negative"""
        try:
            async with self.session.get(f"{API_BASE_URL}/turned-positive") as response:
                if response.status == 200:
                    data = await response.json()
                    rates = data.get('rates', [])[:limit]
                    
                    embed = discord.Embed(
                        title="🟢 Turned Positive",
                        color=discord.Color.green(),
                        timestamp=datetime.utcnow()
                    )
                    
                    for rate in rates:
                        change = rate.get('rate_change', 0)
                        embed.add_field(
                            name=f"{rate['inst_id']}",
                            value=f"Now: {rate['current_rate']:.4%}\nChange: +{change:.4%}",
                            inline=True
                        )
                    
                    await ctx.send(embed=embed)
                else:
                    await ctx.send("Failed to fetch data")
                    
        except Exception as e:
            await ctx.send(f"Error: {str(e)}")
    
    @commands.command(name='watchlist')
    async def get_watchlist(self, ctx, exchange: str = "blofin"):
        """Get watchlist for an exchange"""
        try:
            async with self.session.get(f"{API_BASE_URL}/watchlist/{exchange}") as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Create a file with the watchlist
                    watchlist_text = "\n".join(data.get('symbols', []))
                    
                    # Send as a file
                    file = discord.File(
                        io.StringIO(watchlist_text),
                        filename=f"{exchange}_watchlist.txt"
                    )
                    
                    await ctx.send(
                        f"📋 {exchange.upper()} Watchlist ({len(data.get('symbols', []))} symbols)",
                        file=file
                    )
                else:
                    await ctx.send(f"Failed to fetch {exchange} watchlist")
                    
        except Exception as e:
            await ctx.send(f"Error: {str(e)}")

# Auto-update channel with funding data
class AutoUpdater(commands.Cog):
    def __init__(self, bot, channel_id):
        self.bot = bot
        self.channel_id = channel_id
        self.session = None
        self.update_funding_channel.start()
        
    async def cog_load(self):
        self.session = aiohttp.ClientSession()
        
    async def cog_unload(self):
        self.update_funding_channel.cancel()
        if self.session:
            await self.session.close()
    
    @tasks.loop(minutes=30)  # Update every 30 minutes
    async def update_funding_channel(self):
        channel = self.bot.get_channel(self.channel_id)
        if not channel:
            return
            
        try:
            async with self.session.get(f"{API_BASE_URL}/most-negative") as response:
                if response.status == 200:
                    data = await response.json()
                    rates = data.get('rates', [])[:10]
                    
                    embed = discord.Embed(
                        title="🔴 Live Funding Rates",
                        description="Most negative funding rates right now",
                        color=discord.Color.red(),
                        timestamp=datetime.utcnow()
                    )
                    
                    for i, rate in enumerate(rates, 1):
                        embed.add_field(
                            name=f"{i}. {rate['inst_id']}",
                            value=f"{rate['current_rate']:.4%}",
                            inline=True
                        )
                    
                    # Update pinned message or create new one
                    async for message in channel.history(limit=10):
                        if message.author == self.bot.user and message.pinned:
                            await message.edit(embed=embed)
                            return
                    
                    # No pinned message found, create one
                    msg = await channel.send(embed=embed)
                    await msg.pin()
                    
        except Exception as e:
            print(f"Error updating funding channel: {e}")

# Set up bot
async def setup_bot():
    await bot.add_cog(CryptoData(bot))
    # await bot.add_cog(AutoUpdater(bot, CHANNEL_ID))  # Add channel ID for auto-updates

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    await setup_bot()

# Run bot
bot.run('YOUR_BOT_TOKEN')
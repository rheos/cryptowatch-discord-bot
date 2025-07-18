"""
Auto Updates Cog - Posts scheduled crypto updates to specified channels
"""
import discord
from discord.ext import commands, tasks
import aiohttp
from datetime import datetime
import logging

logger = logging.getLogger('discord-bot.auto-updates')

class AutoUpdatesCog(commands.Cog):
    def __init__(self, bot, config):
        self.bot = bot
        self.config = config
        self.api_base = "https://example.com/api"
        self.session = None
        
        # Get update channels from config
        self.funding_channel_id = config.get("auto_update_channels", {}).get("funding")
        self.alerts_channel_id = config.get("auto_update_channels", {}).get("alerts")
        
        # Start scheduled tasks if channels are configured
        if self.funding_channel_id:
            self.update_funding_summary.start()
        if self.alerts_channel_id:
            self.check_extreme_rates.start()
    
    async def cog_load(self):
        self.session = aiohttp.ClientSession()
    
    async def cog_unload(self):
        self.update_funding_summary.cancel()
        self.check_extreme_rates.cancel()
        if self.session:
            await self.session.close()
    
    @tasks.loop(hours=4)  # Every 4 hours
    async def update_funding_summary(self):
        """Post funding rate summary to designated channel"""
        channel = self.bot.get_channel(self.funding_channel_id)
        if not channel:
            return
        
        try:
            async with self.session.get(f"{self.api_base}/most-negative") as response:
                if response.status == 200:
                    data = await response.json()
                    rates = data.get('rates', [])[:20]
                    
                    embed = discord.Embed(
                        title="📊 Funding Rate Summary",
                        description=f"Top 20 negative funding rates at {datetime.utcnow().strftime('%H:%M UTC')}",
                        color=discord.Color.blue(),
                        timestamp=datetime.utcnow()
                    )
                    
                    # Split into negative and improving
                    very_negative = [r for r in rates if float(r['currentRate']) < -0.001]  # < -0.1%
                    moderate = [r for r in rates if -0.001 <= float(r['currentRate']) < -0.0005]
                    
                    if very_negative:
                        symbols = [r['instId'].replace('-USDT', '') for r in very_negative[:8]]
                        embed.add_field(
                            name="🔴 Extreme Negative (< -0.1%)",
                            value=", ".join(symbols),
                            inline=False
                        )
                    
                    if moderate:
                        symbols = [r['instId'].replace('-USDT', '') for r in moderate[:8]]
                        embed.add_field(
                            name="🟡 Moderate Negative",
                            value=", ".join(symbols),
                            inline=False
                        )
                    
                    # Check for any that turned positive
                    async with self.session.get(f"{self.api_base}/turned-positive") as resp2:
                        if resp2.status == 200:
                            turned_data = await resp2.json()
                            turned = turned_data.get('rates', [])[:5]
                            if turned:
                                symbols = [r['instId'].replace('-USDT', '') for r in turned]
                                embed.add_field(
                                    name="🟢 Recently Turned Positive",
                                    value=", ".join(symbols),
                                    inline=False
                                )
                    
                    embed.set_footer(text="Use !funding for detailed rates")
                    await channel.send(embed=embed)
                    
        except Exception as e:
            logger.error(f"Error in funding summary update: {e}")
    
    @tasks.loop(minutes=30)  # Every 30 minutes
    async def check_extreme_rates(self):
        """Alert on extreme funding rate changes"""
        channel = self.bot.get_channel(self.alerts_channel_id)
        if not channel:
            return
        
        try:
            # Check for extreme negative rates
            async with self.session.get(f"{self.api_base}/most-negative") as response:
                if response.status == 200:
                    data = await response.json()
                    rates = data.get('rates', [])
                    
                    # Alert if any coin has funding < -0.2%
                    extreme = [r for r in rates if float(r['currentRate']) < -0.002]
                    
                    if extreme:
                        embed = discord.Embed(
                            title="⚠️ Extreme Funding Alert",
                            description="Coins with funding rates below -0.2%",
                            color=discord.Color.red(),
                            timestamp=datetime.utcnow()
                        )
                        
                        for rate in extreme[:5]:
                            symbol = rate['instId'].replace('-USDT', '')
                            funding = float(rate['currentRate']) * 100
                            embed.add_field(
                                name=symbol,
                                value=f"{funding:.3f}%",
                                inline=True
                            )
                        
                        embed.set_footer(text="Potential volatility ahead")
                        
                        # Only send if we haven't alerted about these in last 2 hours
                        # (You'd implement alert tracking here)
                        await channel.send(embed=embed)
            
            # Check for coins that just turned positive
            async with self.session.get(f"{self.api_base}/turned-positive") as response:
                if response.status == 200:
                    data = await response.json()
                    turned = data.get('rates', [])
                    
                    # Alert if high-change turnarounds
                    big_turns = [r for r in turned if r.get('rate_change', 0) > 0.003]  # >0.3% swing
                    
                    if big_turns:
                        embed = discord.Embed(
                            title="🚀 Funding Flip Alert",
                            description="Large funding rate reversals detected",
                            color=discord.Color.green(),
                            timestamp=datetime.utcnow()
                        )
                        
                        for rate in big_turns[:3]:
                            symbol = rate['inst_id'].replace('-USDT', '')
                            change = rate.get('rate_change', 0) * 100
                            embed.add_field(
                                name=symbol,
                                value=f"↗️ +{change:.3f}% swing",
                                inline=True
                            )
                        
                        await channel.send(embed=embed)
                        
        except Exception as e:
            logger.error(f"Error in extreme rates check: {e}")
    
    @update_funding_summary.before_loop
    async def before_funding_summary(self):
        await self.bot.wait_until_ready()
    
    @check_extreme_rates.before_loop
    async def before_extreme_check(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    pass
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
        self.api_base = "https://cryptowatchtools.com/api"
        self.session = None
        
        # Get update channels from config
        self.funding_channel_id = config.get("auto_update_channels", {}).get("funding")
        self.alerts_channel_id = config.get("auto_update_channels", {}).get("alerts")
        
        # Track last funding update times
        self.last_funding_time = None
        self.last_alert_symbols = set()  # Track alerted symbols to avoid spam
        self.last_alert_time = None  # Track when we last sent alerts
        
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
    
    @tasks.loop(minutes=15)  # Check every 15 minutes for new data (funding updates every 8 hours)
    async def update_funding_summary(self):
        """Check for new funding data and post summary if updated
        
        Note: BloFin funding rates typically update every 8 hours (00:00, 08:00, 16:00 UTC)
        but different coins may update at different times, so we check frequently.
        """
        channel = self.bot.get_channel(self.funding_channel_id)
        if not channel:
            return
        
        try:
            async with self.session.get(f"{self.api_base}/most-negative") as response:
                if response.status == 200:
                    data = await response.json()
                    rates = data.get('rates', [])
                    
                    # Check if we have new funding data
                    if rates:
                        # Get the latest funding time from the data
                        latest_funding_time = max(
                            rate.get('fundingTime', 0) for rate in rates if rate.get('fundingTime')
                        )
                        
                        # Skip if we've already posted this funding update
                        if self.last_funding_time and latest_funding_time <= self.last_funding_time:
                            logger.debug(f"Checked for updates - no new funding data since {datetime.fromtimestamp(self.last_funding_time/1000)} UTC")
                            return
                        
                        logger.info(f"New funding data available! Last: {datetime.fromtimestamp(self.last_funding_time/1000) if self.last_funding_time else 'Never'}, Current: {datetime.fromtimestamp(latest_funding_time/1000)} UTC")
                        
                        self.last_funding_time = latest_funding_time
                    
                    rates = rates[:20]
                    
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
                    
                    embed.set_footer(text="Use !negative for detailed rates")
                    await channel.send(embed=embed)
                    logger.info(f"Posted funding summary - latest data from {datetime.fromtimestamp(latest_funding_time/1000)} UTC")
                    
        except Exception as e:
            logger.error(f"Error in funding summary update: {e}")
    
    @tasks.loop(minutes=15)  # Check every 15 minutes for new data
    async def check_extreme_rates(self):
        """Check for extreme funding rates and alert if new"""
        channel = self.bot.get_channel(self.alerts_channel_id)
        if not channel:
            return
        
        try:
            # Check for extreme negative rates
            async with self.session.get(f"{self.api_base}/most-negative") as response:
                if response.status == 200:
                    data = await response.json()
                    rates = data.get('rates', [])
                    
                    # Check if we have new funding data
                    if rates:
                        latest_funding_time = max(
                            rate.get('fundingTime', 0) for rate in rates if rate.get('fundingTime')
                        )
                        
                        # Skip if this is old data we've already seen
                        if self.last_funding_time and latest_funding_time <= self.last_funding_time:
                            logger.debug(f"No new extreme rate data since {datetime.fromtimestamp(self.last_funding_time/1000)} UTC")
                            return
                    
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
                        
                        # Reset alert tracking after 2 hours
                        now = datetime.utcnow()
                        if self.last_alert_time and (now - self.last_alert_time).total_seconds() > 7200:
                            self.last_alert_symbols = set()
                            self.last_alert_time = None
                            logger.info("Reset alert tracking after 2 hours")
                        
                        # Only send if we have new extreme rates
                        extreme_symbols = {r['instId'] for r in extreme}
                        if not extreme_symbols.issubset(self.last_alert_symbols):
                            await channel.send(embed=embed)
                            # Update tracked symbols
                            self.last_alert_symbols = extreme_symbols
                            self.last_alert_time = now
                            logger.info(f"Sent extreme funding alert for: {', '.join(s.replace('-USDT', '') for s in extreme_symbols)}")
                        else:
                            logger.debug("Skipping extreme alert - no new symbols")
            
            # Check for coins that just turned positive
            async with self.session.get(f"{self.api_base}/turned-positive") as response:
                if response.status == 200:
                    data = await response.json()
                    turned = data.get('rates', [])
                    
                    # Alert if high-change turnarounds (using changes.prev.change)
                    big_turns = []
                    for r in turned:
                        prev_change = r.get('changes', {}).get('prev', {}).get('change', 0)
                        if float(prev_change) > 0.003:  # >0.3% swing
                            big_turns.append(r)
                    
                    if big_turns:
                        embed = discord.Embed(
                            title="🚀 Funding Flip Alert",
                            description="Large funding rate reversals detected",
                            color=discord.Color.green(),
                            timestamp=datetime.utcnow()
                        )
                        
                        for rate in big_turns[:3]:
                            symbol = rate['instId'].replace('-USDT', '')
                            change = float(rate.get('changes', {}).get('prev', {}).get('change', 0)) * 100
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
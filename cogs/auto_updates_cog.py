"""
Auto Updates Cog - Posts scheduled crypto updates to specified channels
"""
import discord
from discord.ext import commands, tasks
import aiohttp
from datetime import datetime, timedelta
import logging
from utils.message_cleanup import cleanup_before_send, find_last_bot_message

logger = logging.getLogger('discord-bot.auto-updates')

class AutoUpdatesCog(commands.Cog):
    def __init__(self, bot, config):
        self.bot = bot
        self.config = config
        self.api_base = "https://example.com/api"
        self.session = None
        
        # Channel IDs will be loaded from database in cog_load
        self.funding_channel_id = None
        self.alerts_channel_id = None
        
        # Track last rates snapshot to detect changes
        self.last_rates_snapshot = {}  # {symbol: rate} to detect rate changes
        self.last_funding_time = None  # Still track for logging
        self.last_alert_symbols = set()  # Track alerted symbols to avoid spam
        self.last_alert_time = None  # Track when we last sent alerts
        
        # Track funding flip alerts to prevent duplicates
        self.recent_flip_alerts = {}  # {symbol: (change_value, alert_time)}
    
    async def cog_load(self):
        self.session = aiohttp.ClientSession()
        
        # Start the tasks - they'll load channels when ready
        self.update_funding_summary.start()
        self.check_extreme_rates.start()
        logger.info("AutoUpdatesCog initialized, tasks will load channels when bot is ready")
    
    async def load_channels_from_db(self):
        """Load channel IDs from database after bot is ready"""
        # Get channel IDs from database for the first guild
        # (This assumes single-guild bot, for multi-guild would need to iterate)
        if self.bot.guilds:
            guild = self.bot.guilds[0]
            
            # Get funding alerts channel
            funding_channel_id = await self.bot.db.get_setting(guild.id, 'funding_alerts')
            if funding_channel_id:
                self.funding_channel_id = int(funding_channel_id)
                logger.info(f"Funding alerts channel configured: {self.funding_channel_id}")
            else:
                logger.info("No funding alerts channel configured in database")
            
            # Get general alerts channel  
            alerts_channel_id = await self.bot.db.get_setting(guild.id, 'general_alerts')
            if alerts_channel_id:
                self.alerts_channel_id = int(alerts_channel_id)
                logger.info(f"General alerts channel configured: {self.alerts_channel_id}")
            else:
                logger.info("No general alerts channel configured in database")
    
    async def cog_unload(self):
        self.update_funding_summary.cancel()
        self.check_extreme_rates.cancel()
        if self.session:
            await self.session.close()
    
    @tasks.loop(minutes=30)  # Check every 30 minutes for rate changes
    async def update_funding_summary(self):
        """Check for funding rate changes and post summary if updated
        
        Note: Funding rates can change dynamically throughout the day,
        not just at the 8-hour settlement times.
        """
        channel = self.bot.get_channel(self.funding_channel_id)
        if not channel:
            return
        
        try:
            async with self.session.get(f"{self.api_base}/most-negative") as response:
                if response.status == 200:
                    data = await response.json()
                    rates = data.get('rates', [])
                    
                    # Check if we have rate changes (not just funding time changes)
                    current_snapshot = {}
                    has_changes = False
                    
                    for rate in rates:
                        symbol = rate['instId']
                        current_rate = float(rate['currentRate'])
                        current_snapshot[symbol] = current_rate
                        
                        # Check if this rate has changed significantly (at least 0.01% change)
                        if symbol in self.last_rates_snapshot:
                            last_rate = self.last_rates_snapshot[symbol]
                            if abs(current_rate - last_rate) > 0.0001:  # 0.01% minimum change
                                has_changes = True
                                logger.debug(f"{symbol}: rate changed from {last_rate:.6f} to {current_rate:.6f}")
                        else:
                            # New symbol we haven't seen before
                            has_changes = True
                    
                    # If no changes detected, skip update
                    if self.last_rates_snapshot and not has_changes:
                        logger.debug("No rate changes detected")
                        return
                    
                    # Update our snapshot
                    self.last_rates_snapshot = current_snapshot
                    
                    # Track funding time for logging
                    if rates:
                        latest_funding_time = max(
                            rate.get('fundingTime', 0) for rate in rates if rate.get('fundingTime')
                        )
                        self.last_funding_time = latest_funding_time
                        logger.info(f"Rate changes detected! Funding time: {datetime.fromtimestamp(latest_funding_time/1000)} UTC")
                    
                    rates = rates[:20]
                    
                    embed = discord.Embed(
                        title="📊 Funding Rate Summary",
                        description=f"Top 20 negative funding rates at {datetime.utcnow().strftime('%H:%M UTC')}",
                        color=discord.Color.blue(),
                        timestamp=datetime.utcnow()
                    )
                    
                    # Split into categories
                    very_negative = [r for r in rates if float(r['currentRate']) < -0.001]  # < -0.1%
                    
                    if very_negative:
                        symbols = [r['instId'] for r in very_negative[:8]]
                        embed.add_field(
                            name="🔴 Extreme Negative (< -0.1%)",
                            value=", ".join(symbols),
                            inline=False
                        )
                    
                    # Get worsening and improving rates
                    async with self.session.get(f"{self.api_base}/worsening-negative") as resp_worse:
                        if resp_worse.status == 200:
                            worse_data = await resp_worse.json()
                            worsening = worse_data.get('rates', [])[:8]
                            if worsening:
                                symbols = [r['instId'] for r in worsening]
                                embed.add_field(
                                    name="📉 Worsening Negative",
                                    value=", ".join(symbols),
                                    inline=False
                                )
                    
                    async with self.session.get(f"{self.api_base}/improving-negative") as resp_improve:
                        if resp_improve.status == 200:
                            improve_data = await resp_improve.json()
                            improving = improve_data.get('rates', [])[:8]
                            if improving:
                                symbols = [r['instId'] for r in improving]
                                embed.add_field(
                                    name="📈 Improving Negative",
                                    value=", ".join(symbols),
                                    inline=False
                                )
                    
                    # Check for any that turned positive
                    async with self.session.get(f"{self.api_base}/turned-positive") as resp2:
                        if resp2.status == 200:
                            turned_data = await resp2.json()
                            turned = turned_data.get('rates', [])[:5]
                            if turned:
                                symbols = [r['instId'] for r in turned]
                                embed.add_field(
                                    name="🟢 Recently Turned Positive",
                                    value=", ".join(symbols),
                                    inline=False
                                )
                    
                    embed.set_footer(text="Use /funding for detailed rates")
                    
                    # Try to find and edit the last funding summary message
                    logger.debug(f"Looking for last funding summary message in #{channel.name}")
                    last_message = await find_last_bot_message(
                        channel,
                        self.bot.user.id,
                        embed_check="Funding Rate Summary",
                        max_age_hours=None  # No age limit - keep editing the same message indefinitely
                    )
                    
                    if last_message:
                        # Edit the existing message
                        await last_message.edit(embed=embed)
                        message_age = (datetime.utcnow() - last_message.created_at.replace(tzinfo=None)).total_seconds() / 3600
                        logger.info(f"Updated existing funding summary (message age: {message_age:.1f}h) - latest data from {datetime.fromtimestamp(latest_funding_time/1000)} UTC")
                    else:
                        # No existing message or too old, create new one
                        await channel.send(embed=embed)
                        logger.info(f"Posted new funding summary (no recent message found) - latest data from {datetime.fromtimestamp(latest_funding_time/1000)} UTC")
                    
        except Exception as e:
            logger.error(f"Error in funding summary update: {e}")
    
    @tasks.loop(minutes=15)  # Check every 15 minutes for rate changes
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
                    
                    # Note: We don't check funding time here because rates can change
                    # dynamically. Instead we track which symbols we've alerted on below.
                    
                    # Alert if any coin has funding < -0.5%
                    extreme = [r for r in rates if float(r['currentRate']) < -0.005]
                    
                    if extreme:
                        embed = discord.Embed(
                            title="⚠️ Extreme Funding Alert",
                            description="Coins with funding rates below -0.5%",
                            color=discord.Color.red(),
                            timestamp=datetime.utcnow()
                        )
                        
                        for rate in extreme[:5]:
                            symbol = rate['instId']
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
                            logger.info(f"Sent extreme funding alert for: {', '.join(extreme_symbols)}")
                            
                            # Clean up old messages after sending new alert
                            try:
                                logger.debug(f"Starting cleanup of messages older than 4 hours in #{channel.name}")
                                deleted = await cleanup_before_send(channel, max_age_hours=4, bot_id=self.bot.user.id)
                                if deleted > 0:
                                    logger.info(f"Cleaned up {deleted} old alert messages")
                                else:
                                    logger.debug("No old messages to clean up")
                            except Exception as e:
                                logger.warning(f"Failed to cleanup old messages: {e}")
                        else:
                            logger.debug("Skipping extreme alert - no new symbols")
            
            # Check for coins that just turned positive
            async with self.session.get(f"{self.api_base}/turned-positive") as response:
                if response.status == 200:
                    data = await response.json()
                    turned = data.get('rates', [])
                    
                    # Alert if high-change turnarounds (using changes.prev.change)
                    big_turns = []
                    current_time = datetime.utcnow()
                    
                    for r in turned:
                        prev_change = r.get('changes', {}).get('prev', {}).get('change', 0)
                        if float(prev_change) > 0.01:  # >1% swing
                            symbol = r['instId']
                            
                            # Check if we've alerted this symbol recently
                            if symbol in self.recent_flip_alerts:
                                last_change, last_time = self.recent_flip_alerts[symbol]
                                time_diff = (current_time - last_time).total_seconds()
                                
                                # Skip if same alert within 1 hour
                                if time_diff < 3600 and abs(float(prev_change) - last_change) < 0.001:
                                    logger.debug(f"Skipping duplicate flip alert for {symbol}")
                                    continue
                            
                            big_turns.append(r)
                    
                    if big_turns:
                        embed = discord.Embed(
                            title="🚀 Funding Flip Alert",
                            description="Large funding rate reversals detected",
                            color=discord.Color.green(),
                            timestamp=datetime.utcnow()
                        )
                        
                        for rate in big_turns[:3]:
                            symbol = rate['instId']
                            change = float(rate.get('changes', {}).get('prev', {}).get('change', 0))
                            change_pct = change * 100
                            embed.add_field(
                                name=symbol,
                                value=f"↗️ +{change_pct:.3f}% swing",
                                inline=True
                            )
                            # Update cache to prevent duplicate alerts
                            self.recent_flip_alerts[symbol] = (change, current_time)
                        
                        await channel.send(embed=embed)
                        
                        # Clean up old messages after sending new alert
                        try:
                            logger.debug(f"Starting cleanup of messages older than 4 hours in #{channel.name}")
                            deleted = await cleanup_before_send(channel, max_age_hours=4, bot_id=self.bot.user.id)
                            if deleted > 0:
                                logger.info(f"Cleaned up {deleted} old alert messages")
                            else:
                                logger.debug("No old messages to clean up")
                        except Exception as e:
                            logger.warning(f"Failed to cleanup old messages: {e}")
                        
                        # Clean up old alerts (older than 2 hours)
                        cutoff_time = current_time - timedelta(hours=2)
                        self.recent_flip_alerts = {
                            sym: (chg, time) for sym, (chg, time) in self.recent_flip_alerts.items()
                            if time > cutoff_time
                        }
                        
        except Exception as e:
            logger.error(f"Error in extreme rates check: {e}")
    
    @update_funding_summary.before_loop
    async def before_funding_summary(self):
        await self.bot.wait_until_ready()
        # Load channels on first run
        if self.funding_channel_id is None:
            await self.load_channels_from_db()
    
    @check_extreme_rates.before_loop
    async def before_extreme_check(self):
        await self.bot.wait_until_ready()
        # Load channels on first run  
        if self.alerts_channel_id is None:
            await self.load_channels_from_db()

async def setup(bot):
    pass
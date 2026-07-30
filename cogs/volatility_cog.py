"""
Volatility Scanner Commands for Discord Bot
"""
import discord
from discord.ext import commands, tasks
import aiohttp
import asyncio
from datetime import datetime
import logging
from typing import Dict, List, Optional
from utils.message_cleanup import cleanup_before_send

logger = logging.getLogger('discord-bot.volatility')

class VolatilityCog(commands.Cog):
    """Commands for crypto volatility scanning"""
    
    def __init__(self, bot, config):
        self.bot = bot
        self.config = config
        # Read API base from config (Docker: http://app:5173/api, prod: https://cryptowatchtools.com/api)
        api_base = config.get('api_base_url', 'https://cryptowatchtools.com/api')
        self.base_url = f"{api_base}/volatility-scanner"
        self.session = None
        self.sent_alerts = {}  # Track alerts: {symbol: highest_timeframe_hours}
        self.volatility_alerts.start()
        logger.info("VolatilityCog initialized and alert loop started")
        
    def cog_unload(self):
        self.volatility_alerts.cancel()
        if self.session:
            asyncio.create_task(self.session.close())
    
    async def fetch_volatility_data(self, thresholds: Dict[str, float]) -> Optional[dict]:
        """Fetch volatility data from API"""
        if not self.session:
            self.session = aiohttp.ClientSession()
            
        try:
            # Build query parameters
            params = {}
            for timeframe, percent in thresholds.items():
                params[timeframe] = str(percent)
                
            async with self.session.get(self.base_url, params=params) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(f"API returned status {response.status}")
                    return None
        except Exception as e:
            logger.error(f"Error fetching volatility data: {e}")
            return None
    
    @commands.command(name='volatility', aliases=['vola', 'move'])
    async def volatility(self, ctx, timeframe: str = '1h', threshold: float = 5.0):
        """
        Check for volatile coins
        Usage: !volatility [timeframe] [threshold]
        Example: !volatility 1h 5
        """
        # Validate timeframe
        valid_timeframes = ['5m', '15m', '30m', '45m', '1h', '2h', '3h', '4h', '6h', '12h', '24h', '48h']
        if timeframe not in valid_timeframes:
            await ctx.send(f"Invalid timeframe. Choose from: {', '.join(valid_timeframes)}")
            return
            
        # Fetch data
        data = await self.fetch_volatility_data({timeframe: threshold})
        if not data or not data.get('success'):
            await ctx.send("Failed to fetch volatility data.")
            return
            
        # Find the matching threshold data
        threshold_data = None
        for t in data['thresholds']:
            # Convert hours to timeframe string
            hours = t['hours']
            if hours < 1:
                tf = f"{int(hours * 60)}m"
            else:
                tf = f"{int(hours)}h"
                
            if tf == timeframe:
                threshold_data = t
                break
                
        if not threshold_data or not threshold_data['coins']:
            await ctx.send(f"No coins found with ≥{threshold}% movement in {timeframe}")
            return
            
        # Build response
        embed = discord.Embed(
            title=f"🎢 Volatile Coins - {timeframe}",
            description=f"Coins with ≥{threshold}% price movement",
            color=discord.Color.gold(),
            timestamp=datetime.utcnow()
        )
        
        # Sort by absolute percent change
        coins = sorted(threshold_data['coins'], 
                      key=lambda x: abs(float(x['percentChange'])), 
                      reverse=True)[:10]  # Top 10
        
        for coin in coins:
            percent = float(coin['percentChange'])
            emoji = "📈" if percent > 0 else "📉"
            color_indicator = "🟢" if percent > 0 else "🔴"
            
            embed.add_field(
                name=f"{emoji} {coin['symbol']}",
                value=f"{color_indicator} {percent:.2f}%\n"
                      f"${float(coin['currentPrice']):.4f}",
                inline=True
            )
        
        embed.set_footer(text="Data from CryptoWatchTools")
        await ctx.send(embed=embed)
    
    @commands.command(name='movers', aliases=['top', 'gainers'])
    async def top_movers(self, ctx, timeframe: str = '24h'):
        """
        Show top movers across all timeframes
        Usage: !movers [timeframe]
        """
        # Default thresholds for each timeframe
        default_thresholds = {
            '5m': 2,
            '15m': 3,
            '30m': 4,
            '45m': 4.5,
            '1h': 5,
            '2h': 7,
            '3h': 10,
            '4h': 12,
            '6h': 15,
            '12h': 20,
            '24h': 25,
            '48h': 30
        }
        
        data = await self.fetch_volatility_data(default_thresholds)
        if not data or not data.get('success'):
            await ctx.send("Failed to fetch volatility data.")
            return
            
        embed = discord.Embed(
            title=f"🚀 Top Movers - {timeframe}",
            description="Biggest price movements",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )
        
        # Find the timeframe data
        all_coins = []
        for t in data['thresholds']:
            hours = t['hours']
            if hours < 1:
                tf = f"{int(hours * 60)}m"
            else:
                tf = f"{int(hours)}h"
                
            if tf == timeframe:
                all_coins = t['coins']
                break
        
        if not all_coins:
            await ctx.send(f"No data available for {timeframe}")
            return
            
        # Get top gainers and losers
        sorted_coins = sorted(all_coins, key=lambda x: float(x['percentChange']), reverse=True)
        gainers = [c for c in sorted_coins if float(c['percentChange']) > 0][:5]
        losers = [c for c in sorted_coins if float(c['percentChange']) < 0][-5:]
        
        # Add gainers
        if gainers:
            gainer_text = ""
            for coin in gainers:
                gainer_text += f"**{coin['symbol']}**: +{float(coin['percentChange']):.2f}% (${float(coin['currentPrice']):.4f})\n"
            embed.add_field(name="📈 Top Gainers", value=gainer_text or "None", inline=False)
        
        # Add losers
        if losers:
            loser_text = ""
            for coin in reversed(losers):  # Show biggest losers first
                loser_text += f"**{coin['symbol']}**: {float(coin['percentChange']):.2f}% (${float(coin['currentPrice']):.4f})\n"
            embed.add_field(name="📉 Top Losers", value=loser_text or "None", inline=False)
        
        embed.set_footer(text=f"Threshold: {default_thresholds.get(timeframe, 5)}% | CryptoWatchTools")
        await ctx.send(embed=embed)
    
    @commands.command(name='pricealert', aliases=['pa', 'valert'])
    async def price_alert(self, ctx, symbol: str, timeframe: str = '1h', threshold: float = 10.0):
        """
        Check if a specific coin has moved significantly
        Usage: !pricealert BTC 1h 5
        """
        symbol = symbol.upper()
        
        # Validate timeframe
        valid_timeframes = ['5m', '15m', '30m', '45m', '1h', '2h', '3h', '4h', '6h', '12h', '24h', '48h']
        if timeframe not in valid_timeframes:
            await ctx.send(f"Invalid timeframe. Choose from: {', '.join(valid_timeframes)}")
            return
            
        data = await self.fetch_volatility_data({timeframe: threshold})
        if not data or not data.get('success'):
            await ctx.send("Failed to fetch volatility data.")
            return
            
        # Look for the symbol
        found = False
        for t in data['thresholds']:
            hours = t['hours']
            if hours < 1:
                tf = f"{int(hours * 60)}m"
            else:
                tf = f"{int(hours)}h"
                
            if tf == timeframe:
                for coin in t['coins']:
                    if coin['symbol'] == symbol:
                        found = True
                        percent = float(coin['percentChange'])
                        emoji = "📈" if percent > 0 else "📉"
                        color = discord.Color.green() if percent > 0 else discord.Color.red()
                        
                        embed = discord.Embed(
                            title=f"{emoji} {symbol} Alert",
                            description=f"Significant price movement detected!",
                            color=color,
                            timestamp=datetime.utcnow()
                        )
                        
                        embed.add_field(name="Change", value=f"{percent:+.2f}%", inline=True)
                        embed.add_field(name="Current Price", value=f"${float(coin['currentPrice']):.4f}", inline=True)
                        embed.add_field(name="Start Price", value=f"${float(coin['startPrice']):.4f}", inline=True)
                        embed.add_field(name="Timeframe", value=timeframe, inline=True)
                        embed.add_field(name="Threshold", value=f"{threshold}%", inline=True)
                        
                        await ctx.send(embed=embed)
                        break
                break
                
        if not found:
            await ctx.send(f"{symbol} hasn't moved ≥{threshold}% in the last {timeframe}")
    
    @tasks.loop(minutes=5)
    async def volatility_alerts(self):
        """Run one volatility check per cycle.

        The body is wrapped so a transient error (e.g. a Discord 503 on
        channel.send, or an API blip) is logged and the loop keeps going.
        discord.py permanently STOPS a tasks.loop on any unhandled
        exception, so nothing must be allowed to escape this coroutine.
        """
        try:
            await self._run_volatility_check()
        except Exception as e:
            logger.error(f"volatility_alerts cycle failed (loop continues): {e!r}")

    async def _run_volatility_check(self):
        """Check for extreme volatility and send alerts"""
        logger.info("Volatility alerts loop running...")

        # Get alerts channel from database for first guild (or could iterate all guilds)
        guilds = self.bot.guilds
        if not guilds:
            logger.warning("No guilds connected - skipping volatility check")
            return
            
        # For now, use first guild - could be enhanced to check all guilds
        guild = guilds[0]
        alerts_channel_id = await self.bot.db.get_setting(guild.id, 'general_alerts')
        
        if not alerts_channel_id:
            logger.warning(f"No general_alerts channel configured for guild {guild.id} ({guild.name})")
            return
            
        # Define alert thresholds - matching web app defaults
        alert_thresholds = {
            '5m': 2,      # 2% in 5 minutes - catch early moves
            '15m': 3,     # 3% in 15 minutes
            '1h': 5,      # 5% in 1 hour
            '2h': 7,      # 7% in 2 hours
            '4h': 12,     # 12% in 4 hours
        }
        
        data = await self.fetch_volatility_data(alert_thresholds)
        if not data or not data.get('success'):
            logger.warning(f"Failed to fetch volatility data or API returned error")
            return

        logger.debug(f"Received volatility data with {len(data.get('thresholds', []))} timeframes")
            
        channel_id = int(alerts_channel_id)
        channel = self.bot.get_channel(channel_id)
        if not channel:
            logger.error(f"Alerts channel {channel_id} not found")
            return
            
        # Collect extreme movers
        alerts = []
        current_time = datetime.utcnow()
        
        # Clean up old alerts (older than 24 hours)
        # Remove symbols that haven't had alerts in 24 hours
        cutoff_time = current_time.timestamp() - 86400
        self.sent_alerts = {
            k: v for k, v in self.sent_alerts.items() 
            if v['timestamp'] > cutoff_time
        }
        
        # Map timeframe to hours for comparison
        timeframe_to_hours = {
            '5m': 0.0833,
            '15m': 0.25,
            '1h': 1,
            '2h': 2,
            '4h': 4
        }
        
        for t in data['thresholds']:
            hours = t['hours']
            if hours < 1:
                tf = f"{int(hours * 60)}m"
            else:
                tf = f"{int(hours)}h"
                
            for coin in t['coins']:
                percent_change = float(coin['percentChange'])
                if abs(percent_change) >= alert_thresholds.get(tf, 999):
                    symbol = coin['symbol']
                    
                    # Check if we've already alerted for this symbol
                    if symbol in self.sent_alerts:
                        # Get the highest timeframe we've alerted for
                        prev_timeframe_hours = self.sent_alerts[symbol]['timeframe_hours']
                        current_timeframe_hours = timeframe_to_hours.get(tf, hours)
                        
                        # Only alert if this is a longer timeframe (higher hours)
                        if current_timeframe_hours <= prev_timeframe_hours:
                            logger.debug(f"Skipping {symbol} {tf} alert - already alerted for {prev_timeframe_hours}h timeframe")
                            continue
                    
                    alerts.append({
                        'symbol': symbol,
                        'percent': percent_change,
                        'timeframe': tf,
                        'timeframe_hours': timeframe_to_hours.get(tf, hours),
                        'price': float(coin['currentPrice'])
                    })
        
        if alerts:
            # Deduplicate alerts - keep only the most significant alert for each symbol
            # Most significant = highest absolute percentage change OR longest timeframe if percentages are similar
            deduped_alerts = {}
            for alert in alerts:
                symbol = alert['symbol']
                if symbol not in deduped_alerts:
                    deduped_alerts[symbol] = alert
                else:
                    # Keep the alert with higher absolute percentage
                    # If percentages are close (within 1%), prefer longer timeframe
                    current_abs = abs(deduped_alerts[symbol]['percent'])
                    new_abs = abs(alert['percent'])
                    
                    if new_abs > current_abs + 1.0:  # New alert is significantly higher
                        deduped_alerts[symbol] = alert
                    elif abs(new_abs - current_abs) <= 1.0 and alert['timeframe_hours'] > deduped_alerts[symbol]['timeframe_hours']:
                        # Similar percentages, prefer longer timeframe
                        deduped_alerts[symbol] = alert
            
            # Convert back to list and sort by absolute percentage
            alerts = list(deduped_alerts.values())
            alerts.sort(key=lambda x: abs(x['percent']), reverse=True)
            
            embed = discord.Embed(
                title="🚨 Volatility Alert",
                color=discord.Color.orange(),
                timestamp=datetime.utcnow()
            )
            
            for alert in alerts[:5]:  # Top 5 alerts
                emoji = "🚀" if alert['percent'] > 0 else "💥"
                embed.add_field(
                    name=f"{emoji} {alert['symbol']}",
                    value=f"{alert['percent']:+.2f}% in {alert['timeframe']}\n"
                          f"Price: ${alert['price']:.4f}",
                    inline=True
                )
            
            embed.set_footer(text="Price movements exceeding configured thresholds")

            await channel.send(embed=embed)
            logger.info(f"Sent volatility alert with {len(alerts[:5])} coins to #{channel.name}")
            
            # Clean up old messages after sending new alert
            try:
                logger.debug(f"Starting cleanup of messages older than 4 hours in #{channel.name}")
                deleted = await cleanup_before_send(channel, max_age_hours=4, bot_id=self.bot.user.id)
                if deleted and deleted > 0:
                    logger.info(f"Cleaned up {deleted} old volatility alert messages")
                else:
                    logger.debug("No old volatility messages to clean up")
            except Exception as e:
                logger.warning(f"Failed to cleanup old messages: {e}")
            
            # Track sent alerts - update to the longest timeframe
            for alert in alerts[:5]:
                symbol = alert['symbol']
                if symbol not in self.sent_alerts or alert['timeframe_hours'] > self.sent_alerts[symbol]['timeframe_hours']:
                    self.sent_alerts[symbol] = {
                        'timeframe_hours': alert['timeframe_hours'],
                        'timestamp': current_time.timestamp()
                    }
        else:
            logger.debug("No coins exceeded volatility thresholds this cycle")

    @volatility_alerts.before_loop
    async def before_volatility_alerts(self):
        await self.bot.wait_until_ready()

    @volatility_alerts.error
    async def volatility_alerts_error(self, error):
        """Safety net: if the loop ever dies, log it and restart it so
        alerts don't stay silently dead (as happened on a Discord 503)."""
        logger.error(f"volatility_alerts loop crashed: {error!r} — restarting")
        try:
            self.volatility_alerts.restart()
        except Exception as e:
            logger.error(f"Failed to restart volatility_alerts loop: {e!r}")

def setup(bot, config):
    bot.add_cog(VolatilityCog(bot, config))
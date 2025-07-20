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

logger = logging.getLogger('discord-bot.volatility')

class VolatilityCog(commands.Cog):
    """Commands for crypto volatility scanning"""
    
    def __init__(self, bot, config):
        self.bot = bot
        self.config = config
        api_base = config.get('api_base_url', 'https://example.com/api')
        self.base_url = f"{api_base}/volatility-scanner"
        self.session = None
        self.volatility_alerts.start()
        
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
        valid_timeframes = ['15m', '1h', '2h', '3h', '4h', '6h', '12h', '24h', '48h']
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
            '15m': 3,
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
        valid_timeframes = ['15m', '1h', '2h', '3h', '4h', '6h', '12h', '24h', '48h']
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
        """Check for extreme volatility and send alerts"""
        if not self.config.get('auto_update_channels', {}).get('alerts'):
            return
            
        # Define alert thresholds
        alert_thresholds = {
            '15m': 10,   # 10% in 15 minutes is extreme
            '1h': 15,     # 15% in 1 hour
            '4h': 25,     # 25% in 4 hours
        }
        
        data = await self.fetch_volatility_data(alert_thresholds)
        if not data or not data.get('success'):
            return
            
        channel_id = self.config['auto_update_channels']['alerts']
        channel = self.bot.get_channel(channel_id)
        if not channel:
            logger.error(f"Alerts channel {channel_id} not found")
            return
            
        # Collect extreme movers
        alerts = []
        for t in data['thresholds']:
            hours = t['hours']
            if hours < 1:
                tf = f"{int(hours * 60)}m"
            else:
                tf = f"{int(hours)}h"
                
            for coin in t['coins']:
                percent_change = float(coin['percentChange'])
                if abs(percent_change) >= alert_thresholds.get(tf, 999):
                    alerts.append({
                        'symbol': coin['symbol'],
                        'percent': percent_change,
                        'timeframe': tf,
                        'price': float(coin['currentPrice'])
                    })
        
        if alerts:
            # Sort by absolute percentage
            alerts.sort(key=lambda x: abs(x['percent']), reverse=True)
            
            embed = discord.Embed(
                title="⚠️ Extreme Volatility Alert",
                description="Significant price movements detected!",
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
            
            embed.set_footer(text="Extreme price movements detected")
            
            await channel.send(embed=embed)
    
    @volatility_alerts.before_loop
    async def before_volatility_alerts(self):
        await self.bot.wait_until_ready()

def setup(bot, config):
    bot.add_cog(VolatilityCog(bot, config))
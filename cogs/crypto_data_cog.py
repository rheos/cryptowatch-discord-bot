"""
Crypto Data Cog - Handles funding rates and market data commands
"""
import discord
from discord.ext import commands
import aiohttp
import asyncio
from datetime import datetime
import logging

logger = logging.getLogger('discord-bot.crypto')

class CryptoDataCog(commands.Cog):
    def __init__(self, bot, config):
        self.bot = bot
        self.config = config
        self.api_base = config.get('api_base_url', 'https://example.com/api')
        self.session = None
    
    async def cog_load(self):
        """Called when cog is loaded"""
        self.session = aiohttp.ClientSession()
        logger.info("Crypto data cog loaded")
    
    async def cog_unload(self):
        """Cleanup when cog is unloaded"""
        if self.session:
            await self.session.close()
    
    @commands.command(name='negative', aliases=['n', 'neg'])
    async def most_negative_rates(self, ctx, limit: int = 10):
        """Show most negative funding rates
        Usage: !negative [limit]
        """
        try:
            async with self.session.get(f"{self.api_base}/most-negative") as response:
                if response.status == 200:
                    data = await response.json()
                    rates = data.get('rates', [])[:limit]
                    
                    embed = discord.Embed(
                        title="🔴 Most Negative",
                        description=f"Top {len(rates)} coins with extreme negative funding rates",
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
            logger.error(f"Error in negative command: {e}")
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
                        description="Recently flipped from negative to positive funding",
                        color=discord.Color.green(),
                        timestamp=datetime.utcnow()
                    )
                    
                    for rate in rates:
                        symbol = rate['instId'].replace('-USDT', '')
                        current = float(rate['currentRate']) * 100
                        # Get previous rate from changes.prev.rate
                        prev_data = rate.get('changes', {}).get('prev', {})
                        previous = float(prev_data.get('rate', 0)) * 100
                        
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
                        title="🟡 Improving Negative",
                        description="Still negative but getting better",
                        color=discord.Color.orange(),
                        timestamp=datetime.utcnow()
                    )
                    
                    for rate in rates:
                        symbol = rate['instId'].replace('-USDT', '')
                        current = float(rate['currentRate']) * 100
                        # Get change from the changes object
                        changes = rate.get('changes', {})
                        # Get the first available timeframe
                        timeframe_data = changes.get('24h') or changes.get('12h') or changes.get('8h') or changes.get('4h') or {}
                        change = float(timeframe_data.get('change', 0)) * 100
                        
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
            # Fetch data from multiple endpoints like the web app does
            endpoints = {
                'most_negative': f"{self.api_base}/most-negative",
                'turned_positive': f"{self.api_base}/turned-positive",
                'worsening': f"{self.api_base}/worsening-negative",
                'improving': f"{self.api_base}/improving-negative"
            }
            
            results = {}
            for key, url in endpoints.items():
                async with self.session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        results[key] = data.get('rates', [])
                    
            embed = discord.Embed(
                title="🔍 Funding Scanner Overview",
                description="Current market funding rates",
                color=discord.Color.gold(),
                timestamp=datetime.utcnow()
            )
            
            # Add Most Negative
            if results.get('most_negative'):
                most_neg = results['most_negative'][:3]
                if most_neg:
                    value = "\n".join([
                        f"**{r['instId']}**: {float(r['currentRate'])*100:.3f}%"
                        for r in most_neg
                    ])
                    embed.add_field(name="🔴 Most Negative", value=value, inline=True)
            
            # Add Turned Positive
            if results.get('turned_positive'):
                turned = results['turned_positive'][:3]
                if turned:
                    value = "\n".join([
                        f"**{r['instId']}**: {float(r['currentRate'])*100:.3f}%"
                        for r in turned
                    ])
                    embed.add_field(name="🟢 Turned Positive", value=value, inline=True)
            
            # Add Worsening
            if results.get('worsening'):
                worse = results['worsening'][:3]
                if worse:
                    value = "\n".join([
                        f"**{r['instId']}**: {float(r['currentRate'])*100:.3f}%"
                        for r in worse
                    ])
                    embed.add_field(name="🟠 Worsening", value=value, inline=True)
            
            # Add Improving
            if results.get('improving'):
                improving = results['improving'][:3]
                if improving:
                    value = "\n".join([
                        f"**{r['instId']}**: {float(r['currentRate'])*100:.3f}%"
                        for r in improving
                    ])
                    embed.add_field(name="🟡 Improving", value=value, inline=True)
            
            # Add summary stats
            all_rates = []
            for rates in results.values():
                all_rates.extend(rates)
            
            # Remove duplicates by instId
            unique_rates = {}
            for r in all_rates:
                unique_rates[r['instId']] = r
            
            total_negative = len([r for r in unique_rates.values() if float(r.get('currentRate', 0)) < 0])
            extreme_negative = len([r for r in unique_rates.values() if float(r.get('currentRate', 0)) < -0.001])
            
            embed.add_field(
                name="📊 Summary",
                value=f"Negative rates: {total_negative}\nExtreme (<-0.1%): {extreme_negative}\nTotal tracked: {len(unique_rates)}",
                inline=True
            )
            
            embed.set_footer(text="Use !n, !t, !w, !i for detailed views")
            await ctx.send(embed=embed)
                    
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
                        title="🟠 Worsening Negative",
                        description="Getting more negative - shorts building",
                        color=discord.Color.dark_red(),
                        timestamp=datetime.utcnow()
                    )
                    
                    for rate in rates:
                        symbol = rate['instId'].replace('-USDT', '')
                        current = float(rate['currentRate']) * 100
                        # Get change from the changes object
                        changes = rate.get('changes', {})
                        # Get the first available timeframe
                        timeframe_data = changes.get('24h') or changes.get('12h') or changes.get('8h') or changes.get('4h') or {}
                        change = float(timeframe_data.get('change', 0)) * 100
                        
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
    
    @commands.command(name='help', aliases=['h', 'commands'])
    async def help_command(self, ctx):
        """Show bot commands"""
        embed = discord.Embed(
            title="📊 CryptoWatch Bot Commands",
            description="Real-time funding rates and market data",
            color=discord.Color.blue()
        )
        
        # Market data commands
        funding_commands = [
            ("!scanner", "!scan", "📊 Market overview & statistics"),
            ("!negative [n]", "!n", "🔴 Most Negative (extreme rates)"),
            ("!turned [n]", "!t", "🟢 Turned Positive (flipped bullish)"),
            ("!improving [n]", "!i", "🟡 Improving Negative (getting better)"),
            ("!worsening [n]", "!w", "🟠 Worsening Negative (getting worse)")
        ]
        
        commands_text = ""
        for cmd, alias, desc in funding_commands:
            commands_text += f"**{cmd}**"
            if alias:
                commands_text += f" or **{alias}**"
            commands_text += f"\n{desc}\n\n"
        
        embed.add_field(
            name="📈 Funding Rate Commands",
            value=commands_text.strip(),
            inline=False
        )
        
        # Volatility commands
        volatility_commands = [
            ("!volatility [tf] [%]", "!vola, !move", "🎢 Check volatile coins (e.g. !vola 1h 5)"),
            ("!movers [tf]", "!top", "🚀 Top gainers/losers (e.g. !movers 24h)"),
            ("!pricealert COIN [tf] [%]", "!pa", "⚠️ Check specific coin movement")
        ]
        
        vol_commands_text = ""
        for cmd, alias, desc in volatility_commands:
            vol_commands_text += f"**{cmd}**"
            if alias:
                vol_commands_text += f" or **{alias}**"
            vol_commands_text += f"\n{desc}\n\n"
        
        embed.add_field(
            name="📊 Volatility Scanner",
            value=vol_commands_text.strip(),
            inline=False
        )
        
        embed.add_field(
            name="ℹ️ Notes",
            value=(
                "• Funding data from BloFin exchange\n"
                "• Price data from Binance\n" 
                "• Updates every 5-30 minutes\n"
                "• Example: `!n 20` shows top 20"
            ),
            inline=False
        )
        
        embed.set_footer(text="Tracking mid-cap alts and meme coins")
        await ctx.send(embed=embed)

    @commands.command(name='purge', aliases=['clear'])
    @commands.has_permissions(manage_messages=True)
    async def purge_messages(self, ctx, amount: int = 100):
        """Delete messages in bulk (admin only)
        Usage: !purge [amount]
        Max: 100 messages at once
        """
        if amount > 100:
            await ctx.send("❌ Can only delete up to 100 messages at once")
            return
        
        try:
            # Delete the command message too
            deleted = await ctx.channel.purge(limit=amount + 1)
            
            # Send confirmation that auto-deletes
            msg = await ctx.send(f"✅ Deleted {len(deleted) - 1} messages")
            await asyncio.sleep(3)
            await msg.delete()
            
        except discord.errors.Forbidden:
            await ctx.send("❌ I don't have permission to delete messages")
        except Exception as e:
            logger.error(f"Error in purge command: {e}")
            await ctx.send("❌ An error occurred while deleting messages")

async def setup(bot):
    # This allows the cog to be loaded dynamically
    pass
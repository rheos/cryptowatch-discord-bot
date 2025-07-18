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
                        description="Recently flipped from negative to positive funding",
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
                        title="🟡 Improving Negative",
                        description="Still negative but getting better",
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
                    
                    # Get rates data first
                    rates = data.get('rates', [])
                    
                    # Add statistics if available
                    stats = data.get('stats', {}).get('overall')
                    if stats:
                        # Count negative rates from the rates data
                        negative_count = sum(1 for r in rates if float(r.get('currentRate', 0)) < 0)
                        extreme_count = sum(1 for r in rates if float(r.get('currentRate', 0)) < -0.001)
                        
                        embed.add_field(
                            name="📊 Market Stats",
                            value=(
                                f"Total Tracked: {stats.get('total_instruments', 0)}\n"
                                f"Negative Now: {negative_count}\n"
                                f"Extreme (<-0.1%): {extreme_count}"
                            ),
                            inline=True
                        )
                    
                    # Top movers
                    if rates:
                        # Most negative (or least positive if no negatives)
                        sorted_rates = sorted(rates, key=lambda x: float(x.get('currentRate', 0)))
                        # Get actual negative rates or the least positive ones
                        negative_rates = [r for r in sorted_rates if float(r.get('currentRate', 0)) < 0]
                        display_rates = negative_rates[:3] if negative_rates else sorted_rates[:3]
                        
                        if display_rates:
                            value = "\n".join([
                                f"{r['instId'].replace('-USDT', '')}: {float(r['currentRate'])*100:.3f}%"
                                for r in display_rates
                            ])
                            title = "🔴 Most Negative" if negative_rates else "📈 Least Positive"
                            embed.add_field(name=title, value=value, inline=True)
                        
                        # Biggest changes - look in the changes object
                        rates_with_changes = []
                        for r in rates:
                            changes = r.get('changes', {})
                            # Get the first available change period
                            if '24h' in changes:
                                change_val = float(changes['24h'].get('change', 0))
                            elif '12h' in changes:
                                change_val = float(changes['12h'].get('change', 0))
                            elif '8h' in changes:
                                change_val = float(changes['8h'].get('change', 0))
                            else:
                                change_val = 0
                            rates_with_changes.append((r, change_val))
                        
                        biggest_changes = sorted(rates_with_changes, 
                            key=lambda x: abs(x[1]), 
                            reverse=True
                        )[:3]
                        
                        if biggest_changes and any(x[1] != 0 for x in biggest_changes):
                            value = "\n".join([
                                f"{r[0]['instId'].replace('-USDT', '')}: {r[1]*100:+.3f}%"
                                for r in biggest_changes if r[1] != 0
                            ])
                            if value:
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
                        title="🟠 Worsening Negative",
                        description="Getting more negative - shorts building",
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
    
    @commands.command(name='help', aliases=['h', 'commands'])
    async def help_command(self, ctx):
        """Show bot commands"""
        embed = discord.Embed(
            title="📊 CryptoWatch Bot Commands",
            description="Real-time funding rates and market data",
            color=discord.Color.blue()
        )
        
        # Funding commands
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
        
        embed.add_field(
            name="ℹ️ Notes",
            value=(
                "• Data from BloFin exchange\n"
                "• Updates every 30 minutes\n"
                "• Default shows top 10 results\n"
                "• Example: `!negative 20` shows top 20"
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
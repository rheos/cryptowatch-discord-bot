"""
Setup commands for configuring the bot in new guilds
"""
import discord
from discord.ext import commands
import json
import logging

class SetupCog(commands.Cog):
    def __init__(self, bot, config=None):
        self.bot = bot
        self.config = config or bot.config
        self.logger = logging.getLogger('discord-bot.setup')
    
    @commands.command()
    @commands.has_permissions(administrator=True)
    async def setup(self, ctx):
        """Interactive setup wizard for the guild"""
        guild = ctx.guild
        
        embed = discord.Embed(
            title="🛠️ CryptoWatch Bot Setup",
            description="Welcome! Let's configure the bot for your server.",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="Available Setup Commands",
            value=(
                "`!setup_timezone #voice-channel timezone` - Set up a timezone channel (voice channel required)\n"
                "`!setup_market_events #text-channel` - Set market events channel\n"
                "`!setup_funding #text-channel` - Set funding rates channel\n"
                "`!setup_alerts #text-channel` - Set alerts channel\n"
                "`!setup_engagement` - Configure engagement tracking\n"
                "`!setup_show` - Show current configuration"
            ),
            inline=False
        )
        
        await ctx.send(embed=embed)
    
    @commands.command()
    @commands.has_permissions(administrator=True)
    async def setup_timezone(self, ctx, channel: discord.VoiceChannel, *, timezone: str):
        """Set up a timezone channel (voice channel - allows flexible naming with spaces/colons)"""
        guild_id = ctx.guild.id
        
        # Validate timezone
        import pytz
        try:
            pytz.timezone(timezone)
        except:
            await ctx.send(f"❌ Invalid timezone: {timezone}")
            await ctx.send("Example timezones: America/New_York, Europe/London, Asia/Tokyo")
            return
        
        # Save to database
        async with self.bot.db.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("""
                    INSERT INTO guild_channels (guild_id, channel_type, channel_id, settings)
                    VALUES (%s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE 
                        channel_id = VALUES(channel_id),
                        settings = VALUES(settings)
                """, (
                    guild_id,
                    f"timezone_{timezone.replace('/', '_')}",
                    channel.id,
                    json.dumps({'timezone': timezone})
                ))
                await conn.commit()
        
        await ctx.send(f"✅ Set up {channel.mention} for timezone **{timezone}**")
        
        # Update channel name immediately
        try:
            from cogs.timezone_cog import TimezoneCog
            tz_cog = self.bot.get_cog('TimezoneCog')
            if tz_cog:
                await tz_cog.update_single_channel(channel, timezone)
        except Exception as e:
            self.logger.error(f"Error updating channel name: {e}")
    
    @commands.command()
    @commands.has_permissions(administrator=True)
    async def setup_market_events(self, ctx, channel: discord.TextChannel):
        """Set up market events channel"""
        await self._setup_channel(ctx, channel, 'market_events', "market events")
    
    @commands.command()
    @commands.has_permissions(administrator=True)
    async def setup_funding(self, ctx, channel: discord.TextChannel):
        """Set up funding rates channel"""
        await self._setup_channel(ctx, channel, 'auto_update_funding', "funding rates")
    
    @commands.command()
    @commands.has_permissions(administrator=True)
    async def setup_alerts(self, ctx, channel: discord.TextChannel):
        """Set up alerts channel"""
        await self._setup_channel(ctx, channel, 'auto_update_alerts', "alerts")
    
    async def _setup_channel(self, ctx, channel: discord.TextChannel, channel_type: str, friendly_name: str):
        """Helper to set up a channel"""
        guild_id = ctx.guild.id
        
        async with self.bot.db.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("""
                    INSERT INTO guild_channels (guild_id, channel_type, channel_id, settings)
                    VALUES (%s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE channel_id = VALUES(channel_id)
                """, (guild_id, channel_type, channel.id, '{}'))
                await conn.commit()
        
        await ctx.send(f"✅ Set up {channel.mention} for **{friendly_name}**")
    
    @commands.command()
    @commands.has_permissions(administrator=True)
    async def setup_engagement(self, ctx):
        """Configure engagement tracking"""
        guild = ctx.guild
        
        # Check for required roles
        required_roles = ['NewMember', 'Member', 'Active', 'Vacation']
        missing_roles = []
        
        for role_name in required_roles:
            if not discord.utils.get(guild.roles, name=role_name):
                missing_roles.append(role_name)
        
        if missing_roles:
            embed = discord.Embed(
                title="⚠️ Missing Roles",
                description=f"Please create these roles first:\n" + "\n".join(f"• {role}" for role in missing_roles),
                color=discord.Color.yellow()
            )
            await ctx.send(embed=embed)
            return
        
        # Enable engagement for this guild
        async with self.bot.db.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("""
                    INSERT INTO guild_settings (
                        guild_id, 
                        engagement_enabled,
                        active_messages_threshold,
                        active_days_threshold,
                        warning_days_before,
                        warning_min_messages,
                        dm_warnings_enabled
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        engagement_enabled = VALUES(engagement_enabled)
                """, (guild.id, True, 10, 30, 7, 7, True))
                await conn.commit()
        
        embed = discord.Embed(
            title="✅ Engagement Tracking Enabled",
            description=(
                "Members will be automatically assigned roles based on activity:\n"
                "• **NewMember** → **Member** (after first message)\n"
                "• **Member** → **Active** (10+ messages in 30 days)\n"
                "• Warnings sent 7 days before losing Active status"
            ),
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)
    
    @commands.command()
    @commands.has_permissions(administrator=True)
    async def setup_show(self, ctx):
        """Show current guild configuration"""
        guild_id = ctx.guild.id
        settings = await self.bot.db.get_guild_settings(guild_id)
        
        if not settings:
            await ctx.send("❌ No configuration found. Run `!setup` to get started.")
            return
        
        embed = discord.Embed(
            title="📋 Current Configuration",
            color=discord.Color.blue()
        )
        
        # Show channels
        channels = settings.get('channels', {})
        if channels:
            channel_list = []
            for channel_type, channel_data in channels.items():
                channel = ctx.guild.get_channel(channel_data['id'])
                if channel:
                    channel_list.append(f"• **{channel_type}**: {channel.mention}")
            
            if channel_list:
                embed.add_field(
                    name="Configured Channels",
                    value="\n".join(channel_list),
                    inline=False
                )
        
        # Show settings
        guild_settings = settings.get('settings', {})
        if guild_settings:
            embed.add_field(
                name="Engagement",
                value="✅ Enabled" if guild_settings.get('engagement_enabled') else "❌ Disabled",
                inline=True
            )
        
        await ctx.send(embed=embed)
    
    @commands.command()
    @commands.has_permissions(administrator=True)
    async def setup_remove(self, ctx, channel_type: str):
        """Remove a channel configuration"""
        guild_id = ctx.guild.id
        
        async with self.bot.db.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("""
                    DELETE FROM guild_channels 
                    WHERE guild_id = %s AND channel_type = %s
                """, (guild_id, channel_type))
                affected = cursor.rowcount
                await conn.commit()
        
        if affected:
            await ctx.send(f"✅ Removed configuration for **{channel_type}**")
        else:
            await ctx.send(f"❌ No configuration found for **{channel_type}**")

async def setup(bot):
    await bot.add_cog(SetupCog(bot))
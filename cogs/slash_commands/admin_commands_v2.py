"""
Admin slash commands: /setup, /admin - Version 2 with working command structure
"""
import discord
from discord import app_commands
from discord.ext import commands
import logging
import json
from typing import Optional, Union, List
from datetime import datetime, timedelta
import pytz
from .base import SlashCommandBase

logger = logging.getLogger('discord-bot.admin_commands')

class AdminCommands(SlashCommandBase):
    """Admin-related slash commands"""
    
    @app_commands.command(name="setup", description="Configure bot settings for this server")
    @app_commands.describe(
        action="Setup action to perform"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="Show Configuration", value="show"),
        app_commands.Choice(name="Enable Engagement Tracking", value="engagement_enable"),
        app_commands.Choice(name="Disable Engagement Tracking", value="engagement_disable"),
        app_commands.Choice(name="Enable Market Events", value="market_enable"),
        app_commands.Choice(name="Disable Market Events", value="market_disable"),
    ])
    @app_commands.default_permissions(administrator=True)
    async def setup_command(self, interaction: discord.Interaction, action: str):
        """Main setup command"""
        logger.info(f"Setup command called with action: {action}")
        await interaction.response.defer(ephemeral=True)  # Make response private
        
        if action == "show":
            logger.info("Calling _handle_setup_show")
            await self._handle_setup_show(interaction)
        elif action == "engagement_enable":
            await self._handle_setup_engagement(interaction, enable=True)
        elif action == "engagement_disable":
            await self._handle_setup_engagement(interaction, enable=False)
        elif action == "market_enable":
            await self._handle_setup_market_events(interaction, enable=True)
        elif action == "market_disable":
            await self._handle_setup_market_events(interaction, enable=False)
    
    @app_commands.command(name="setup_timezone", description="Configure a timezone display channel")
    @app_commands.describe(
        channel="Voice channel for timezone display",
        timezone="Timezone (e.g., America/New_York, Europe/London)"
    )
    @app_commands.default_permissions(administrator=True)
    async def setup_timezone(self, interaction: discord.Interaction, 
                           channel: discord.VoiceChannel, 
                           timezone: str):
        """Setup timezone channel"""
        await interaction.response.defer(ephemeral=True)
        await self._handle_setup_timezone(interaction, channel, timezone)
    
    @app_commands.command(name="setup_market_channels", description="Configure market event channels")
    @app_commands.describe(
        countdown_channel="Voice channel for market event countdown",
        schedule_channel="Text channel for market schedule"
    )
    @app_commands.default_permissions(administrator=True)
    async def setup_market_channels(self, interaction: discord.Interaction,
                                   countdown_channel: discord.VoiceChannel,
                                   schedule_channel: discord.TextChannel):
        """Setup market event channels"""
        await interaction.response.defer(ephemeral=True)
        
        # Configure countdown channel
        await self.bot.db.configure_guild_channel(
            interaction.guild_id,
            'market_events',
            countdown_channel.id
        )
        
        # Configure schedule channel
        await self.bot.db.configure_guild_channel(
            interaction.guild_id,
            'market_times',
            schedule_channel.id
        )
        
        embed = discord.Embed(
            title="✅ Market Event Channels Configured",
            description=(
                f"**Countdown Channel**: {countdown_channel.mention}\n"
                f"**Schedule Channel**: {schedule_channel.mention}\n\n"
                "Use `/setup` and choose 'Enable Market Events' to start tracking"
            ),
            color=discord.Color.green()
        )
        await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="setup_alerts", description="Configure alert channels")
    @app_commands.describe(
        channel="Text channel for alerts",
        alert_type="Type of alerts"
    )
    @app_commands.choices(alert_type=[
        app_commands.Choice(name="Market Events", value="market_events"),
        app_commands.Choice(name="Funding Rates", value="funding"),
        app_commands.Choice(name="General Alerts", value="alerts"),
    ])
    @app_commands.default_permissions(administrator=True)
    async def setup_alerts(self, interaction: discord.Interaction,
                         channel: discord.TextChannel,
                         alert_type: str):
        """Setup alert channels"""
        await interaction.response.defer(ephemeral=True)
        await self._handle_setup_channel(interaction, channel, alert_type)
    
    async def _handle_setup_show(self, interaction: discord.Interaction):
        """Show current configuration"""
        guild_id = interaction.guild_id
        logger.info(f"Setup show called for guild {guild_id}")
        
        try:
            settings = await self.bot.db.get_guild_settings(guild_id)
            logger.info(f"Retrieved settings: {settings}")
            
            embed = discord.Embed(
                title="📋 Current Configuration",
                color=discord.Color.blue()
            )
            
            # Handle no settings case
            if not settings:
                embed.add_field(name="Status", value="No configuration found", inline=False)
                await interaction.followup.send(embed=embed)
                return
            
            # Show channels if any
            if settings.get('channels'):
                channels = settings['channels']
                timezone_lines = []
                other_lines = []
                
                # Sort channels for consistent display
                sorted_channels = sorted(channels.items())
                
                for channel_type, channel_info in sorted_channels:
                    channel_id = channel_info.get('id')
                    if channel_id:
                        channel = interaction.guild.get_channel(channel_id)
                        if channel:
                            # Handle timezone channels specially
                            if channel_type.startswith('timezone_'):
                                # Extract timezone from settings
                                tz_settings = channel_info.get('settings', {})
                                if isinstance(tz_settings, str):
                                    tz_settings = json.loads(tz_settings)
                                timezone = tz_settings.get('timezone', 'Unknown')
                                timezone_lines.append((timezone, channel))
                            else:
                                # Regular channels
                                other_lines.append(f"**{channel_type}**: {channel.mention}")
                
                # Build final config lines
                config_lines = []
                
                # Add timezone channels with numbers
                for i, (timezone, channel) in enumerate(timezone_lines, 1):
                    config_lines.append(f"**timezone {i}**: {channel.mention} ({timezone})")
                
                # Add other channels
                config_lines.extend(other_lines)
                
                if config_lines:
                    embed.add_field(name="Configured Channels", value="\n".join(config_lines), inline=False)
                else:
                    embed.add_field(name="Channels", value="No channels configured", inline=False)
            else:
                embed.add_field(name="Channels", value="No channels configured", inline=False)
            
            # Check engagement settings
            engagement_settings = await self.bot.db.get_engagement_settings(guild_id)
            if engagement_settings:
                status = "✅ Enabled" if engagement_settings.get('enabled') else "❌ Disabled"
                embed.add_field(name="Engagement Tracking", value=status, inline=True)
                
                if engagement_settings.get('welcome_channel_id'):
                    channel = interaction.guild.get_channel(engagement_settings['welcome_channel_id'])
                    if channel:
                        embed.add_field(name="Welcome Channel", value=channel.mention, inline=True)
            else:
                embed.add_field(name="Engagement Tracking", value="❌ Not configured", inline=True)
            
            # Check market events settings
            market_enabled = await self.bot.db.get_setting(guild_id, 'market_events.enabled')
            if market_enabled:
                embed.add_field(name="Market Events", value="✅ Enabled", inline=True)
            else:
                embed.add_field(name="Market Events", value="❌ Disabled", inline=True)
            
            embed.set_footer(text="Use /setup commands to configure")
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in setup show: {e}", exc_info=True)
            import traceback
            tb = traceback.format_exc()
            logger.error(f"Full traceback:\n{tb}")
            await interaction.followup.send(f"❌ Error retrieving configuration: {str(e)}")
    
    def _format_timezone_name(self, timezone_str: str) -> str:
        """Format timezone for channel name"""
        tz = pytz.timezone(timezone_str)
        now = datetime.now(tz)
        
        # Round to nearest 5-minute interval
        minute = round(now.minute / 5) * 5
        if minute == 60:
            rounded_time = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        else:
            rounded_time = now.replace(minute=minute, second=0, microsecond=0)
        
        hour = rounded_time.strftime('%-I')
        minute_str = rounded_time.strftime('%M')
        period = rounded_time.strftime('%p').lower()
        
        # Get city name and format it nicely
        city_name = timezone_str.split("/")[1].replace("_", " ").title()
        
        # Special replacements
        if city_name == "Halifax":
            city_name = "PEI"
        elif city_name == "Kolkata":
            city_name = "India"
        
        return f"{city_name} {hour}:{minute_str}{period}"
    
    async def _handle_setup_timezone(self, interaction: discord.Interaction, channel: discord.VoiceChannel, timezone: str):
        """Setup timezone channel"""
        try:
            pytz.timezone(timezone)
        except pytz.exceptions.UnknownTimeZoneError:
            await interaction.followup.send(f"❌ Unknown timezone: {timezone}\nUse format like: America/New_York, Europe/London, Asia/Tokyo")
            return
        
        # Store in database
        await self.bot.db.configure_guild_channel(
            interaction.guild_id,
            f"timezone_{timezone.replace('/', '_')}",
            channel.id,
            {'timezone': timezone}
        )
        
        embed = discord.Embed(
            title="✅ Timezone Channel Configured",
            description=f"{channel.mention} will now show time for **{timezone}**",
            color=discord.Color.green()
        )
        await interaction.followup.send(embed=embed)
        
        # Update channel name immediately
        try:
            new_name = self._format_timezone_name(timezone)
            await channel.edit(name=new_name)
            logger.info(f"Updated timezone channel name to: {new_name}")
        except Exception as e:
            logger.error(f"Error updating channel name: {e}")
    
    async def _handle_setup_channel(self, interaction: discord.Interaction, channel: discord.TextChannel, channel_type: str):
        """Setup various channel types"""
        await self.bot.db.configure_guild_channel(
            interaction.guild_id,
            channel_type,
            channel.id,
            {}
        )
        
        channel_names = {
            'market_events': 'Market Events',
            'funding': 'Funding Rates',
            'alerts': 'Alerts'
        }
        
        embed = discord.Embed(
            title=f"✅ {channel_names.get(channel_type, channel_type)} Channel Configured",
            description=f"{channel.mention} will receive {channel_names.get(channel_type, channel_type).lower()} updates",
            color=discord.Color.green()
        )
        await interaction.followup.send(embed=embed)
    
    async def _handle_setup_engagement(self, interaction: discord.Interaction, enable: bool = True):
        """Setup engagement tracking"""
        guild = interaction.guild
        
        if enable:
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
                await interaction.followup.send(embed=embed)
                return
        
        # Enable/disable engagement
        await self.bot.db.update_engagement_settings(
            guild.id,
            enabled=enable,
            active_messages_threshold=10,
            active_days_threshold=30,
            warning_days_before=7,
            warning_min_messages=7,
            dm_warnings_enabled=True
        )
        
        if enable:
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
        else:
            embed = discord.Embed(
                title="❌ Engagement Tracking Disabled",
                description="Automatic role assignment has been disabled",
                color=discord.Color.red()
            )
        
        await interaction.followup.send(embed=embed)
    
    async def _handle_setup_market_events(self, interaction: discord.Interaction, enable: bool = True):
        """Setup market events"""
        guild = interaction.guild
        
        if enable:
            # Check for required channels
            channels = await self.bot.db.get_guild_channels(guild.id)
            has_market_events = False
            has_market_times = False
            
            for channel in channels:
                if channel['channel_type'] == 'market_events':
                    has_market_events = True
                elif channel['channel_type'] == 'market_times':
                    has_market_times = True
            
            if not has_market_events or not has_market_times:
                missing = []
                if not has_market_events:
                    missing.append("Market Events (voice channel for countdown)")
                if not has_market_times:
                    missing.append("Market Times (text channel for schedule)")
                
                embed = discord.Embed(
                    title="⚠️ Missing Channels",
                    description=f"Please configure these channels first:\n" + "\n".join(f"• {ch}" for ch in missing),
                    color=discord.Color.yellow()
                )
                embed.add_field(
                    name="How to configure",
                    value="Use `/setup_market_channels` to set up the required channels",
                    inline=False
                )
                await interaction.followup.send(embed=embed)
                return
        
        # Enable/disable market events
        await self.bot.db.set_setting(guild.id, 'market_events.enabled', enable)
        
        if enable:
            embed = discord.Embed(
                title="✅ Market Events Enabled",
                description=(
                    "Market events tracking has been enabled:\n"
                    "• Voice channel will show countdown to next market event\n"
                    "• Text channel will show pinned market schedule\n"
                    "• Updates every 5 minutes"
                ),
                color=discord.Color.green()
            )
        else:
            embed = discord.Embed(
                title="❌ Market Events Disabled",
                description="Market events tracking has been disabled",
                color=discord.Color.red()
            )
        
        await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="admin", description="Admin commands for engagement management")
    @app_commands.describe(
        action="Admin action to perform",
        member="Member to target (for specific actions)",
        role="Role to grant/remove",
        limit="Number of results to show"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="Analyze All Members", value="analyze"),
        app_commands.Choice(name="Show Active Members", value="active"),
        app_commands.Choice(name="Show Inactive Members", value="inactive"),
        app_commands.Choice(name="Grant Role to Member", value="grant_role"),
        app_commands.Choice(name="Remove Role from Member", value="remove_role"),
        app_commands.Choice(name="Check Member Stats", value="check_member"),
        app_commands.Choice(name="Refresh All Stats", value="refresh"),
    ])
    @app_commands.default_permissions(administrator=True)
    async def admin_command(self, interaction: discord.Interaction,
                           action: str,
                           member: Optional[discord.Member] = None,
                           role: Optional[discord.Role] = None,
                           limit: Optional[int] = 10):
        """Admin engagement management"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            if action == "analyze":
                await self._handle_analyze_members(interaction, limit)
            elif action == "active":
                await self._handle_show_active(interaction, limit)
            elif action == "inactive":
                await self._handle_show_inactive(interaction, limit)
            elif action == "grant_role":
                if not member or not role:
                    await interaction.followup.send("❌ Grant role requires both member and role parameters")
                    return
                await self._handle_grant_role(interaction, member, role)
            elif action == "remove_role":
                if not member or not role:
                    await interaction.followup.send("❌ Remove role requires both member and role parameters")
                    return
                await self._handle_remove_role(interaction, member, role)
            elif action == "check_member":
                if not member:
                    await interaction.followup.send("❌ Check member requires a member parameter")
                    return
                await self._handle_check_member(interaction, member)
            elif action == "refresh":
                await self._handle_refresh_stats(interaction)
                
        except Exception as e:
            logger.error(f"Error in admin command: {e}")
            await interaction.followup.send("❌ An error occurred while processing the command")
    
    async def _handle_analyze_members(self, interaction: discord.Interaction, limit: int):
        """Analyze all members"""
        guild = interaction.guild
        
        # Get member stats from database
        all_stats = await self.bot.db.get_all_member_stats(guild.id, days=30)
        
        if not all_stats:
            await interaction.followup.send("No member activity data found.")
            return
        
        # Sort by total messages
        sorted_stats = sorted(all_stats, key=lambda x: x['total_messages'], reverse=True)
        
        embed = discord.Embed(
            title="📊 Member Activity Analysis",
            description=f"Top {min(limit, len(sorted_stats))} members by 30-day activity",
            color=discord.Color.blue()
        )
        
        # Format top members
        lines = []
        for i, stat in enumerate(sorted_stats[:limit], 1):
            member = guild.get_member(stat['user_id'])
            if member:
                name = member.display_name
                messages = stat['total_messages']
                days = stat['active_days']
                lines.append(f"`{i:02d}` **{name}** - {messages} msgs, {days} days")
        
        if lines:
            embed.add_field(name="Most Active Members", value="\n".join(lines), inline=False)
        
        # Summary stats
        total_active = sum(1 for s in all_stats if s['total_messages'] >= 10)
        total_members = len(all_stats)
        
        embed.add_field(name="Active Members", value=f"{total_active}/{total_members}", inline=True)
        embed.add_field(name="Activity Rate", value=f"{(total_active/total_members*100):.1f}%", inline=True)
        
        await interaction.followup.send(embed=embed)
    
    async def _handle_show_active(self, interaction: discord.Interaction, limit: int):
        """Show active members"""
        guild = interaction.guild
        active_stats = await self.bot.db.get_active_members(guild.id, threshold=10, days=30)
        
        if not active_stats:
            await interaction.followup.send("No active members found.")
            return
        
        embed = discord.Embed(
            title="✅ Active Members",
            description=f"Members with 10+ messages in last 30 days",
            color=discord.Color.green()
        )
        
        lines = []
        for stat in active_stats[:limit]:
            member = guild.get_member(stat['user_id'])
            if member:
                lines.append(f"• **{member.display_name}** - {stat['total_messages']} messages")
        
        if lines:
            embed.add_field(name=f"Top {len(lines)} Active Members", value="\n".join(lines), inline=False)
        
        embed.set_footer(text=f"Total: {len(active_stats)} active members")
        await interaction.followup.send(embed=embed)
    
    async def _handle_show_inactive(self, interaction: discord.Interaction, limit: int):
        """Show inactive members"""
        guild = interaction.guild
        
        # Get all members with Active role
        active_role = discord.utils.get(guild.roles, name="Active")
        if not active_role:
            await interaction.followup.send("❌ Active role not found")
            return
        
        inactive_members = []
        for member in active_role.members:
            stats = await self.bot.db.get_member_stats(guild.id, member.id, days=30)
            if not stats or stats['total_messages'] < 10:
                inactive_members.append((member, stats['total_messages'] if stats else 0))
        
        if not inactive_members:
            await interaction.followup.send("No inactive members with Active role found.")
            return
        
        # Sort by message count
        inactive_members.sort(key=lambda x: x[1])
        
        embed = discord.Embed(
            title="⚠️ Inactive Members",
            description="Members with Active role but <10 messages in 30 days",
            color=discord.Color.orange()
        )
        
        lines = []
        for member, msg_count in inactive_members[:limit]:
            lines.append(f"• **{member.display_name}** - {msg_count} messages")
        
        if lines:
            embed.add_field(name=f"Top {len(lines)} Inactive Members", value="\n".join(lines), inline=False)
        
        embed.set_footer(text=f"Total: {len(inactive_members)} inactive members")
        await interaction.followup.send(embed=embed)
    
    async def _handle_grant_role(self, interaction: discord.Interaction, member: discord.Member, role: discord.Role):
        """Grant role to member"""
        try:
            await member.add_roles(role)
            await interaction.followup.send(f"✅ Granted **{role.name}** role to {member.mention}")
        except discord.Forbidden:
            await interaction.followup.send("❌ I don't have permission to manage that role")
        except Exception as e:
            await interaction.followup.send(f"❌ Error granting role: {str(e)}")
    
    async def _handle_remove_role(self, interaction: discord.Interaction, member: discord.Member, role: discord.Role):
        """Remove role from member"""
        try:
            await member.remove_roles(role)
            await interaction.followup.send(f"✅ Removed **{role.name}** role from {member.mention}")
        except discord.Forbidden:
            await interaction.followup.send("❌ I don't have permission to manage that role")
        except Exception as e:
            await interaction.followup.send(f"❌ Error removing role: {str(e)}")
    
    async def _handle_check_member(self, interaction: discord.Interaction, member: discord.Member):
        """Check specific member stats"""
        stats = await self.bot.db.get_member_stats(interaction.guild_id, member.id, days=30)
        
        embed = discord.Embed(
            title=f"📊 Stats for {member.display_name}",
            color=discord.Color.blue()
        )
        
        if stats and stats['total_messages'] > 0:
            embed.add_field(name="30-Day Activity", 
                          value=f"Messages: {stats['total_messages']}\nActive Days: {stats['active_days']}", 
                          inline=False)
            
            # Check qualification
            if stats['total_messages'] >= 10:
                status = "✅ Qualifies for Active"
            else:
                status = f"❌ Needs {10 - stats['total_messages']} more messages"
            
            embed.add_field(name="Active Status", value=status, inline=False)
        else:
            embed.description = "No activity recorded in the last 30 days"
        
        # Show current roles
        roles = [r.name for r in member.roles if r.name != "@everyone"]
        if roles:
            embed.add_field(name="Current Roles", value=", ".join(roles), inline=False)
        
        await interaction.followup.send(embed=embed)
    
    async def _handle_refresh_stats(self, interaction: discord.Interaction):
        """Refresh all member stats"""
        guild = interaction.guild
        
        embed = discord.Embed(
            title="🔄 Refreshing Member Stats",
            description="This may take a moment...",
            color=discord.Color.blue()
        )
        msg = await interaction.followup.send(embed=embed)
        
        # Get engagement cog and run update
        engagement_cog = self.bot.get_cog('EngagementCog')
        if engagement_cog:
            await engagement_cog.update_all_members(guild)
            
            embed.title = "✅ Stats Refreshed"
            embed.description = "All member statistics have been updated"
            embed.color = discord.Color.green()
            
            await msg.edit(embed=embed)
        else:
            await msg.edit(content="❌ Engagement cog not found")

async def setup(bot):
    await bot.add_cog(AdminCommands(bot))
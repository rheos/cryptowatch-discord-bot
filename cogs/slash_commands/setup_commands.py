"""
Setup commands for bot configuration
/setup for simple toggles, dedicated commands for complex configurations
"""
import discord
from discord import app_commands
from discord.ext import commands
import logging
from typing import Optional, List
from datetime import datetime, timedelta
import asyncio
import subprocess
import pytz
import json
import os
from .base import SlashCommandBase
from .utils import db_helpers

logger = logging.getLogger('discord-bot.setup_commands')

# Popular timezones to show by default (25 max for Discord)
POPULAR_TIMEZONES = [
    ("New York / Boston / Miami (ET)", "America/New_York"),
    ("Los Angeles / Vancouver / Seattle (PT)", "America/Los_Angeles"),
    ("Chicago / Houston / Dallas (CT)", "America/Chicago"),
    ("Denver / Phoenix (MT)", "America/Denver"),
    ("Toronto / Montreal (ET)", "America/Toronto"),
    ("Mexico City", "America/Mexico_City"),
    ("São Paulo / Rio (Brazil)", "America/Sao_Paulo"),
    ("Buenos Aires (Argentina)", "America/Argentina/Buenos_Aires"),
    ("London / Dublin (UK/Ireland)", "Europe/London"),
    ("Paris / Berlin / Amsterdam (CET)", "Europe/Paris"),
    ("Madrid / Rome (CET)", "Europe/Madrid"),
    ("Athens / Helsinki (EET)", "Europe/Athens"),
    ("Moscow / St. Petersburg", "Europe/Moscow"),
    ("Dubai / Abu Dhabi (UAE)", "Asia/Dubai"),
    ("Mumbai / Delhi / Kolkata (India)", "Asia/Kolkata"),
    ("Bangkok / Jakarta (SE Asia)", "Asia/Bangkok"),
    ("Singapore / Kuala Lumpur", "Asia/Singapore"),
    ("Hong Kong", "Asia/Hong_Kong"),
    ("Shanghai / Beijing (China)", "Asia/Shanghai"),
    ("Tokyo / Osaka (Japan)", "Asia/Tokyo"),
    ("Seoul (South Korea)", "Asia/Seoul"),
    ("Sydney / Melbourne (AEDT)", "Australia/Sydney"),
    ("Perth (AWST)", "Australia/Perth"),
    ("Auckland / Wellington (NZ)", "Pacific/Auckland"),
    ("Honolulu (Hawaii)", "Pacific/Honolulu"),
]

class SetupCommands(SlashCommandBase):
    """Setup commands for bot configuration"""
    
    @app_commands.command(name="setup", description="Configure bot settings for this server")
    @app_commands.describe(
        action="Configuration action to perform"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="📋 Show Configuration", value="show"),
        app_commands.Choice(name="🔄 Toggle Engagement Tracking", value="engagement"),
        app_commands.Choice(name="⚖️ Toggle Engagement Enforcement", value="enforce_engagement"),
        app_commands.Choice(name="📈 Toggle Market Events", value="market"),
        app_commands.Choice(name="💹 Toggle Market Display", value="market_display"),
        app_commands.Choice(name="📉 Check Engagement Status", value="engagement_status"),
    ])
    @app_commands.default_permissions(administrator=True)
    async def setup_command(self, interaction: discord.Interaction, action: str):
        """Main setup command for simple actions"""
        await interaction.response.defer(ephemeral=True)
        
        if action == "show":
            await self._handle_show(interaction)
        elif action == "engagement":
            await self._handle_toggle_engagement(interaction)
        elif action == "enforce_engagement":
            await self._handle_toggle_enforcement(interaction)
        elif action == "market":
            await self._handle_toggle_market(interaction)
        elif action == "market_display":
            await self._handle_toggle_market_display(interaction)
        elif action == "engagement_status":
            await self._handle_engagement_status(interaction)
    
    @app_commands.command(name="setup_timezone", description="Configure a timezone display channel")
    @app_commands.describe(
        channel="Voice channel to display the timezone",
        timezone="Timezone to display (type to search all 597 timezones)"
    )
    @app_commands.default_permissions(administrator=True)
    async def setup_timezone_command(self, interaction: discord.Interaction,
                                    channel: discord.VoiceChannel,
                                    timezone: str):
        """Setup timezone channel with autocomplete"""
        await interaction.response.defer(ephemeral=True)
        await self._handle_setup_timezone(interaction, channel, timezone)
    
    @setup_timezone_command.autocomplete('timezone')
    async def timezone_autocomplete(self, interaction: discord.Interaction, 
                                   current: str) -> List[app_commands.Choice[str]]:
        """Autocomplete for timezone selection"""
        choices = []
        
        if not current:
            # No input - show popular timezones
            for name, tz in POPULAR_TIMEZONES[:25]:
                choices.append(app_commands.Choice(name=name, value=tz))
        else:
            # User is typing - search all timezones
            current_lower = current.lower()
            
            # First, check popular timezones
            for name, tz in POPULAR_TIMEZONES:
                if current_lower in name.lower() or current_lower in tz.lower():
                    choices.append(app_commands.Choice(name=name, value=tz))
            
            # Then search all timezones
            for tz in pytz.all_timezones:
                if current_lower in tz.lower():
                    # Format nicely
                    parts = tz.split('/')
                    if len(parts) >= 2:
                        region = parts[0].replace('_', ' ')
                        city = parts[-1].replace('_', ' ')
                        display_name = f"{city} ({region})"
                    else:
                        display_name = tz.replace('_', ' ')
                    
                    # Avoid duplicates from popular list
                    if not any(c.value == tz for c in choices):
                        choices.append(app_commands.Choice(name=display_name, value=tz))
                
                # Stop at 25 (Discord limit)
                if len(choices) >= 25:
                    break
        
        return choices[:25]
    
    async def alert_type_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        """Autocomplete for alert types including dynamic signal sources"""
        choices = []

        # Add static alert types
        static_alerts = [
            ("Market Events", "market_events"),
            ("Funding Rates", "funding"),
            ("General Alerts", "alerts"),
        ]

        for name, value in static_alerts:
            if current.lower() in name.lower():
                choices.append(app_commands.Choice(name=name, value=value))

        # Fetch signal sources from API
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                api_base = self.bot.config.get('api_base_url', 'https://example.com/api')
                async with session.get(f"{api_base}/signals/sources?active_only=true") as response:
                    if response.status == 200:
                        data = await response.json()
                        sources = data.get("sources", [])

                        for source in sources:
                            source_name = f"📡 {source.get('name', source['source_id'])}"
                            source_value = f"signal_{source['source_id']}"

                            if current.lower() in source_name.lower():
                                choices.append(app_commands.Choice(name=source_name, value=source_value))
        except Exception as e:
            logger.error(f"Error fetching signal sources for autocomplete: {e}")

        return choices[:25]  # Discord limit

    @app_commands.command(name="setup_alerts", description="Configure alert channels")
    @app_commands.describe(
        channel="Text channel for alerts",
        alert_type="Type of alerts for this channel"
    )
    @app_commands.autocomplete(alert_type=alert_type_autocomplete)
    @app_commands.default_permissions(administrator=True)
    async def setup_alerts_command(self, interaction: discord.Interaction,
                                  channel: discord.TextChannel,
                                  alert_type: str):
        """Setup alert channels"""
        await interaction.response.defer(ephemeral=True)
        await self._handle_setup_alerts(interaction, channel, alert_type)
    
    @app_commands.command(name="setup_market_channels", description="Configure market event channels")
    @app_commands.describe(
        countdown_channel="Voice channel for market countdown",
        schedule_channel="Text channel for market schedule"
    )
    @app_commands.default_permissions(administrator=True)
    async def setup_market_channels_command(self, interaction: discord.Interaction,
                                           countdown_channel: discord.VoiceChannel,
                                           schedule_channel: discord.TextChannel):
        """Setup market event channels"""
        await interaction.response.defer(ephemeral=True)
        await self._handle_setup_market_channels(interaction, countdown_channel, schedule_channel)
    
    async def _handle_show(self, interaction: discord.Interaction):
        """Show current configuration"""
        guild_id = interaction.guild_id
        
        try:
            embed = discord.Embed(
                title="📋 Current Configuration",
                color=discord.Color.blue()
            )
            
            # Get data using helper functions
            settings = await db_helpers.get_guild_settings(self.bot.db.pool, guild_id)
            timezone_channels = await db_helpers.get_timezone_channels(self.bot.db.pool, guild_id)
            features = await db_helpers.get_feature_status(self.bot.db.pool, guild_id)
            channels = await db_helpers.get_configured_channels(self.bot.db.pool, guild_id)
            
            # Show timezone channels
            if timezone_channels:
                tz_lines = []
                for tz_data in timezone_channels:
                    channel = interaction.guild.get_channel(tz_data['channel_id'])
                    if channel:
                        display = tz_data['display_name'] or tz_data['timezone']
                        tz_lines.append(f"• {channel.mention}: **{display}**")
                
                if tz_lines:
                    embed.add_field(name="🕐 Timezone Channels", value="\n".join(tz_lines), inline=False)
            
            # Show engagement channels (welcome, introductions, and engagement log)
            engagement_lines = []
            
            # Get welcome channel
            welcome_channel_id = await self.bot.db.get_setting(guild_id, 'welcome_channel_id')
            if welcome_channel_id:
                welcome_channel = interaction.guild.get_channel(int(welcome_channel_id))
                if welcome_channel:
                    engagement_lines.append(f"👋 Welcome: {welcome_channel.mention}")
            
            # Get introductions channel
            intro_channel_id = await self.bot.db.get_setting(guild_id, 'introductions_channel_id')
            if intro_channel_id:
                intro_channel = interaction.guild.get_channel(int(intro_channel_id))
                if intro_channel:
                    engagement_lines.append(f"💬 Introductions: {intro_channel.mention}")
            
            # Get engagement log channel
            engagement_log_id = await self.bot.db.get_setting(guild_id, 'engagement_log_channel_id')
            if engagement_log_id:
                engagement_log_channel = interaction.guild.get_channel(int(engagement_log_id))
                if engagement_log_channel:
                    engagement_lines.append(f"📝 Engagement Log: {engagement_log_channel.mention}")
            
            if engagement_lines:
                embed.add_field(name="🤝 Engagement Channels", value="\n".join(engagement_lines), inline=False)
            
            # Show configured channels
            channel_lines = []
            channel_names = {
                'market_countdown': '⏱️ Market Countdown',
                'market_schedule': '📅 Market Schedule',
                'funding_alerts': '💰 Funding Alerts',
                'general_alerts': '📢 General Alerts',
                'volatility_alerts': '📊 Volatility Alerts'
            }
            
            for key, channel_id in channels.items():
                if channel_id:
                    channel = interaction.guild.get_channel(channel_id)
                    if channel:
                        name = channel_names.get(key, key.replace('_', ' ').title())
                        channel_lines.append(f"{name}: {channel.mention}")
            
            if channel_lines:
                embed.add_field(name="📢 Alert Channels", value="\n".join(channel_lines), inline=False)
            
            # Show market schedule message ID if set
            if features.get('market'):
                message_id = await self.bot.db.get_setting(guild_id, 'market_schedule_message_id')
                if message_id:
                    embed.add_field(
                        name="📌 Market Schedule Message", 
                        value=f"Message ID: `{message_id}`",
                        inline=False
                    )
            
            # Show enabled features
            feature_list = []
            if features.get('engagement'):
                feature_list.append("✅ Engagement Tracking")
            if features.get('market'):
                feature_list.append("✅ Market Events")
            
            # Get market_display_enabled separately since it might not be in features dict
            market_display = await self.bot.db.get_setting(guild_id, 'market_display_enabled')
            if market_display == 'True' or market_display == 'true':
                feature_list.append("✅ Market Display Channels")
                
            if features.get('funding'):
                feature_list.append("✅ Funding Alerts")
            if features.get('volatility'):
                feature_list.append("✅ Volatility Alerts")
            if features.get('timezone'):
                feature_list.append("✅ Timezone Display")
            
            if feature_list:
                embed.add_field(name="⚙️ Enabled Features", value="\n".join(feature_list), inline=False)
            else:
                embed.add_field(name="⚙️ Enabled Features", value="No features enabled", inline=False)
            
            # Show engagement details if enabled
            if features.get('engagement'):
                eng_details = []
                
                # Get all engagement settings
                messages_threshold = settings.get('messages_threshold')
                days_threshold = settings.get('days_threshold')
                active_days_threshold = await self.bot.db.get_setting(guild_id, 'active_days_threshold')
                warning_days = await self.bot.db.get_setting(guild_id, 'warning_days')
                warning_min_messages = await self.bot.db.get_setting(guild_id, 'warning_min_messages')
                dm_warnings = await self.bot.db.get_setting(guild_id, 'dm_warnings')
                enforce_engagement = await self.bot.db.get_setting(guild_id, 'enforce_engagement')
                
                # Activity requirements
                if messages_threshold:
                    eng_details.append(f"Messages Required: **{messages_threshold}**")
                if days_threshold:
                    eng_details.append(f"Days Lookback: **{days_threshold}**")
                if active_days_threshold:
                    eng_details.append(f"Active Days Required: **{active_days_threshold}**")
                
                # Enforcement status
                if enforce_engagement == 'true':
                    eng_details.append(f"⚖️ **Enforcement: ENABLED** (roles will be removed)")
                else:
                    eng_details.append(f"🛡️ **Enforcement: DISABLED** (tracking only)")
                
                # Warning settings (only show if enforcement is enabled)
                if enforce_engagement == 'true':
                    if warning_days:
                        eng_details.append(f"Warning Period: **{warning_days} days**")
                    if warning_min_messages:
                        eng_details.append(f"Warning Threshold: **{warning_min_messages} messages**")
                    if dm_warnings == 'true':
                        eng_details.append(f"DM Warnings: **Enabled**")
                    else:
                        eng_details.append(f"DM Warnings: **Disabled**")
                
                if eng_details:
                    embed.add_field(name="👥 Engagement Settings", value="\n".join(eng_details), inline=False)
            
            if not timezone_channels and not settings:
                embed.add_field(name="Status", value="No configuration found. Use `/setup` commands to configure.", inline=False)
            
            embed.set_footer(text="Commands: /setup, /setup_timezone, /setup_alerts, /setup_market_channels")
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in setup show: {e}", exc_info=True)
            await interaction.followup.send(f"❌ Error retrieving configuration: {str(e)}")
    
    async def _handle_toggle_engagement(self, interaction: discord.Interaction):
        """Toggle engagement tracking"""
        guild = interaction.guild
        
        # Check current state using helper
        features = await db_helpers.get_feature_status(self.bot.db.pool, guild.id)
        current_state = features.get('engagement', False)
        enable = not current_state
        
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
        
        # Enable/disable engagement using helper
        if enable:
            success = await db_helpers.enable_feature(self.bot.db.pool, guild.id, 'engagement')
            # Also set the default thresholds
            await db_helpers.set_guild_setting(self.bot.db.pool, guild.id, 'messages_threshold', 10)
            await db_helpers.set_guild_setting(self.bot.db.pool, guild.id, 'days_threshold', 30)
            await db_helpers.set_guild_setting(self.bot.db.pool, guild.id, 'warning_days', 7)
            await db_helpers.set_guild_setting(self.bot.db.pool, guild.id, 'warning_min_messages', 7)
            await db_helpers.set_guild_setting(self.bot.db.pool, guild.id, 'dm_warnings', True)
        else:
            success = await db_helpers.disable_feature(self.bot.db.pool, guild.id, 'engagement')
        
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
    
    async def _handle_toggle_enforcement(self, interaction: discord.Interaction):
        """Toggle engagement enforcement (role removal)"""
        guild = interaction.guild
        
        # Check if engagement is enabled first
        features = await db_helpers.get_feature_status(self.bot.db.pool, guild.id)
        if not features.get('engagement', False):
            embed = discord.Embed(
                title="⚠️ Engagement Not Enabled",
                description="You must enable engagement tracking first before enabling enforcement.\nUse `/setup` → **Toggle Engagement Tracking**",
                color=discord.Color.yellow()
            )
            await interaction.followup.send(embed=embed)
            return
        
        # Check current enforcement state
        current_state = await db_helpers.get_guild_setting(self.bot.db.pool, guild.id, 'enforce_engagement')
        current_state = current_state == 'true' if current_state else False
        enable = not current_state
        
        # Toggle enforcement
        await db_helpers.set_guild_setting(self.bot.db.pool, guild.id, 'enforce_engagement', str(enable).lower())
        
        if enable:
            embed = discord.Embed(
                title="⚖️ Engagement Enforcement Enabled",
                description=(
                    "Role removal is now **ACTIVE**:\n"
                    "• Members who don't meet activity thresholds will lose their Active role\n"
                    "• Warnings will be sent before role removal\n"
                    "• NewMembers still need to post introductions to get roles\n\n"
                    "Current thresholds: 10+ messages in 30 days for Active role"
                ),
                color=discord.Color.orange()
            )
        else:
            embed = discord.Embed(
                title="🛡️ Engagement Enforcement Disabled",
                description=(
                    "Role removal is now **DISABLED**:\n"
                    "• Members can still gain Active role by meeting thresholds\n"
                    "• Members will NOT lose roles for inactivity\n"
                    "• Activity tracking continues for statistics\n"
                    "• NewMember introduction system still works"
                ),
                color=discord.Color.blue()
            )
        
        await interaction.followup.send(embed=embed)
    
    async def _handle_toggle_market(self, interaction: discord.Interaction):
        """Toggle market events"""
        guild = interaction.guild
        
        # Check current state using new schema
        features = await db_helpers.get_feature_status(self.bot.db.pool, guild.id)
        current_state = features.get('market', False)
        enable = not current_state
        
        if enable:
            # Check for required channels
            channels = await db_helpers.get_configured_channels(self.bot.db.pool, guild.id)
            has_countdown = channels.get('market_countdown') is not None
            has_schedule = channels.get('market_schedule') is not None
            
            if not has_countdown or not has_schedule:
                missing = []
                if not has_countdown:
                    missing.append("Market Countdown (voice channel)")
                if not has_schedule:
                    missing.append("Market Schedule (text channel)")
                
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
        
        # Enable/disable market events using helper
        if enable:
            success = await db_helpers.enable_feature(self.bot.db.pool, guild.id, 'market')
        else:
            success = await db_helpers.disable_feature(self.bot.db.pool, guild.id, 'market')
        
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
    
    async def _handle_setup_timezone(self, interaction: discord.Interaction, 
                                    channel: discord.VoiceChannel, 
                                    timezone: str):
        """Setup timezone channel"""
        # Validate timezone
        if timezone not in pytz.all_timezones:
            await interaction.followup.send(f"❌ Invalid timezone: {timezone}")
            return
        
        # First, remove any existing timezone configuration for this channel
        # This prevents duplicates when changing a channel's timezone
        await db_helpers.remove_timezone_channel(self.bot.db.pool, interaction.guild_id, channel.id)
        
        # Store in timezone_channels table
        success = await db_helpers.add_timezone_channel(
            self.bot.db.pool,
            interaction.guild_id,
            channel.id,
            timezone,
            None  # display_name
        )
        
        if not success:
            await interaction.followup.send("❌ Failed to configure timezone channel")
            return
        
        embed = discord.Embed(
            title="✅ Timezone Channel Configured",
            description=f"{channel.mention} will now show time for **{timezone}**",
            color=discord.Color.green()
        )
        await interaction.followup.send(embed=embed)
        
        # Update channel name immediately
        try:
            tz = pytz.timezone(timezone)
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
            
            # Get city name
            city_name = timezone.split("/")[1].replace("_", " ").title()
            
            # Special replacements
            if city_name == "Halifax":
                city_name = "PEI"
            elif city_name == "Kolkata":
                city_name = "India"
            
            new_name = f"{city_name} {hour}:{minute_str}{period}"
            await channel.edit(name=new_name)
            logger.info(f"Updated timezone channel name to: {new_name}")
        except Exception as e:
            logger.error(f"Error updating channel name: {e}")
    
    async def _handle_setup_alerts(self, interaction: discord.Interaction,
                                  channel: discord.TextChannel,
                                  alert_type: str):
        """Setup alert channel"""
        # Check if this is a signal source configuration
        if alert_type.startswith('signal_'):
            # Extract source_id from alert_type (remove 'signal_' prefix)
            source_id = alert_type.replace('signal_', '')

            # Try to get the display name from the API
            display_name = source_id.replace('_', ' ').title()  # Default fallback
            try:
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    api_base = self.bot.config.get('api_base_url', 'https://example.com/api')
                    async with session.get(f"{api_base}/signals/sources?active_only=true") as response:
                        if response.status == 200:
                            data = await response.json()
                            sources = data.get("sources", [])
                            for source in sources:
                                if source['source_id'] == source_id:
                                    display_name = source.get('name', display_name)
                                    break
            except Exception as e:
                logger.error(f"Error fetching signal source name: {e}")

            # Get current signal channels mapping or create new one
            import json
            current_mappings_str = await self.bot.db.get_setting(interaction.guild_id, 'signal_channels')

            if current_mappings_str:
                try:
                    current_mappings = json.loads(current_mappings_str)
                except:
                    current_mappings = {}
            else:
                current_mappings = {}

            # Add/update the mapping for this signal source
            current_mappings[source_id] = str(channel.id)

            # Save the updated mappings
            setting_key = 'signal_channels'
            success = await self.bot.db.set_setting(
                interaction.guild_id,
                'signal_channels',
                json.dumps(current_mappings)
            )

            if success:
                # Enable signals for the guild if not already enabled
                await self.bot.db.set_setting(interaction.guild_id, 'signals_enabled', True)
            else:
                # Fallback: setting might not exist, return error
                success = False
        else:
            # Map alert types to setting keys
            setting_map = {
                'market_events': 'market_alerts',  # Note: might not exist yet
                'funding': 'funding_alerts',
                'alerts': 'general_alerts'
            }

            setting_key = setting_map.get(alert_type, alert_type)

            channel_names = {
                'market_events': 'Market Events',
                'funding': 'Funding Rates',
                'alerts': 'General Alerts'
            }
            display_name = channel_names.get(alert_type, alert_type)

            # Store in guild_settings (only for non-signal types)
            success = await self.bot.db.set_setting(
                interaction.guild_id,
                setting_key,
                str(channel.id)
            )

        if not success:
            await interaction.followup.send(f"❌ Failed to configure {alert_type} channel - setting may not be registered")
            return

        embed = discord.Embed(
            title=f"✅ {display_name} Channel Configured",
            description=f"{channel.mention} will receive {display_name.lower()} updates",
            color=discord.Color.green()
        )

        # Add extra info for signal sources
        if alert_type.startswith('signal_'):
            embed.add_field(
                name="📡 Signal Processing Enabled",
                value="TradingView signals will now be distributed to your configured channels.",
                inline=False
            )

        await interaction.followup.send(embed=embed)
    
    async def _ensure_signal_setting_registered(self, setting_key: str, display_name: str):
        """Ensure a signal source setting is registered in the settings_registry"""
        try:
            async with self.bot.db.pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    # Check if setting already exists
                    await cursor.execute(
                        "SELECT setting_id FROM settings_registry WHERE setting_key = %s",
                        (setting_key,)
                    )
                    if await cursor.fetchone():
                        return  # Setting already exists

                    # Get the alerts section id
                    await cursor.execute(
                        "SELECT section_id FROM settings_sections WHERE section_key = 'alerts'"
                    )
                    row = await cursor.fetchone()
                    if not row:
                        logger.error("Alerts section not found in settings_sections")
                        return

                    section_id = row[0]

                    # Register the new setting
                    await cursor.execute("""
                        INSERT INTO settings_registry
                        (setting_key, setting_type, default_value, description, section_id, display_order, is_advanced)
                        VALUES (%s, 'string', NULL, %s, %s, 100, 0)
                    """, (
                        setting_key,
                        f"Channel for {display_name} signals",
                        section_id
                    ))
                    await conn.commit()
                    logger.info(f"Registered new signal setting: {setting_key}")

        except Exception as e:
            logger.error(f"Error registering signal setting {setting_key}: {e}")

    async def _handle_toggle_market_display(self, interaction: discord.Interaction):
        """Toggle market display feature on/off"""
        guild_id = interaction.guild_id
        
        try:
            # Get current state
            current = await self.bot.db.get_setting(guild_id, 'market_display_enabled')
            new_state = not current
            
            # Update setting
            await self.bot.db.set_setting(guild_id, 'market_display_enabled', new_state)
            
            embed = discord.Embed(
                title=f"{'✅ Market Display Enabled' if new_state else '❌ Market Display Disabled'}",
                description=(
                    "Voice channels will update with market data every 5 minutes"
                    if new_state else
                    "Market display updates have been stopped"
                ),
                color=discord.Color.green() if new_state else discord.Color.red()
            )
            
            if new_state:
                # Check if any channels are configured
                async with self.bot.db.pool.acquire() as conn:
                    async with conn.cursor() as cursor:
                        await cursor.execute("""
                            SELECT COUNT(*) FROM market_display_channels
                            WHERE guild_id = %s
                        """, (guild_id,))
                        count = (await cursor.fetchone())[0]
                
                if count == 0:
                    embed.add_field(
                        name="ℹ️ Next Step",
                        value="Use `/market_display add` to configure voice channels",
                        inline=False
                    )
                else:
                    embed.add_field(
                        name="✅ Channels Configured", 
                        value=f"{count} channel(s) will be updated",
                        inline=False
                    )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error toggling market display: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ Failed to toggle market display: {str(e)}",
                ephemeral=True
            )
    
    async def _handle_setup_market_channels(self, interaction: discord.Interaction,
                                           countdown_channel: discord.VoiceChannel,
                                           schedule_channel: discord.TextChannel):
        """Setup market event channels"""
        # Configure countdown channel in guild_settings
        success1 = await self.bot.db.set_setting(
            interaction.guild_id,
            'market_countdown',
            str(countdown_channel.id)
        )
        
        # Configure schedule channel in guild_settings
        success2 = await self.bot.db.set_setting(
            interaction.guild_id,
            'market_schedule',
            str(schedule_channel.id)
        )
        
        if not success1 or not success2:
            await interaction.followup.send("❌ Failed to configure market channels - settings may not be registered")
            return
        
        # Also enable market events
        await self.bot.db.set_setting(
            interaction.guild_id,
            'market_enabled',
            'true'
        )
        
        embed = discord.Embed(
            title="✅ Market Event Channels Configured",
            description=(
                f"**Countdown Channel**: {countdown_channel.mention}\n"
                f"**Schedule Channel**: {schedule_channel.mention}\n\n"
                "Market events have been automatically enabled"
            ),
            color=discord.Color.green()
        )
        await interaction.followup.send(embed=embed)
    
    async def _handle_backfill_engagement(self, interaction: discord.Interaction):
        """Backfill engagement data by calling external script"""
        guild = interaction.guild
        
        # Check if engagement is enabled
        engagement_settings = await self.bot.db.get_engagement_settings(guild.id)
        if not engagement_settings or not engagement_settings.get('enabled'):
            await interaction.followup.send(
                "❌ Engagement tracking is not enabled. Enable it first with `/setup` → Toggle Engagement"
            )
            return
        
        # Send initial status
        embed = discord.Embed(
            title="🔄 Starting Engagement Backfill",
            description="Launching backfill process for 30 days of history...",
            color=discord.Color.blue()
        )
        status_msg = await interaction.followup.send(embed=embed)
        
        try:
            # Launch external backfill script as subprocess
            script_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "scripts", "backfill_engagement.py"
            )
            
            # Run the script with guild ID and 30 days
            process = await asyncio.create_subprocess_exec(
                "python3", script_path,
                "--guild", str(guild.id),
                "--days", "30",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=os.environ.copy()  # Pass environment variables to subprocess
            )
            
            # Update status
            embed.description = "Backfill process running... This may take a few minutes for large servers."
            await status_msg.edit(embed=embed)
            
            # Monitor the process
            update_count = 0
            while process.returncode is None:
                await asyncio.sleep(5)  # Check every 5 seconds
                update_count += 1
                
                # Update status every 15 seconds
                if update_count % 3 == 0:
                    embed.description = f"Backfill in progress... ({update_count * 5} seconds elapsed)"
                    await status_msg.edit(embed=embed)
                
                # Timeout after 5 minutes
                if update_count > 60:
                    process.terminate()
                    embed = discord.Embed(
                        title="⏱️ Backfill Timeout",
                        description="Process took too long and was terminated. Try running on fewer days or specific channels.",
                        color=discord.Color.yellow()
                    )
                    await status_msg.edit(embed=embed)
                    return
            
            # Get output
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                # Success - get summary from database
                summary = await self.bot.db.get_activity_summary(guild.id)
                
                if summary:
                    embed = discord.Embed(
                        title="✅ Engagement Backfill Complete",
                        description=(
                            f"Successfully backfilled engagement data\n"
                            f"**Period**: {summary.get('earliest_date')} to {summary.get('latest_date')}\n"
                            f"**Total Messages**: {summary.get('total_messages', 0):,}\n"
                            f"**Active Members**: {summary.get('unique_members', 0)}"
                        ),
                        color=discord.Color.green()
                    )
                else:
                    embed = discord.Embed(
                        title="✅ Backfill Complete",
                        description="Process completed successfully. Use `/setup` → Check Engagement Status for details.",
                        color=discord.Color.green()
                    )
            else:
                # Error occurred
                error_msg = stderr.decode('utf-8') if stderr else "Unknown error"
                embed = discord.Embed(
                    title="❌ Backfill Failed",
                    description=f"Process failed: {error_msg[:200]}",
                    color=discord.Color.red()
                )
            
            await status_msg.edit(embed=embed)
            
        except Exception as e:
            logger.error(f"Error launching backfill: {e}", exc_info=True)
            embed = discord.Embed(
                title="❌ Failed to Launch Backfill",
                description=f"Could not start backfill process: {str(e)}",
                color=discord.Color.red()
            )
            await status_msg.edit(embed=embed)
    
    async def _handle_engagement_status(self, interaction: discord.Interaction):
        """Check status of engagement data"""
        guild = interaction.guild
        
        try:
            # Get activity summary from database
            summary = await self.bot.db.get_activity_summary(guild.id)
            
            if not summary:
                await interaction.followup.send(
                    "ℹ️ No engagement data found. Use `/setup` → Backfill Engagement Data to populate."
                )
                return
            
            embed = discord.Embed(
                title="📊 Engagement Data Status",
                color=discord.Color.blue()
            )
            
            # Add summary fields
            embed.add_field(
                name="Data Coverage",
                value=(
                    f"**Earliest Date**: {summary.get('earliest_date', 'N/A')}\n"
                    f"**Latest Date**: {summary.get('latest_date', 'N/A')}\n"
                    f"**Total Days**: {summary.get('total_days', 0)}"
                ),
                inline=True
            )
            
            embed.add_field(
                name="Activity Stats",
                value=(
                    f"**Total Messages**: {summary.get('total_messages', 0):,}\n"
                    f"**Active Members**: {summary.get('unique_members', 0)}\n"
                    f"**Avg Messages/Day**: {summary.get('avg_messages_per_day', 0):.1f}"
                ),
                inline=True
            )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error checking status: {e}", exc_info=True)
            await interaction.followup.send(f"❌ Error checking status: {str(e)}")

async def setup(bot):
    await bot.add_cog(SetupCommands(bot))
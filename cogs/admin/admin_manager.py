"""
Admin management module - handles all admin business logic
This module contains the actual implementation of admin features.
Slash commands should just call these methods.
"""
import discord
import asyncio
import os
import re
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone

logger = logging.getLogger('discord-bot.admin_manager')


class AdminManager:
    """Handles all admin operations - analysis, member management, backfill, etc."""
    
    def __init__(self, bot):
        self.bot = bot
    
    async def analyze_activity(self, guild: discord.Guild, limit: int = 10) -> discord.Embed:
        """Analyze member activity and return formatted embed"""
        engagement_cog = self.bot.get_cog('EngagementCog')
        if not engagement_cog:
            raise ValueError("Engagement system not loaded")
        
        # Get configured lookback period from database
        settings = await self.bot.db.get_engagement_settings(guild.id)
        lookback_days = settings.get('days_threshold', 30) if settings else 30
        
        stats = await engagement_cog.activity_tracker.get_all_member_stats(guild.id, lookback_days)
        if not stats:
            return discord.Embed(
                title="📊 Activity Analysis",
                description="No activity data found",
                color=discord.Color.blue()
            )
        
        sorted_stats = sorted(stats, key=lambda x: x['total_messages'], reverse=True)
        if limit:
            sorted_stats = sorted_stats[:limit]
        
        lines = []
        for i, stat in enumerate(sorted_stats, 1):
            member = guild.get_member(stat['user_id'])
            if member:
                active_days = stat.get('active_days', 0)
                lines.append(f"{i}. **{member.display_name}** - {stat['total_messages']} msgs, {active_days} days")
        
        # Get message threshold for active status
        messages_threshold = settings.get('messages_threshold', 10) if settings else 10
        
        total_active = sum(1 for s in stats if s['total_messages'] >= messages_threshold)
        embed = discord.Embed(
            title=f"📊 Activity Analysis (Last {lookback_days} Days)",
            description="\n".join(lines) if lines else "No data",
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"{total_active}/{len(stats)} active ({messages_threshold}+ msgs in {lookback_days} days)")
        return embed
    
    async def get_active_members(self, guild: discord.Guild, limit: int = 10) -> discord.Embed:
        """Get list of active members"""
        engagement_cog = self.bot.get_cog('EngagementCog')
        if not engagement_cog:
            raise ValueError("Engagement system not loaded")
        
        # Get configured thresholds from database
        settings = await self.bot.db.get_engagement_settings(guild.id)
        lookback_days = settings.get('days_threshold', 30) if settings else 30
        messages_threshold = settings.get('messages_threshold', 10) if settings else 10
        
        stats = await engagement_cog.activity_tracker.get_active_members(guild.id, messages_threshold, lookback_days)
        if not stats:
            return discord.Embed(
                title="✅ Active Members",
                description="No active members found",
                color=discord.Color.green()
            )
        
        lines = []
        stats_to_show = stats[:limit] if limit else stats
        for stat in stats_to_show:
            member = guild.get_member(stat['user_id'])
            if member:
                active_days = stat.get('active_days', 0)
                lines.append(f"• **{member.display_name}** - {stat['total_messages']} msgs, {active_days} days")
        
        embed = discord.Embed(
            title=f"✅ Active Members (Last {lookback_days} Days)",
            description="\n".join(lines) if lines else "None",
            color=discord.Color.green()
        )
        embed.set_footer(text=f"Total: {len(stats)} active ({messages_threshold}+ msgs)")
        return embed
    
    async def get_inactive_members(self, guild: discord.Guild, limit: int = 10) -> discord.Embed:
        """Get list of inactive members with Active role"""
        engagement_cog = self.bot.get_cog('EngagementCog')
        if not engagement_cog:
            raise ValueError("Engagement system not loaded")
        
        # Get configured thresholds from database
        settings = await self.bot.db.get_engagement_settings(guild.id)
        lookback_days = settings.get('days_threshold', 30) if settings else 30
        messages_threshold = settings.get('messages_threshold', 10) if settings else 10
        
        active_role = discord.utils.get(guild.roles, name="Active")
        if not active_role:
            return discord.Embed(
                title="⚠️ Inactive Members",
                description="Active role not found",
                color=discord.Color.orange()
            )
        
        inactive = []
        for member in active_role.members:
            activity = await engagement_cog.activity_tracker.get_member_activity(guild.id, member.id, lookback_days)
            if activity['messages'] < messages_threshold:
                inactive.append((member, activity['messages']))
        
        if not inactive:
            return discord.Embed(
                title="⚠️ Inactive Members",
                description="No inactive members with Active role",
                color=discord.Color.orange()
            )
        
        inactive.sort(key=lambda x: x[1])
        inactive_to_show = inactive[:limit] if limit else inactive
        lines = [f"• **{m.display_name}** - {msgs} msgs" for m, msgs in inactive_to_show]
        
        embed = discord.Embed(
            title=f"⚠️ Inactive Members (Last {lookback_days} Days)",
            description="\n".join(lines),
            color=discord.Color.orange()
        )
        embed.set_footer(text=f"Total: {len(inactive)} below {messages_threshold} msgs")
        return embed
    
    async def check_member_stats(self, guild: discord.Guild, member: discord.Member) -> discord.Embed:
        """Check individual member statistics"""
        engagement_cog = self.bot.get_cog('EngagementCog')
        if not engagement_cog:
            raise ValueError("Engagement system not loaded")
        
        # Get configured thresholds from database
        settings = await self.bot.db.get_engagement_settings(guild.id)
        lookback_days = settings.get('days_threshold', 30) if settings else 30
        threshold = settings.get('messages_threshold', 10) if settings else 10
        
        activity = await engagement_cog.activity_tracker.get_member_activity(guild.id, member.id, lookback_days)
        
        embed = discord.Embed(
            title=f"📊 {member.display_name}",
            color=discord.Color.blue()
        )
        embed.add_field(
            name=f"{lookback_days}-Day Stats",
            value=f"Messages: {activity['messages']}\nActive Days: {activity.get('active_days', 0)}",
            inline=False
        )
        
        status = "✅ Active" if activity['messages'] >= threshold else f"❌ Needs {threshold - activity['messages']} more"
        embed.add_field(name="Status", value=status, inline=False)
        
        return embed
    
    async def run_backfill(self, guild: discord.Guild, days: int = 30) -> Dict[str, Any]:
        """Run backfill script and return results"""
        script_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "scripts", "backfill_engagement.py"
        )
        
        # Track start time
        start_time = asyncio.get_event_loop().time()
        
        process = await asyncio.create_subprocess_exec(
            "python3", script_path,
            "--guild", str(guild.id),
            "--days", str(days),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        # Calculate elapsed time
        elapsed = asyncio.get_event_loop().time() - start_time
        
        if process.returncode != 0:
            return {
                'success': False,
                'error': stderr.decode()[:200] if stderr else "Unknown error",
                'elapsed': elapsed
            }
        
        # Parse output for statistics
        output = stdout.decode() if stdout else ""
        lines = output.split('\n')
        
        stats = {
            'channels_scanned': 0,
            'messages_processed': 0,
            'members_found': 0,
            'records_updated': 0
        }
        
        for line in lines:
            if "Found" in line and "accessible text channels" in line:
                match = re.search(r'Found (\d+) accessible', line)
                if match:
                    stats['channels_scanned'] = int(match.group(1))
            elif "Guild scan complete:" in line:
                match = re.search(r'Guild scan complete: (\d+) members', line)
                if match:
                    stats['members_found'] = int(match.group(1))
            elif "Total messages to store:" in line:
                match = re.search(r'Total messages to store: (\d+)', line)
                if match:
                    stats['messages_processed'] = int(match.group(1))
            elif "Successfully inserted/updated" in line:
                match = re.search(r'inserted/updated (\d+) activity', line)
                if match:
                    stats['records_updated'] = int(match.group(1))
        
        return {
            'success': True,
            'stats': stats,
            'elapsed': elapsed
        }
    
    async def get_engagement_settings(self, guild: discord.Guild) -> discord.Embed:
        """Get current engagement settings"""
        settings = await self.bot.db.get_engagement_settings(guild.id)
        
        embed = discord.Embed(title="⚙️ Engagement Settings", color=discord.Color.blue())
        
        if settings:
            embed.add_field(name="Enabled", value="✅" if settings.get('enabled') else "❌", inline=True)
            embed.add_field(name="Messages Required", value=f"{settings.get('messages_threshold', 10)}", inline=True)
            embed.add_field(name="Lookback Period", value=f"{settings.get('days_threshold', 30)} days", inline=True)
            
            active_days = settings.get('active_days_threshold')
            if active_days:
                embed.add_field(name="Active Days Required", value=f"{active_days} days", inline=True)
            else:
                embed.add_field(name="Active Days Required", value="Not set", inline=True)
        else:
            embed.description = "Using defaults"
        
        # Check for intro channel
        intro_id = await self.bot.db.get_setting(guild.id, 'introductions_channel_id')
        if intro_id:
            channel = guild.get_channel(int(intro_id))
            if channel:
                embed.add_field(name="Intro Channel", value=channel.mention, inline=False)
        
        # Check for welcome channel
        welcome_id = await self.bot.db.get_setting(guild.id, 'welcome_channel_id')
        if welcome_id:
            channel = guild.get_channel(int(welcome_id))
            if channel:
                embed.add_field(name="Welcome Channel", value=channel.mention, inline=False)
        
        return embed
    
    async def configure_thresholds(self, guild: discord.Guild, 
                                  messages: Optional[int] = None,
                                  active_days: Optional[int] = None,
                                  period: Optional[int] = None) -> discord.Embed:
        """Configure engagement thresholds"""
        updates = []
        
        # Validate and update message threshold
        if messages is not None:
            if messages < 1 or messages > 1000:
                raise ValueError("Messages must be between 1 and 1000")
            success = await self.bot.db.set_setting(guild.id, 'messages_threshold', str(messages))
            if success:
                updates.append(f"✅ Message threshold set to **{messages}**")
            else:
                updates.append(f"❌ Failed to set message threshold")
        
        # Validate and update active days threshold
        if active_days is not None:
            if active_days < 1 or active_days > 365:
                raise ValueError("Active days must be between 1 and 365")
            success = await self.bot.db.set_setting(guild.id, 'active_days_threshold', str(active_days))
            if success:
                updates.append(f"✅ Active days requirement set to **{active_days}**")
            else:
                updates.append(f"❌ Failed to set active days requirement")
        
        # Validate and update period (days to look back)
        if period is not None:
            if period < 1 or period > 365:
                raise ValueError("Period must be between 1 and 365 days")
            success = await self.bot.db.set_setting(guild.id, 'days_threshold', str(period))
            if success:
                updates.append(f"✅ Lookback period set to **{period} days**")
            else:
                updates.append(f"❌ Failed to set lookback period")
        
        # Get current settings to show
        settings = await self.bot.db.get_engagement_settings(guild.id)
        
        embed = discord.Embed(
            title="⚙️ Engagement Configuration Updated",
            description="\n".join(updates) if updates else "No changes made",
            color=discord.Color.green()
        )
        
        # Show new configuration
        embed.add_field(
            name="Current Settings",
            value=(
                f"**Messages Required**: {settings.get('messages_threshold', 10)}\n"
                f"**Active Days Required**: {settings.get('active_days_threshold', 'Not set')}\n"
                f"**Lookback Period**: {settings.get('days_threshold', 30)} days"
            ),
            inline=False
        )
        
        embed.set_footer(text="Run /admin → Refresh Roles to apply changes")
        return embed
    
    async def set_channel(self, guild: discord.Guild, channel_type: str, channel: discord.TextChannel) -> str:
        """Set a channel for engagement features"""
        if channel_type == "welcome":
            success = await self.bot.db.set_setting(guild.id, 'welcome_channel_id', str(channel.id))
            if success:
                return f"✅ Set {channel.mention} as welcome channel\nNew member welcome messages will be sent here"
            else:
                return f"❌ Failed to set welcome channel - setting not registered in database\nPlease contact the bot administrator"
        
        elif channel_type == "intro":
            success = await self.bot.db.set_setting(guild.id, 'introductions_channel_id', str(channel.id))
            if success:
                return f"✅ Set {channel.mention} as introductions channel\nNew members must post 50+ chars here to get Member role"
            else:
                return f"❌ Failed to set introductions channel - setting not registered in database\nPlease contact the bot administrator"
        
        elif channel_type == "engagement_log":
            success = await self.bot.db.set_setting(guild.id, 'engagement_log_channel_id', str(channel.id))
            if success:
                return f"✅ Set {channel.mention} as engagement log channel\nWarning messages and role changes will be posted here"
            else:
                return f"❌ Failed to set engagement log channel - setting not registered in database\nPlease contact the bot administrator"
        
        else:
            return f"❌ Unknown channel type: {channel_type}"
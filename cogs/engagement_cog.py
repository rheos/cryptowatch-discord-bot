import discord
from discord.ext import commands, tasks
import json
import logging
from datetime import datetime, timedelta
from collections import defaultdict
import asyncio

class EngagementCog(commands.Cog):
    def __init__(self, bot, config=None):
        self.bot = bot
        self.config = config or bot.config
        self.logger = logging.getLogger('engagement')
        
        # Configure logger
        handler = logging.FileHandler('logs/engagement.log')
        handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
        
        # Check if engagement is enabled
        self.enabled = self.config.get('engagement', {}).get('enabled', False)
        
        # Role names from config
        engagement_config = self.config.get('engagement', {})
        roles_config = engagement_config.get('roles', {})
        self.NEWMEMBER_ROLE = roles_config.get('new_member', 'NewMember')
        self.MEMBER_ROLE = roles_config.get('member', 'Member')
        self.ACTIVE_ROLE = roles_config.get('active', 'Active')
        self.VACATION_ROLE = roles_config.get('vacation', 'Vacation')
        
        # Activity thresholds from config
        thresholds_config = engagement_config.get('thresholds', {})
        self.ACTIVE_MESSAGES_THRESHOLD = thresholds_config.get('active_messages', 10)
        self.ACTIVE_DAYS_THRESHOLD = thresholds_config.get('active_days', 30)
        
        # Channel names from config
        self.channels_config = engagement_config.get('channels', {})
        
        # Warning system config
        warnings_config = engagement_config.get('warnings', {})
        self.warnings_enabled = warnings_config.get('enabled', True)
        self.warning_days_before = warnings_config.get('days_before', 7)
        self.dm_warnings_enabled = warnings_config.get('dm_enabled', True)
        self.min_messages_warning = warnings_config.get('min_messages_warning', 7)
        
        # Cache for member activity
        self.member_activity = defaultdict(lambda: {"messages": 0, "last_active": None})
        
        # Cache for warnings sent (to avoid spamming)
        self.warnings_sent = defaultdict(lambda: None)
        
        # Start background tasks only if enabled
        if self.enabled:
            self.check_activity.start()
            self.logger.info("EngagementCog initialized and enabled")
        else:
            self.logger.info("EngagementCog initialized but disabled")
    
    def cog_unload(self):
        self.check_activity.cancel()
    
    @tasks.loop(hours=24)
    async def check_activity(self):
        """Daily check for member activity and role updates"""
        if not self.enabled:
            return
            
        try:
            for guild in self.bot.guilds:
                await self.update_member_roles(guild)
        except Exception as e:
            self.logger.error(f"Error in check_activity: {e}")
    
    @check_activity.before_loop
    async def before_check_activity(self):
        await self.bot.wait_until_ready()
    
    async def update_member_roles(self, guild):
        """Update roles based on member activity"""
        try:
            # Get roles
            newmember_role = discord.utils.get(guild.roles, name=self.NEWMEMBER_ROLE)
            member_role = discord.utils.get(guild.roles, name=self.MEMBER_ROLE)
            active_role = discord.utils.get(guild.roles, name=self.ACTIVE_ROLE)
            vacation_role = discord.utils.get(guild.roles, name=self.VACATION_ROLE)
            
            if not all([newmember_role, member_role, active_role]):
                self.logger.warning(f"Required roles not found in {guild.name}")
                return
            
            # Check each member
            for member in guild.members:
                if member.bot:
                    continue
                
                # Skip if on vacation
                if vacation_role and vacation_role in member.roles:
                    continue
                
                # Get member activity
                activity = await self.get_member_activity(guild, member)
                
                # Check if member needs warning (Active members at risk)
                if active_role in member.roles and self.warnings_enabled:
                    await self.check_warning_needed(guild, member, activity)
                
                # Update roles based on activity
                if activity["messages"] >= self.ACTIVE_MESSAGES_THRESHOLD:
                    # Qualify for Active
                    if active_role not in member.roles:
                        await member.add_roles(active_role)
                        if member_role not in member.roles:
                            await member.add_roles(member_role)
                        if newmember_role in member.roles:
                            await member.remove_roles(newmember_role)
                        self.logger.info(f"Granted Active role to {member.name}")
                elif activity["messages"] > 0:
                    # Qualify for Member
                    if member_role not in member.roles:
                        await member.add_roles(member_role)
                        if newmember_role in member.roles:
                            await member.remove_roles(newmember_role)
                    # Remove Active if they had it
                    if active_role in member.roles:
                        await member.remove_roles(active_role)
                        self.logger.info(f"Removed Active role from {member.name}")
                
        except Exception as e:
            self.logger.error(f"Error updating roles: {e}")
    
    async def get_member_activity(self, guild, member):
        """Get member activity in the last X days"""
        try:
            messages = 0
            cutoff_date = datetime.utcnow() - timedelta(days=self.ACTIVE_DAYS_THRESHOLD)
            
            # Check recent messages in all channels
            for channel in guild.text_channels:
                try:
                    async for message in channel.history(after=cutoff_date, limit=None):
                        if message.author == member and not message.content.startswith('!'):
                            messages += 1
                except discord.Forbidden:
                    continue
            
            return {"messages": messages, "last_active": datetime.utcnow()}
            
        except Exception as e:
            self.logger.error(f"Error getting activity for {member.name}: {e}")
            return {"messages": 0, "last_active": None}
    
    async def check_warning_needed(self, guild, member, activity):
        """Check if member needs a warning about losing Active status"""
        try:
            # Check if they're below threshold
            if activity["messages"] < self.ACTIVE_MESSAGES_THRESHOLD:
                # Check if they would qualify with messages from next X days
                messages_needed = self.ACTIVE_MESSAGES_THRESHOLD - activity["messages"]
                
                # Only warn if they need reasonable number of messages
                if messages_needed <= self.min_messages_warning:
                    # Check if we already warned them recently (within warning period)
                    last_warning = self.warnings_sent.get(member.id)
                    if last_warning:
                        days_since_warning = (datetime.utcnow() - last_warning).days
                        if days_since_warning < self.warning_days_before:
                            return  # Already warned recently
                    
                    # Send warning
                    await self.send_warning(guild, member, activity["messages"], messages_needed)
                    self.warnings_sent[member.id] = datetime.utcnow()
                    
        except Exception as e:
            self.logger.error(f"Error checking warning for {member.name}: {e}")
    
    async def send_warning(self, guild, member, current_messages, messages_needed):
        """Send warning to member about losing Active status"""
        try:
            warning_msg = (
                f"⚠️ **Active Status Warning**\n\n"
                f"Hi {member.mention}! Your Active member status is at risk.\n\n"
                f"**Current activity**: {current_messages} messages in the last 30 days\n"
                f"**Required**: {self.ACTIVE_MESSAGES_THRESHOLD} messages\n"
                f"**You need**: {messages_needed} more messages in the next {self.warning_days_before} days\n\n"
                f"Post in any channel (except bot commands) to maintain your Active status and "
                f"keep access to premium channels!\n\n"
                f"_Note: Quality contributions matter more than quantity. Share your thoughts, "
                f"analysis, or questions about the markets._"
            )
            
            # Try to DM first
            dm_sent = False
            if self.dm_warnings_enabled:
                try:
                    await member.send(warning_msg)
                    dm_sent = True
                    self.logger.info(f"Sent DM warning to {member.name}")
                except discord.Forbidden:
                    self.logger.info(f"Could not DM {member.name} - will post in engagement channel")
                except Exception as e:
                    self.logger.error(f"Error sending DM to {member.name}: {e}")
            
            # Post in engagement log channel
            engagement_channel_id = self.channels_config.get('engagement_log_id')
            engagement_channel = None
            
            if engagement_channel_id:
                engagement_channel = guild.get_channel(engagement_channel_id)
            else:
                # Fallback to name-based search
                engagement_channel_name = self.channels_config.get('engagement_log', 'engagement-log')
                engagement_channel = discord.utils.get(guild.text_channels, name=engagement_channel_name)
            
            if engagement_channel:
                channel_msg = warning_msg
                if dm_sent:
                    channel_msg = f"✅ DM sent to {member.mention}\n\n" + warning_msg
                else:
                    channel_msg = f"❌ Could not DM {member.mention} (DMs disabled)\n\n" + warning_msg
                
                await engagement_channel.send(channel_msg)
                self.logger.info(f"Posted warning in engagement channel for {member.name}")
            else:
                self.logger.warning(f"Engagement log channel not found (ID: {engagement_channel_id})")
                
        except Exception as e:
            self.logger.error(f"Error sending warning to {member.name}: {e}")
    
    @commands.Cog.listener()
    async def on_member_join(self, member):
        """Handle new member joins"""
        try:
            guild = member.guild
            newmember_role = discord.utils.get(guild.roles, name=self.NEWMEMBER_ROLE)
            
            if newmember_role:
                await member.add_roles(newmember_role)
                self.logger.info(f"Added NewMember role to {member.name}")
                
        except Exception as e:
            self.logger.error(f"Error handling member join: {e}")
    
    @commands.Cog.listener()
    async def on_message(self, message):
        """Track member messages for engagement"""
        if message.author.bot or message.content.startswith('!'):
            return
        
        # Update member role if they're new
        if message.guild:
            member = message.author
            guild = message.guild
            
            newmember_role = discord.utils.get(guild.roles, name=self.NEWMEMBER_ROLE)
            member_role = discord.utils.get(guild.roles, name=self.MEMBER_ROLE)
            
            # If user has NewMember role and posts in welcome-chat, upgrade to Member
            if newmember_role and newmember_role in member.roles:
                if message.channel.name == self.channels_config.get('welcome_chat', 'welcome-chat'):
                    if member_role:
                        await member.add_roles(member_role)
                        await member.remove_roles(newmember_role)
                        self.logger.info(f"Upgraded {member.name} from NewMember to Member")
    
    # Admin Commands
    @commands.command()
    @commands.has_permissions(administrator=True)
    async def analyze_members(self, ctx):
        """Analyze member activity statistics"""
        try:
            guild = ctx.guild
            total_members = len([m for m in guild.members if not m.bot])
            
            # Activity buckets
            active_7d = 0
            active_30d = 0
            active_90d = 0
            message_counts = defaultdict(int)
            
            # Analyze each member
            embed = discord.Embed(
                title="Member Activity Analysis",
                description="Analyzing member activity...",
                color=discord.Color.blue()
            )
            status_msg = await ctx.send(embed=embed)
            
            for member in guild.members:
                if member.bot:
                    continue
                
                # Count messages in different time periods
                for days, counter in [(7, 'active_7d'), (30, 'active_30d'), (90, 'active_90d')]:
                    cutoff = datetime.utcnow() - timedelta(days=days)
                    msg_count = 0
                    
                    for channel in guild.text_channels:
                        try:
                            async for message in channel.history(after=cutoff, limit=None):
                                if message.author == member and not message.content.startswith('!'):
                                    msg_count += 1
                        except discord.Forbidden:
                            continue
                    
                    if msg_count > 0:
                        if days == 7:
                            active_7d += 1
                        elif days == 30:
                            active_30d += 1
                            message_counts[member.id] = msg_count
                        elif days == 90:
                            active_90d += 1
            
            # Prepare results
            embed = discord.Embed(
                title="📊 Member Activity Analysis",
                color=discord.Color.green()
            )
            
            embed.add_field(
                name="Total Members",
                value=f"{total_members} (excluding bots)",
                inline=False
            )
            
            embed.add_field(
                name="Active Members",
                value=f"Last 7 days: {active_7d}\n"
                      f"Last 30 days: {active_30d}\n"
                      f"Last 90 days: {active_90d}",
                inline=True
            )
            
            # Message distribution
            msg_buckets = {"0": 0, "1-5": 0, "6-10": 0, "11-20": 0, "21+": 0}
            for count in message_counts.values():
                if count == 0:
                    msg_buckets["0"] += 1
                elif count <= 5:
                    msg_buckets["1-5"] += 1
                elif count <= 10:
                    msg_buckets["6-10"] += 1
                elif count <= 20:
                    msg_buckets["11-20"] += 1
                else:
                    msg_buckets["21+"] += 1
            
            embed.add_field(
                name="30-Day Message Distribution",
                value="\n".join([f"{k} messages: {v} members" for k, v in msg_buckets.items()]),
                inline=True
            )
            
            embed.add_field(
                name="Recommended Grandfather Settings",
                value=f"Days: 30\nMessages: 10\nWould grant Active to: {len([c for c in message_counts.values() if c >= 10])} members",
                inline=False
            )
            
            await status_msg.edit(embed=embed)
            
        except Exception as e:
            self.logger.error(f"Error in analyze_members: {e}")
            await ctx.send(f"Error analyzing members: {e}")
    
    @commands.command()
    @commands.has_permissions(administrator=True)
    async def grandfather_active(self, ctx, *, args):
        """Grant Active role to qualifying members
        Usage: !grandfather_active days:30 messages:10"""
        try:
            # Parse arguments
            params = {}
            for arg in args.split():
                if ':' in arg:
                    key, value = arg.split(':')
                    params[key] = int(value)
            
            days = params.get('days', 30)
            min_messages = params.get('messages', 10)
            
            guild = ctx.guild
            active_role = discord.utils.get(guild.roles, name=self.ACTIVE_ROLE)
            member_role = discord.utils.get(guild.roles, name=self.MEMBER_ROLE)
            
            if not active_role:
                await ctx.send("Active role not found!")
                return
            
            granted = 0
            cutoff = datetime.utcnow() - timedelta(days=days)
            
            embed = discord.Embed(
                title="Grandfathering Active Members",
                description=f"Checking members with {min_messages}+ messages in last {days} days...",
                color=discord.Color.blue()
            )
            status_msg = await ctx.send(embed=embed)
            
            for member in guild.members:
                if member.bot or active_role in member.roles:
                    continue
                
                msg_count = 0
                for channel in guild.text_channels:
                    try:
                        async for message in channel.history(after=cutoff, limit=None):
                            if message.author == member and not message.content.startswith('!'):
                                msg_count += 1
                    except discord.Forbidden:
                        continue
                
                if msg_count >= min_messages:
                    await member.add_roles(active_role)
                    if member_role and member_role not in member.roles:
                        await member.add_roles(member_role)
                    granted += 1
                    self.logger.info(f"Grandfathered {member.name} with {msg_count} messages")
            
            embed = discord.Embed(
                title="✅ Grandfathering Complete",
                description=f"Granted Active role to {granted} members",
                color=discord.Color.green()
            )
            await status_msg.edit(embed=embed)
            
        except Exception as e:
            self.logger.error(f"Error in grandfather_active: {e}")
            await ctx.send(f"Error: {e}")
    
    @commands.command()
    @commands.has_permissions(administrator=True)
    async def check_user(self, ctx, member: discord.Member):
        """Check a user's engagement statistics"""
        try:
            activity = await self.get_member_activity(ctx.guild, member)
            
            embed = discord.Embed(
                title=f"📊 Engagement Stats for {member.display_name}",
                color=discord.Color.blue()
            )
            
            embed.add_field(
                name="30-Day Activity",
                value=f"Messages: {activity['messages']}\n"
                      f"Status: {'✅ Qualifies for Active' if activity['messages'] >= self.ACTIVE_MESSAGES_THRESHOLD else '❌ Below Active threshold'}",
                inline=False
            )
            
            embed.add_field(
                name="Current Roles",
                value=", ".join([role.name for role in member.roles if role.name != "@everyone"]),
                inline=False
            )
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            self.logger.error(f"Error in check_user: {e}")
            await ctx.send(f"Error checking user: {e}")
    
    @commands.command()
    @commands.has_permissions(administrator=True)
    async def grant_active(self, ctx, member: discord.Member):
        """Manually grant Active role to a member"""
        try:
            active_role = discord.utils.get(ctx.guild.roles, name=self.ACTIVE_ROLE)
            member_role = discord.utils.get(ctx.guild.roles, name=self.MEMBER_ROLE)
            
            if not active_role:
                await ctx.send("Active role not found!")
                return
            
            await member.add_roles(active_role)
            if member_role and member_role not in member.roles:
                await member.add_roles(member_role)
            
            await ctx.send(f"✅ Granted Active role to {member.mention}")
            self.logger.info(f"Admin {ctx.author.name} manually granted Active to {member.name}")
            
        except Exception as e:
            self.logger.error(f"Error in grant_active: {e}")
            await ctx.send(f"Error: {e}")
    
    @commands.command()
    @commands.has_permissions(administrator=True)
    async def test_warning(self, ctx, member: discord.Member):
        """Test warning system on a specific member (admin only)"""
        try:
            activity = await self.get_member_activity(ctx.guild, member)
            messages_needed = self.ACTIVE_MESSAGES_THRESHOLD - activity["messages"]
            
            if messages_needed > 0:
                await self.send_warning(ctx.guild, member, activity["messages"], messages_needed)
                await ctx.send(f"✅ Test warning sent to {member.mention}")
            else:
                await ctx.send(f"❌ {member.mention} has enough messages ({activity['messages']}) - no warning needed")
                
        except Exception as e:
            self.logger.error(f"Error in test_warning: {e}")
            await ctx.send(f"Error: {e}")
    
    @commands.command()
    @commands.has_permissions(administrator=True)
    async def grant_vacation(self, ctx, member: discord.Member, *, args=""):
        """Grant vacation role to a member
        Usage: !grant_vacation @member days:30"""
        try:
            vacation_role = discord.utils.get(ctx.guild.roles, name=self.VACATION_ROLE)
            
            if not vacation_role:
                await ctx.send("Vacation role not found!")
                return
            
            # Parse days
            days = 30  # default
            if 'days:' in args:
                days = int(args.split('days:')[1].split()[0])
            
            await member.add_roles(vacation_role)
            
            await ctx.send(f"✅ Granted {days}-day vacation to {member.mention}")
            self.logger.info(f"Admin {ctx.author.name} granted {days}-day vacation to {member.name}")
            
        except Exception as e:
            self.logger.error(f"Error in grant_vacation: {e}")
            await ctx.send(f"Error: {e}")
    
    # User Commands
    @commands.command()
    async def mystats(self, ctx):
        """Check your own engagement statistics"""
        try:
            member = ctx.author
            activity = await self.get_member_activity(ctx.guild, member)
            
            embed = discord.Embed(
                title="📊 Your Engagement Stats",
                color=discord.Color.blue()
            )
            
            # Calculate status message
            if activity['messages'] >= self.ACTIVE_MESSAGES_THRESHOLD:
                status_msg = "✅ Active Member"
            else:
                messages_needed = self.ACTIVE_MESSAGES_THRESHOLD - activity['messages']
                status_msg = f"📈 {messages_needed} more messages needed for Active"
            
            embed.add_field(
                name="30-Day Activity",
                value=f"Messages: {activity['messages']}\nStatus: {status_msg}",
                inline=False
            )
            
            # Check current tier
            active_role = discord.utils.get(ctx.guild.roles, name=self.ACTIVE_ROLE)
            member_role = discord.utils.get(ctx.guild.roles, name=self.MEMBER_ROLE)
            
            if active_role and active_role in member.roles:
                tier = "⭐ Active Member"
            elif member_role and member_role in member.roles:
                tier = "👤 Member"
            else:
                tier = "🆕 New Member"
            
            embed.add_field(
                name="Current Tier",
                value=tier,
                inline=True
            )
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            self.logger.error(f"Error in mystats: {e}")
            await ctx.send("Error checking your stats. Please try again later.")
    
    @commands.command()
    async def vacation(self, ctx):
        """Request vacation mode (Active members only)"""
        try:
            member = ctx.author
            active_role = discord.utils.get(ctx.guild.roles, name=self.ACTIVE_ROLE)
            
            if not active_role or active_role not in member.roles:
                await ctx.send("❌ Vacation mode is only available for Active members!")
                return
            
            await ctx.send(
                f"{member.mention} Please contact an admin to enable vacation mode. "
                f"Vacation mode preserves your Active status for up to 30 days while you're away."
            )
            
        except Exception as e:
            self.logger.error(f"Error in vacation: {e}")
            await ctx.send("Error processing vacation request.")

async def setup(bot):
    await bot.add_cog(EngagementCog(bot))
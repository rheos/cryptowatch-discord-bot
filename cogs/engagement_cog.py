import discord
from discord.ext import commands, tasks
import json
import logging
from datetime import datetime, timedelta
from collections import defaultdict
import asyncio
import aiomysql
import time

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
        
        # Note: enabled status is checked from database in each event handler
        # Not cached here since it can be changed at runtime
        
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
        
        # Parse start date for warnings
        start_after_str = warnings_config.get('start_after', None)
        if start_after_str:
            try:
                self.warnings_start_date = datetime.strptime(start_after_str, '%Y-%m-%d')
                self.logger.info(f"Warnings will start after {start_after_str}")
            except ValueError:
                self.warnings_start_date = None
                self.logger.error(f"Invalid start_after date format: {start_after_str}")
        else:
            self.warnings_start_date = None
        
        # Message buffer to reduce database writes
        self.message_buffer = defaultdict(lambda: defaultdict(int))
        self.buffer_lock = asyncio.Lock()
        self.last_flush_time = time.time()
        
        # Cache for member activity
        self.member_activity = defaultdict(lambda: {"messages": 0, "last_active": None})
        
        # Cache for warnings sent (to avoid spamming)
        self.warnings_sent = defaultdict(lambda: None)
        
        # Start background tasks (they will check database for enabled status)
        self.check_activity.start()
        self.flush_message_buffer.start()
        self.logger.info("EngagementCog initialized")
    
    def cog_unload(self):
        self.check_activity.cancel()
        self.flush_message_buffer.cancel()
        # Flush any remaining messages before unloading
        asyncio.create_task(self._flush_buffer())
    
    @tasks.loop(seconds=60)
    async def flush_message_buffer(self):
        """Flush message buffer at the 30-second mark to avoid conflict with price collection"""
        # Wait until we're at the 30-second mark
        current_second = datetime.now().second
        if current_second < 30:
            await asyncio.sleep(30 - current_second)
        elif current_second > 30:
            await asyncio.sleep(90 - current_second)
        
        # Now we're at the 30-second mark, flush the buffer
        await self._flush_buffer()
    
    async def _flush_buffer(self):
        """Flush the message buffer to database"""
        async with self.buffer_lock:
            if not self.message_buffer:
                return
            
            # Copy and clear buffer
            buffer_copy = dict(self.message_buffer)
            self.message_buffer.clear()
        
        # Batch update to database
        try:
            updates = []
            for guild_id, user_counts in buffer_copy.items():
                for user_id, count in user_counts.items():
                    updates.append((guild_id, user_id, count))
            
            if updates:
                async with self.bot.db.pool.acquire() as conn:
                    async with conn.cursor() as cursor:
                        # Batch update all message counts
                        await cursor.executemany("""
                            INSERT INTO member_activity_daily (guild_id, user_id, activity_date, message_count)
                            VALUES (%s, %s, CURDATE(), %s)
                            ON DUPLICATE KEY UPDATE message_count = message_count + VALUES(message_count)
                        """, updates)
                        
                        # Update last_message_at for all users
                        for guild_id, user_id, _ in updates:
                            await cursor.execute("""
                                INSERT INTO member_status (guild_id, user_id, last_message_at)
                                VALUES (%s, %s, NOW())
                                ON DUPLICATE KEY UPDATE last_message_at = NOW()
                            """, (guild_id, user_id))
                        
                        await conn.commit()
                
                self.logger.info(f"Flushed {len(updates)} user message counts to database")
        except Exception as e:
            self.logger.error(f"Error flushing message buffer: {e}", exc_info=True)
    
    @tasks.loop(hours=24)
    async def check_activity(self):
        """Daily check for member activity and role updates"""
        # Check if engagement is enabled in any guild
        # This task runs for all guilds the bot is in
            
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
            # Get activity from database
            stats = await self.bot.db.get_member_stats(guild.id, member.id, self.ACTIVE_DAYS_THRESHOLD)
            
            if stats:
                return {
                    "messages": stats['total_messages'] or 0,
                    "last_active": stats['last_active_date']
                }
            else:
                return {"messages": 0, "last_active": None}
            
        except Exception as e:
            self.logger.error(f"Error getting activity for {member.name}: {e}")
            return {"messages": 0, "last_active": None}
    
    async def check_warning_needed(self, guild, member, activity):
        """Check if member needs a warning about losing Active status"""
        try:
            # Check if warnings should start yet
            if self.warnings_start_date:
                if datetime.utcnow() < self.warnings_start_date:
                    self.logger.debug(f"Skipping warning for {member.name} - warnings start after {self.warnings_start_date.date()}")
                    return
            
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
            
            # Check if engagement is enabled for this guild
            settings = await self.bot.db.get_engagement_settings(guild.id)
            if not settings or not settings.get('enabled'):
                self.logger.debug(f"Engagement not enabled for guild {guild.name}")
                return
            
            newmember_role = discord.utils.get(guild.roles, name=self.NEWMEMBER_ROLE)
            
            if newmember_role:
                await member.add_roles(newmember_role)
                self.logger.info(f"Added NewMember role to {member.name}")
            else:
                self.logger.warning(f"NewMember role not found in guild {guild.name}")
                
        except Exception as e:
            self.logger.error(f"Error handling member join: {e}", exc_info=True)
    
    @commands.Cog.listener()
    async def on_message(self, message):
        """Track member messages for engagement"""
        if message.author.bot or message.content.startswith('!'):
            return
        
        # Update member role if they're new
        if message.guild:
            member = message.author
            guild = message.guild
            
            # Buffer the message instead of writing to database immediately
            async with self.buffer_lock:
                self.message_buffer[guild.id][member.id] += 1
            
            # Check if engagement is enabled for role assignment
            settings = await self.bot.db.get_engagement_settings(guild.id)
            if not settings or not settings.get('enabled'):
                return
            
            newmember_role = discord.utils.get(guild.roles, name=self.NEWMEMBER_ROLE)
            member_role = discord.utils.get(guild.roles, name=self.MEMBER_ROLE)
            
            # If user has NewMember role and sends their first message, upgrade to Member
            if newmember_role and newmember_role in member.roles:
                if member_role:
                    await member.add_roles(member_role)
                    await member.remove_roles(newmember_role)
                    self.logger.info(f"Upgraded {member.name} from NewMember to Member after first message")
                else:
                    self.logger.warning(f"Member role not found in guild {guild.name}")
    
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
                description="Analyzing community activity...",
                color=discord.Color.blue()
            )
            status_msg = await ctx.send(embed=embed)
            
            # Get activity data from database
            async with self.bot.db.pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    # Get activity for different time periods
                    for days in [7, 30, 90]:
                        await cursor.execute("""
                            SELECT COUNT(DISTINCT user_id) as active_users
                            FROM member_activity_daily
                            WHERE guild_id = %s 
                            AND activity_date >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
                            AND message_count > 0
                        """, (guild.id, days))
                        result = await cursor.fetchone()
                        
                        if days == 7:
                            active_7d = result['active_users']
                        elif days == 30:
                            active_30d = result['active_users']
                        elif days == 90:
                            active_90d = result['active_users']
                    
                    # Get top active members
                    await cursor.execute("""
                        SELECT 
                            user_id,
                            SUM(message_count) as total_messages,
                            COUNT(DISTINCT activity_date) as active_days
                        FROM member_activity_daily
                        WHERE guild_id = %s
                        AND activity_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
                        GROUP BY user_id
                        ORDER BY total_messages DESC
                        LIMIT 10
                    """, (guild.id,))
                    top_members = await cursor.fetchall()
            
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
            
            # Top active members
            if top_members:
                top_list = []
                for i, member_data in enumerate(top_members[:5], 1):
                    member = guild.get_member(member_data['user_id'])
                    if member:
                        top_list.append(
                            f"{i}. {member.mention}: {member_data['total_messages']} msgs "
                            f"({member_data['active_days']} days)"
                        )
                
                if top_list:
                    embed.add_field(
                        name="Top Active Members (30 days)",
                        value="\n".join(top_list),
                        inline=False
                    )
            
            # Add timestamp
            embed.set_footer(text=f"As of {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
            
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
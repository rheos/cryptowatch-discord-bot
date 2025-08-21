"""
Refactored Engagement Cog - Main orchestrator
Coordinates all engagement modules for member activity tracking
"""
import discord
from discord.ext import commands, tasks
import logging
from datetime import datetime
import asyncio

# Import engagement modules
from .engagement.role_manager import RoleManager
from .engagement.activity_tracker import ActivityTracker
from .engagement.warning_system import WarningSystem
from .engagement.welcome_handler import WelcomeHandler


class EngagementCog(commands.Cog):
    """Main engagement cog that orchestrates all modules"""
    
    def __init__(self, bot, config=None):
        self.bot = bot
        self.config = config or bot.config
        self.logger = logging.getLogger('engagement')
        
        # Configure logger
        handler = logging.FileHandler('logs/engagement.log')
        handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
        
        # Initialize modules
        self.role_manager = RoleManager(bot)
        self.activity_tracker = ActivityTracker(bot)
        self.warning_system = WarningSystem(bot)
        self.welcome_handler = WelcomeHandler(bot)
        
        # Start background tasks
        self.check_activity.start()
        self.flush_message_buffer.start()
        self.logger.info("EngagementCog initialized with modular components")
    
    def cog_unload(self):
        """Cleanup when cog is unloaded"""
        self.check_activity.cancel()
        self.flush_message_buffer.cancel()
        # Flush any remaining messages before unloading
        asyncio.create_task(self.activity_tracker.flush_buffer())
    
    # ========== Background Tasks ==========
    
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
        await self.activity_tracker.flush_buffer()
    
    @tasks.loop(hours=24)
    async def check_activity(self):
        """Daily check for member activity and role updates"""
        try:
            for guild in self.bot.guilds:
                # Update roles
                await self.role_manager.update_member_roles(guild)
                
                # Check for warnings
                settings = await self.bot.db.get_engagement_settings(guild.id)
                if settings and settings.get('enabled'):
                    active_role = discord.utils.get(guild.roles, name='Active')
                    if active_role:
                        threshold = settings.get('messages_threshold', 10)
                        for member in active_role.members:
                            if not member.bot:
                                activity = await self.activity_tracker.get_member_activity(
                                    guild.id, member.id, days=30
                                )
                                await self.warning_system.check_warning_needed(
                                    guild, member, activity, threshold
                                )
        except Exception as e:
            self.logger.error(f"Error in check_activity: {e}")
    
    @check_activity.before_loop
    async def before_check_activity(self):
        """Wait until bot is ready before starting activity checks"""
        await self.bot.wait_until_ready()
    
    # ========== Event Listeners ==========
    
    @commands.Cog.listener()
    async def on_member_join(self, member):
        """Handle new member joins"""
        await self.welcome_handler.handle_member_join(member)
    
    @commands.Cog.listener()
    async def on_message(self, message):
        """Track member messages for engagement"""
        if message.author.bot or message.content.startswith('!'):
            return
        
        if message.guild:
            # Track the message
            await self.activity_tracker.track_message(message.guild.id, message.author.id)
            
            # Check if this triggers a role upgrade
            await self.role_manager.handle_new_member_message(message)
    
    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        """Check edited messages for introduction upgrades"""
        # Only check if content actually changed
        if before.content == after.content:
            return
            
        # Skip bot messages
        if after.author.bot:
            return
            
        # Only check in guilds
        if after.guild:
            # Check if the edited message now qualifies for role upgrade
            # (e.g., user edited their intro to make it longer)
            await self.role_manager.handle_new_member_message(after)
    
    # All prefix commands removed - use slash commands instead
    # /engagement for all engagement features


async def setup(bot):
    """Setup function for Discord.py to load this cog"""
    await bot.add_cog(EngagementCog(bot))
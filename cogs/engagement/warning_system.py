"""
Warning system module for engagement
Handles activity warnings for members at risk of losing Active status
"""
import discord
import logging
from datetime import datetime, timedelta
from collections import defaultdict

logger = logging.getLogger('engagement.warning_system')


class WarningSystem:
    """Manages activity warnings for members"""
    
    def __init__(self, bot):
        self.bot = bot
        
        # Warning system defaults
        self.warnings_enabled = True
        self.warning_days_before = 7
        self.dm_warnings_enabled = True
        self.min_messages_warning = 7
        self.warnings_start_date = None
        
        # Cache for warnings sent (to avoid spamming)
        self.warnings_sent = defaultdict(lambda: None)
    
    async def get_warning_settings(self, guild_id):
        """Get warning settings from database"""
        settings = {}
        
        warning_days = await self.bot.db.get_setting(guild_id, 'warning_days')
        if warning_days:
            settings['warning_days'] = int(warning_days)
        else:
            settings['warning_days'] = self.warning_days_before
            
        warning_min_messages = await self.bot.db.get_setting(guild_id, 'warning_min_messages')
        if warning_min_messages:
            settings['warning_min_messages'] = int(warning_min_messages)
        else:
            settings['warning_min_messages'] = self.min_messages_warning
            
        dm_warnings = await self.bot.db.get_setting(guild_id, 'dm_warnings')
        settings['dm_warnings'] = dm_warnings == 'true' if dm_warnings else self.dm_warnings_enabled
        
        return settings
    
    async def check_warning_needed(self, guild, member, activity, threshold=10):
        """Check if member needs a warning about losing Active status"""
        try:
            # Get warning settings
            settings = await self.get_warning_settings(guild.id)
            
            # Check if warnings should start yet
            if self.warnings_start_date:
                if datetime.utcnow() < self.warnings_start_date:
                    logger.debug(f"Skipping warning for {member.name} - warnings start after {self.warnings_start_date.date()}")
                    return
            
            # Check if they're below threshold
            if activity["messages"] < threshold:
                # Check if they would qualify with messages from next X days
                messages_needed = threshold - activity["messages"]
                
                # Only warn if they need reasonable number of messages
                if messages_needed <= settings['warning_min_messages']:
                    # Check if we already warned them recently (within warning period)
                    last_warning = self.warnings_sent.get(member.id)
                    if last_warning:
                        days_since_warning = (datetime.utcnow() - last_warning).days
                        if days_since_warning < settings['warning_days']:
                            return  # Already warned recently
                    
                    # Send warning
                    await self.send_warning(guild, member, activity["messages"], messages_needed, threshold)
                    self.warnings_sent[member.id] = datetime.utcnow()
                    
        except Exception as e:
            logger.error(f"Error checking warning for {member.name}: {e}")
    
    async def send_warning(self, guild, member, current_messages, messages_needed, threshold):
        """Send warning to member about losing Active status"""
        try:
            # Get settings
            settings = await self.get_warning_settings(guild.id)
            
            warning_msg = (
                f"⚠️ **Active Status Warning**\n\n"
                f"Hi {member.mention}! Your Active member status is at risk.\n\n"
                f"**Current activity**: {current_messages} messages in the last 30 days\n"
                f"**Required**: {threshold} messages\n"
                f"**You need**: {messages_needed} more messages in the next {settings['warning_days']} days\n\n"
                f"Post in any channel (except bot commands) to maintain your Active status and "
                f"keep access to premium channels!\n\n"
                f"_Note: Quality contributions matter more than quantity. Share your thoughts, "
                f"analysis, or questions about the markets._"
            )
            
            # Try to DM first
            dm_sent = False
            if settings['dm_warnings']:
                try:
                    await member.send(warning_msg)
                    dm_sent = True
                    logger.info(f"Sent DM warning to {member.name}")
                except discord.Forbidden:
                    logger.info(f"Could not DM {member.name} - will post in engagement channel")
                except Exception as e:
                    logger.error(f"Error sending DM to {member.name}: {e}")
            
            # Post in engagement log channel
            engagement_channel_id = await self.bot.db.get_setting(guild.id, 'engagement_log_channel_id')
            engagement_channel = None
            
            if engagement_channel_id:
                engagement_channel = guild.get_channel(int(engagement_channel_id))
            else:
                # Fallback to name-based search
                engagement_channel = discord.utils.get(guild.text_channels, name='engagement-log')
            
            if engagement_channel:
                channel_msg = warning_msg
                if dm_sent:
                    channel_msg = f"✅ DM sent to {member.mention}\n\n" + warning_msg
                else:
                    channel_msg = f"❌ Could not DM {member.mention} (DMs disabled)\n\n" + warning_msg
                
                await engagement_channel.send(channel_msg)
                logger.info(f"Posted warning in engagement channel for {member.name}")
            else:
                logger.warning(f"Engagement log channel not found")
                
        except Exception as e:
            logger.error(f"Error sending warning to {member.name}: {e}")
    
    async def test_warning(self, guild, member, threshold=10):
        """Test the warning system on a specific member"""
        try:
            # Get member activity
            stats = await self.bot.db.get_member_stats(guild.id, member.id, days=30)
            current_messages = stats['total_messages'] if stats else 0
            messages_needed = threshold - current_messages
            
            if messages_needed > 0:
                await self.send_warning(guild, member, current_messages, messages_needed, threshold)
                return True, f"Test warning sent to {member.mention}"
            else:
                return False, f"{member.mention} has enough messages ({current_messages}) - no warning needed"
                
        except Exception as e:
            logger.error(f"Error in test_warning: {e}")
            return False, f"Error: {e}"
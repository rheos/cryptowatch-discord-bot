"""
Role management module for engagement system
Handles role updates based on member activity
"""
import discord
import logging
from typing import Optional

logger = logging.getLogger('engagement.role_manager')


class RoleManager:
    """Manages role assignments based on member activity"""
    
    def __init__(self, bot):
        self.bot = bot
        self.NEWMEMBER_ROLE = 'NewMember'
        self.MEMBER_ROLE = 'Member'
        self.ACTIVE_ROLE = 'Active'
        self.VACATION_ROLE = 'Vacation'
        
    async def update_member_roles(self, guild):
        """Update roles based on member activity"""
        try:
            # Get engagement settings
            settings = await self.bot.db.get_engagement_settings(guild.id)
            if not settings or not settings.get('enabled'):
                return
            
            # Get thresholds
            messages_threshold = settings.get('messages_threshold', 10)
            days_threshold = settings.get('days_threshold', 30)
            
            # Get roles
            newmember_role = discord.utils.get(guild.roles, name=self.NEWMEMBER_ROLE)
            member_role = discord.utils.get(guild.roles, name=self.MEMBER_ROLE)
            active_role = discord.utils.get(guild.roles, name=self.ACTIVE_ROLE)
            vacation_role = discord.utils.get(guild.roles, name=self.VACATION_ROLE)
            
            if not all([newmember_role, member_role, active_role]):
                logger.warning(f"Required roles not found in {guild.name}")
                return
            
            # Check each member
            for member in guild.members:
                if member.bot:
                    continue
                
                # Skip if on vacation
                if vacation_role and vacation_role in member.roles:
                    continue
                
                # Get member activity
                stats = await self.bot.db.get_member_stats(guild.id, member.id, days_threshold)
                msg_count = stats['total_messages'] if stats else 0
                
                # Update roles based on activity
                if msg_count >= messages_threshold:
                    # Qualify for Active
                    if active_role not in member.roles:
                        await member.add_roles(active_role)
                        if member_role not in member.roles:
                            await member.add_roles(member_role)
                        if newmember_role in member.roles:
                            await member.remove_roles(newmember_role)
                        logger.info(f"Granted Active role to {member.name}")
                elif msg_count > 0:
                    # Qualify for Member
                    if member_role not in member.roles:
                        await member.add_roles(member_role)
                        if newmember_role in member.roles:
                            await member.remove_roles(newmember_role)
                    # Remove Active if they had it
                    if active_role in member.roles:
                        await member.remove_roles(active_role)
                        logger.info(f"Removed Active role from {member.name}")
                
        except Exception as e:
            logger.error(f"Error updating roles: {e}")
    
    async def handle_new_member_message(self, message):
        """Handle role upgrade when new member sends a message"""
        member = message.author
        guild = message.guild
        
        # Check if engagement is enabled
        settings = await self.bot.db.get_engagement_settings(guild.id)
        if not settings or not settings.get('enabled'):
            return False
        
        newmember_role = discord.utils.get(guild.roles, name=self.NEWMEMBER_ROLE)
        member_role = discord.utils.get(guild.roles, name=self.MEMBER_ROLE)
        
        # Check if user has NewMember role and this is in the introductions channel
        if not (newmember_role and newmember_role in member.roles):
            return False
        
        # Get introductions channel ID from database or fall back to name
        intro_channel_id = await self.bot.db.get_setting(guild.id, 'introductions_channel_id')
        
        # Check if this is the introductions channel (by ID or name)
        is_intro_channel = False
        if intro_channel_id:
            is_intro_channel = (str(message.channel.id) == intro_channel_id)
        else:
            # Fallback to channel name if no ID is set
            is_intro_channel = (message.channel.name == 'introductions')
        
        # Only upgrade in introductions channel
        if not is_intro_channel:
            return False
        
        # Check message length requirement (50+ characters)
        if len(message.content) >= 50:
            if member_role:
                await member.add_roles(member_role)
                await member.remove_roles(newmember_role)
                logger.info(f"Upgraded {member.name} from NewMember to Member after 50+ char introduction")
                
                # Send confirmation message
                confirm_embed = discord.Embed(
                    title="✅ Welcome to the Community!",
                    description=(
                        f"Thank you for your introduction, {member.mention}!\n\n"
                        "You now have **Member** access and can see all channels.\n"
                        "Feel free to explore and join the conversation!"
                    ),
                    color=discord.Color.green()
                )
                await message.channel.send(embed=confirm_embed)
                return True
            else:
                logger.warning(f"Member role not found in guild {guild.name}")
        else:
            # Message too short
            await message.channel.send(
                f"{member.mention} Your introduction needs to be at least 50 characters. "
                f"(Currently {len(message.content)} characters)\n"
                "Please tell us a bit more about yourself!",
                delete_after=30  # Delete after 30 seconds
            )
        
        return False
    
    async def grant_vacation_role(self, guild, member, days=30):
        """Grant vacation role to a member"""
        vacation_role = discord.utils.get(guild.roles, name=self.VACATION_ROLE)
        
        if not vacation_role:
            return False, "Vacation role not found!"
        
        await member.add_roles(vacation_role)
        logger.info(f"Granted {days}-day vacation to {member.name}")
        return True, f"Granted {days}-day vacation to {member.mention}"
    
    async def manually_grant_active(self, guild, member):
        """Manually grant Active role to a member"""
        active_role = discord.utils.get(guild.roles, name=self.ACTIVE_ROLE)
        member_role = discord.utils.get(guild.roles, name=self.MEMBER_ROLE)
        
        if not active_role:
            return False, "Active role not found!"
        
        await member.add_roles(active_role)
        if member_role and member_role not in member.roles:
            await member.add_roles(member_role)
        
        logger.info(f"Manually granted Active to {member.name}")
        return True, f"Granted Active role to {member.mention}"
"""
Welcome handler module for engagement system
Handles new member joins and welcome messages
"""
import discord
import logging

logger = logging.getLogger('engagement.welcome_handler')


class WelcomeHandler:
    """Handles new member welcome process"""
    
    def __init__(self, bot):
        self.bot = bot
        self.NEWMEMBER_ROLE = 'NewMember'
    
    async def handle_member_join(self, member):
        """Handle new member joins"""
        try:
            guild = member.guild
            
            # Check if engagement is enabled for this guild
            settings = await self.bot.db.get_engagement_settings(guild.id)
            if not settings or not settings.get('enabled'):
                logger.debug(f"Engagement not enabled for guild {guild.name}")
                return
            
            newmember_role = discord.utils.get(guild.roles, name=self.NEWMEMBER_ROLE)
            
            # Record member join in database with actual join date
            try:
                async with self.bot.db.pool.acquire() as conn:
                    async with conn.cursor() as cursor:
                        # Use member.joined_at for the actual join timestamp
                        await cursor.execute("""
                            INSERT INTO member_status (guild_id, user_id, joined_at)
                            VALUES (%s, %s, %s)
                            ON DUPLICATE KEY UPDATE 
                                joined_at = COALESCE(joined_at, VALUES(joined_at))
                        """, (guild.id, member.id, member.joined_at))
                        await conn.commit()
                        logger.info(f"Recorded join date for {member.name}")
            except Exception as e:
                logger.error(f"Error recording member join date: {e}")
            
            if newmember_role:
                await member.add_roles(newmember_role)
                logger.info(f"Added NewMember role to {member.name}")
                
                # Send welcome message
                await self.send_welcome_message(guild, member)
            else:
                logger.warning(f"NewMember role not found in guild {guild.name}")
                
        except Exception as e:
            logger.error(f"Error handling member join: {e}", exc_info=True)
    
    async def send_welcome_message(self, guild, member):
        """Send welcome message to new member"""
        try:
            # Get welcome channel from database first, then fall back to name lookup
            welcome_channel = None
            welcome_channel_id = await self.bot.db.get_setting(guild.id, 'welcome_channel_id')
            
            if welcome_channel_id:
                welcome_channel = guild.get_channel(int(welcome_channel_id))
                if not welcome_channel:
                    logger.warning(f"Welcome channel ID {welcome_channel_id} not found in {guild.name}")
            
            # Fall back to looking for channel containing 'welcome' in the name
            if not welcome_channel:
                # Find first channel with 'welcome' in the name
                for channel in guild.text_channels:
                    if 'welcome' in channel.name.lower():
                        welcome_channel = channel
                        break
                
                if not welcome_channel:
                    logger.warning(f"Welcome channel not found in {guild.name} (checked ID and channels containing 'welcome')")
                    return
            
            # Get the introductions channel reference
            intro_channel_id = await self.bot.db.get_setting(guild.id, 'introductions_channel_id')
            intro_channel_mention = None
            intro_channel_name = "introductions"
            
            if intro_channel_id:
                intro_channel = guild.get_channel(int(intro_channel_id))
                if intro_channel:
                    intro_channel_mention = intro_channel.mention
                    intro_channel_name = intro_channel.name
            else:
                # Try to find channel containing 'introductions' in the name
                for channel in guild.text_channels:
                    if 'introductions' in channel.name.lower():
                        intro_channel = channel
                        intro_channel_mention = channel.mention
                        intro_channel_name = channel.name
                        break
            
            # Build description with proper channel reference
            if intro_channel_mention:
                channel_instruction = f"Please head to {intro_channel_mention} and tell us about yourself!"
                footer_text = f"Post in #{intro_channel_name} to unlock all channels!"
            else:
                channel_instruction = "Please head to the introductions channel and tell us about yourself!"
                footer_text = "Post your introduction (50+ characters) to unlock all channels!"
            
            welcome_embed = discord.Embed(
                title=f"Welcome to {guild.name}, {member.display_name}! 👋",
                description=(
                    "We're excited to have you join our crypto trading community!\n\n"
                    "**To get started:**\n"
                    f"{channel_instruction}\n\n"
                    "**In your introduction, share:**\n"
                    "• How long have you been in crypto?\n"
                    "• What type of trading are you interested in? (spot, futures, DeFi, etc.)\n"
                    "• What brought you to our community?\n"
                    "• Any specific coins or strategies you're following?\n\n"
                    "Once you post your introduction (50+ characters), you'll automatically "
                    "get Member access to see all channels!"
                ),
                color=discord.Color.green()
            )
            welcome_embed.set_footer(text=footer_text)
            await welcome_channel.send(f"{member.mention}", embed=welcome_embed)
            logger.info(f"Sent welcome message to {member.name} with intro channel: {intro_channel_name}")
            
        except Exception as e:
            logger.error(f"Error sending welcome message: {e}", exc_info=True)
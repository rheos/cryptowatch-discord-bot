"""
Admin commands for server and member management - THIN INTERFACE VERSION
This is a proper thin wrapper that delegates all business logic to modules
"""
import discord
from discord import app_commands
from discord.ext import commands
import logging
from typing import Optional
from .base import SlashCommandBase
from ..admin.admin_manager import AdminManager
from utils.moderation import purge_messages, send_temporary_message

logger = logging.getLogger('discord-bot.admin_commands')

# Purges larger than this require an explicit Delete/Cancel confirmation.
PURGE_CONFIRM_THRESHOLD = 10


class ConfirmPurgeView(discord.ui.View):
    """Delete/Cancel confirmation for a large purge. Only the person who ran the
    command can act on it, and it times out doing nothing after 30s."""

    def __init__(self, invoker_id: int, on_confirm):
        super().__init__(timeout=30)
        self.invoker_id = invoker_id
        self._on_confirm = on_confirm

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.invoker_id:
            await interaction.response.send_message(
                "This confirmation isn't yours.", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Delete", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(content="🧹 Deleting…", view=self)
        await self._on_confirm(interaction)
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(
            content="Cancelled — nothing was deleted.", view=self
        )
        self.stop()


class AdminCommands(SlashCommandBase):
    """Admin commands for server and member management - thin interface"""
    
    def __init__(self, bot):
        super().__init__(bot)
        self.admin_manager = AdminManager(bot)
    
    @app_commands.command(name="admin", description="Server and member management commands")
    @app_commands.describe(
        action="Admin action to perform",
        member="Target member (only for: Check Member, Grant Vacation, Test Warning)",
        limit="Number of results (only for: Analyze, Active, Inactive, Backfill)"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="📊 Analyze Activity", value="analyze"),
        app_commands.Choice(name="✅ Show Active Members", value="active"),
        app_commands.Choice(name="⚠️ Show Inactive Members", value="inactive"),
        app_commands.Choice(name="👤 Check Member Stats", value="check_member"),
        app_commands.Choice(name="🔄 Refresh Roles", value="refresh"),
        app_commands.Choice(name="📥 Backfill Data", value="backfill"),
        app_commands.Choice(name="🏖️ Grant Vacation", value="vacation"),
        app_commands.Choice(name="⚠️ Test Warning", value="test_warning"),
        app_commands.Choice(name="⚙️ Engagement Settings", value="settings"),
        app_commands.Choice(name="📝 Configure Thresholds", value="configure"),
    ])
    @app_commands.default_permissions(administrator=True)
    async def admin_command(self, interaction: discord.Interaction,
                           action: str,
                           member: Optional[discord.Member] = None,
                           limit: Optional[int] = 10):
        """Admin command hub - routes to appropriate modules"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            guild = interaction.guild
            engagement_cog = self.bot.get_cog('EngagementCog')
            
            if action == "analyze":
                embed = await self.admin_manager.analyze_activity(guild, limit)
                await interaction.followup.send(embed=embed)
                
            elif action == "active":
                embed = await self.admin_manager.get_active_members(guild, limit)
                await interaction.followup.send(embed=embed)
                
            elif action == "inactive":
                embed = await self.admin_manager.get_inactive_members(guild, limit)
                await interaction.followup.send(embed=embed)
                
            elif action == "check_member":
                if not member:
                    await interaction.followup.send("❌ Please specify a member")
                    return
                embed = await self.admin_manager.check_member_stats(guild, member)
                await interaction.followup.send(embed=embed)
                
            elif action == "refresh":
                if not engagement_cog:
                    await interaction.followup.send("❌ Engagement system not loaded")
                    return
                await engagement_cog.role_manager.update_member_roles(guild)
                await interaction.followup.send("✅ Roles refreshed")
                
            elif action == "backfill":
                # Start backfill with progress message
                embed = discord.Embed(
                    title="📥 Starting Backfill",
                    description="Launching backfill script...",
                    color=discord.Color.blue()
                )
                msg = await interaction.followup.send(embed=embed, wait=True)
                
                # Run backfill
                result = await self.admin_manager.run_backfill(guild, days=30)
                
                if result['success']:
                    embed.title = "✅ Backfill Complete"
                    embed.color = discord.Color.green()
                    
                    # Build description with results
                    desc_lines = []
                    stats = result['stats']
                    if stats['channels_scanned'] > 0:
                        desc_lines.append(f"📁 Scanned **{stats['channels_scanned']}** channels")
                    if stats['messages_processed'] > 0:
                        desc_lines.append(f"💬 Processed **{stats['messages_processed']:,}** messages")
                    if stats['members_found'] > 0:
                        desc_lines.append(f"👥 Found **{stats['members_found']}** active members")
                    if stats['records_updated'] > 0:
                        desc_lines.append(f"📊 Updated **{stats['records_updated']}** database records")
                    
                    # Add timing
                    elapsed = result['elapsed']
                    if elapsed < 60:
                        desc_lines.append(f"⏱️ Completed in **{elapsed:.1f}** seconds")
                    else:
                        minutes = int(elapsed // 60)
                        seconds = int(elapsed % 60)
                        desc_lines.append(f"⏱️ Completed in **{minutes}m {seconds}s**")
                    
                    embed.description = "\n".join(desc_lines) if desc_lines else "Backfill completed successfully"
                else:
                    embed.title = "❌ Backfill Failed"
                    embed.description = result['error']
                    embed.color = discord.Color.red()
                
                await msg.edit(embed=embed)
                
            elif action == "vacation":
                if not member:
                    await interaction.followup.send("❌ Please specify a member for vacation")
                    return
                if not engagement_cog:
                    await interaction.followup.send("❌ Engagement system not loaded")
                    return
                success, message = await engagement_cog.role_manager.grant_vacation_role(guild, member, days=30)
                await interaction.followup.send(message)
                
            elif action == "test_warning":
                if not member:
                    await interaction.followup.send("❌ Please specify a member to test warning")
                    return
                if not engagement_cog:
                    await interaction.followup.send("❌ Engagement system not loaded")
                    return
                success, message = await engagement_cog.warning_system.test_warning(guild, member)
                await interaction.followup.send(message)
                
            elif action == "settings":
                embed = await self.admin_manager.get_engagement_settings(guild)
                await interaction.followup.send(embed=embed)
                
            elif action == "configure":
                await interaction.followup.send(
                    "Use `/admin_config` to configure engagement thresholds:\n"
                    "• Set message requirement for Active role\n"
                    "• Set active days requirement\n"
                    "• Set lookback period"
                )
                
        except Exception as e:
            logger.error(f"Error in admin command: {e}")
            await interaction.followup.send(f"❌ Error: {e}")
    
    @app_commands.command(name="admin_config", description="Configure engagement thresholds for Active role")
    @app_commands.describe(
        messages="Number of messages required for Active role",
        active_days="Number of unique days with activity required",
        period="Number of days to look back (default: 30)"
    )
    @app_commands.default_permissions(administrator=True)
    async def admin_config_command(
        self,
        interaction: discord.Interaction,
        messages: Optional[int] = None,
        active_days: Optional[int] = None,
        period: Optional[int] = None
    ):
        """Configure engagement thresholds"""
        await interaction.response.defer(ephemeral=True)
        
        if messages is None and active_days is None and period is None:
            await interaction.followup.send(
                "❌ Please provide at least one parameter to configure:\n"
                "• `messages`: Number of messages required\n"
                "• `active_days`: Number of unique days with activity\n"
                "• `period`: Days to look back"
            )
            return
        
        try:
            embed = await self.admin_manager.configure_thresholds(
                interaction.guild,
                messages=messages,
                active_days=active_days,
                period=period
            )
            await interaction.followup.send(embed=embed)
        except ValueError as e:
            await interaction.followup.send(f"❌ {str(e)}")
        except Exception as e:
            logger.error(f"Error configuring thresholds: {e}")
            await interaction.followup.send(f"❌ Error: {e}")
    
    @app_commands.command(name="set_channels", description="Configure welcome and introduction channels")
    @app_commands.describe(
        channel_type="Type of channel to configure",
        channel="The text channel to use"
    )
    @app_commands.choices(channel_type=[
        app_commands.Choice(name="👋 Welcome Channel", value="welcome"),
        app_commands.Choice(name="💬 Introduction Channel", value="intro"),
        app_commands.Choice(name="📝 Engagement Log Channel", value="engagement_log"),
    ])
    @app_commands.default_permissions(administrator=True)
    async def set_channels(self, interaction: discord.Interaction,
                          channel_type: str,
                          channel: discord.TextChannel):
        """Configure engagement system channels"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            message = await self.admin_manager.set_channel(
                interaction.guild,
                channel_type,
                channel
            )
            await interaction.followup.send(message)
        except Exception as e:
            logger.error(f"Error setting channel: {e}")
            await interaction.followup.send(f"❌ Error: {str(e)}")
    
    @app_commands.command(name="purge", description="Delete recent messages from the current channel")
    @app_commands.describe(
        amount="How many messages to delete (1-100). Required — there is no default.",
        reason="Reason for purging messages"
    )
    @app_commands.default_permissions(manage_messages=True)
    async def purge_command(
        self,
        interaction: discord.Interaction,
        amount: app_commands.Range[int, 1, 100],
        reason: Optional[str] = None
    ):
        """Purge messages from the current channel.

        `amount` is REQUIRED and range-checked by Discord (1-100), so an empty or
        hasty submit can no longer silently default to 100 and wipe the channel.
        Anything above PURGE_CONFIRM_THRESHOLD asks for an explicit Delete/Cancel
        confirmation first — the brake that was missing.
        """
        if amount > PURGE_CONFIRM_THRESHOLD:
            view = ConfirmPurgeView(
                invoker_id=interaction.user.id,
                on_confirm=lambda i: self._do_purge(i, amount, reason),
            )
            await interaction.response.send_message(
                f"⚠️ Delete the last **{amount}** messages in this channel? "
                f"This cannot be undone.",
                view=view,
                ephemeral=True,
            )
            return

        # Small purge: no confirmation needed.
        await interaction.response.defer(ephemeral=True)
        await self._do_purge(interaction, amount, reason)

    async def _do_purge(self, interaction: discord.Interaction, amount: int, reason: Optional[str]):
        """Run the actual purge. The interaction must already be deferred (small
        path) or have had its message edited (confirm path), so results are sent
        via followup."""
        deleted_count, error = await purge_messages(
            channel=interaction.channel,
            limit=amount,
        )

        if error:
            await interaction.followup.send(f"❌ {error}", ephemeral=True)
            return

        await interaction.followup.send(
            f"✅ Deleted {deleted_count} message(s)", ephemeral=True
        )

        # Temporary public notification (self-deletes).
        reason_text = f"\nReason: {reason}" if reason else ""
        await send_temporary_message(
            channel=interaction.channel,
            content=f"🧹 Purged {deleted_count} messages{reason_text}",
            delete_after=3.0,
        )

        logger.info(
            f"{interaction.user} purged {deleted_count} messages in "
            f"#{interaction.channel.name} ({interaction.guild.name})"
            f"{f' - Reason: {reason}' if reason else ''}"
        )


async def setup(bot):
    await bot.add_cog(AdminCommands(bot))
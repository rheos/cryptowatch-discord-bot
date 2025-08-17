"""
Admin commands for member management
Handles engagement tracking and member administration
"""
import discord
from discord import app_commands
from discord.ext import commands
import logging
from typing import Optional
from .base import SlashCommandBase
from utils.moderation import purge_messages, send_temporary_message

logger = logging.getLogger('discord-bot.admin_commands')

class AdminCommands(SlashCommandBase):
    """Admin-related member management commands"""
    
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
        app_commands.Choice(name="Backfill Engagement Data", value="backfill"),
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
            elif action == "backfill":
                await self._handle_backfill(interaction)
                
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
    
    async def _handle_backfill(self, interaction: discord.Interaction):
        """Handle engagement data backfill with progress reporting"""
        import asyncio
        import os
        
        # No need to check if engagement is enabled - backfill should work regardless
        
        embed = discord.Embed(
            title="🔄 Starting Engagement Backfill",
            description="Initializing...",
            color=discord.Color.blue()
        )
        await interaction.followup.send(embed=embed)
        msg = await interaction.original_response()
        
        try:
            # Run the backfill script
            script_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                "scripts", "backfill_engagement.py"
            )
            
            process = await asyncio.create_subprocess_exec(
                "python3", script_path,
                "--guild", str(interaction.guild.id),
                "--days", "30",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=os.environ.copy()  # Pass environment variables to subprocess
            )
            
            # Read progress updates
            last_update = ""
            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                    
                text = line.decode().strip()
                # Update on channel progress lines
                if "Scanning channel" in text or "Guild scan complete" in text:
                    last_update = text.split("INFO - ")[-1] if "INFO - " in text else text
                    embed.description = last_update
                    await msg.edit(embed=embed)
            
            # Wait for completion
            await process.wait()
            
            if process.returncode == 0:
                embed.title = "✅ Backfill Complete"
                embed.description = "Successfully backfilled engagement data"
                embed.color = discord.Color.green()
            else:
                stderr_data = await process.stderr.read()
                error = stderr_data.decode() if stderr_data else "Unknown error"
                embed.title = "❌ Backfill Failed"
                embed.description = f"Error: {error[:200]}"
                embed.color = discord.Color.red()
            
            await msg.edit(embed=embed)
                
        except Exception as e:
            logger.error(f"Error during backfill: {e}")
            embed.title = "❌ Error"
            embed.description = str(e)
            embed.color = discord.Color.red()
            await msg.edit(embed=embed)
    
    @app_commands.command(name="purge", description="Delete multiple messages from the current channel")
    @app_commands.describe(
        amount="Number of messages to delete (1-100, default: 100)",
        reason="Reason for purging messages"
    )
    @app_commands.default_permissions(manage_messages=True)
    async def purge_command(
        self, 
        interaction: discord.Interaction, 
        amount: Optional[int] = 100,
        reason: Optional[str] = None
    ):
        """Purge messages from the current channel"""
        # Validate amount
        if amount < 1 or amount > 100:
            await interaction.response.send_message(
                "❌ Amount must be between 1 and 100 messages",
                ephemeral=True
            )
            return
        
        # Defer the response since purging might take a moment
        await interaction.response.defer(ephemeral=True)
        
        # Perform the purge
        deleted_count, error = await purge_messages(
            channel=interaction.channel,
            limit=amount
        )
        
        if error:
            # Send error message
            await interaction.followup.send(f"❌ {error}", ephemeral=True)
        else:
            # Send success message (ephemeral)
            await interaction.followup.send(
                f"✅ Successfully deleted {deleted_count} messages",
                ephemeral=True
            )
            
            # Also send a temporary public notification
            reason_text = f"\nReason: {reason}" if reason else ""
            await send_temporary_message(
                channel=interaction.channel,
                content=f"🧹 Purged {deleted_count} messages{reason_text}",
                delete_after=3.0
            )
            
            # Log the action
            logger.info(
                f"{interaction.user} purged {deleted_count} messages in "
                f"#{interaction.channel.name} ({interaction.guild.name})"
                f"{f' - Reason: {reason}' if reason else ''}"
            )

async def setup(bot):
    await bot.add_cog(AdminCommands(bot))
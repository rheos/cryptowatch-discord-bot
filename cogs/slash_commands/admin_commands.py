"""
Admin commands for server and member management
"""
import discord
from discord import app_commands
from discord.ext import commands
import logging
import os
import asyncio
import re
from typing import Optional
from .base import SlashCommandBase
from utils.moderation import purge_messages, send_temporary_message

logger = logging.getLogger('discord-bot.admin_commands')


class AdminCommands(SlashCommandBase):
    """Admin commands for server and member management"""
    
    @app_commands.command(name="admin", description="Server and member management commands")
    @app_commands.describe(
        action="Admin action to perform",
        member="Target member (for member-specific actions)",
        limit="Number of results to show"
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
        app_commands.Choice(name="💬 Set Intro Channel", value="set_intro"),
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
        
        # Get engagement cog for member management
        engagement_cog = self.bot.get_cog('EngagementCog')
        if not engagement_cog:
            await interaction.followup.send("❌ Engagement system not loaded")
            return
        
        try:
            guild = interaction.guild
            
            if action == "analyze":
                stats = await engagement_cog.activity_tracker.get_all_member_stats(guild.id)
                if not stats:
                    await interaction.followup.send("No activity data found")
                    return
                
                sorted_stats = sorted(stats, key=lambda x: x['total_messages'], reverse=True)[:limit]
                lines = []
                for i, stat in enumerate(sorted_stats, 1):
                    m = guild.get_member(stat['user_id'])
                    if m:
                        lines.append(f"{i}. **{m.display_name}** - {stat['total_messages']} msgs")
                
                total_active = sum(1 for s in stats if s['total_messages'] >= 10)
                embed = discord.Embed(
                    title="📊 Activity Analysis",
                    description="\n".join(lines) if lines else "No data",
                    color=discord.Color.blue()
                )
                embed.set_footer(text=f"{total_active}/{len(stats)} active (10+ msgs)")
                await interaction.followup.send(embed=embed)
                
            elif action == "active":
                stats = await engagement_cog.activity_tracker.get_active_members(guild.id)
                if not stats:
                    await interaction.followup.send("No active members found")
                    return
                
                lines = []
                for stat in stats[:limit]:
                    m = guild.get_member(stat['user_id'])
                    if m:
                        lines.append(f"• **{m.display_name}** - {stat['total_messages']} msgs")
                
                embed = discord.Embed(
                    title="✅ Active Members",
                    description="\n".join(lines) if lines else "None",
                    color=discord.Color.green()
                )
                embed.set_footer(text=f"Total: {len(stats)} active")
                await interaction.followup.send(embed=embed)
                
            elif action == "inactive":
                active_role = discord.utils.get(guild.roles, name="Active")
                if not active_role:
                    await interaction.followup.send("❌ Active role not found")
                    return
                
                inactive = []
                for m in active_role.members:
                    activity = await engagement_cog.activity_tracker.get_member_activity(guild.id, m.id)
                    if activity['messages'] < 10:
                        inactive.append((m, activity['messages']))
                
                if not inactive:
                    await interaction.followup.send("No inactive members with Active role")
                    return
                
                inactive.sort(key=lambda x: x[1])
                lines = [f"• **{m.display_name}** - {msgs} msgs" for m, msgs in inactive[:limit]]
                
                embed = discord.Embed(
                    title="⚠️ Inactive Members",
                    description="\n".join(lines),
                    color=discord.Color.orange()
                )
                embed.set_footer(text=f"Total: {len(inactive)} inactive")
                await interaction.followup.send(embed=embed)
                
            elif action == "check_member":
                if not member:
                    await interaction.followup.send("❌ Please specify a member")
                    return
                
                activity = await engagement_cog.activity_tracker.get_member_activity(guild.id, member.id)
                settings = await self.bot.db.get_engagement_settings(guild.id)
                threshold = settings.get('messages_threshold', 10) if settings else 10
                
                embed = discord.Embed(
                    title=f"📊 {member.display_name}",
                    color=discord.Color.blue()
                )
                embed.add_field(
                    name="30-Day Stats",
                    value=f"Messages: {activity['messages']}\nActive Days: {activity.get('active_days', 0)}",
                    inline=False
                )
                
                status = "✅ Active" if activity['messages'] >= threshold else f"❌ Needs {threshold - activity['messages']} more"
                embed.add_field(name="Status", value=status, inline=False)
                
                await interaction.followup.send(embed=embed)
                
            elif action == "refresh":
                await engagement_cog.role_manager.update_member_roles(guild)
                await interaction.followup.send("✅ Roles refreshed")
                
            elif action == "backfill":
                # Call the external backfill script
                script_path = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                    "scripts", "backfill_engagement.py"
                )
                
                embed = discord.Embed(
                    title="📥 Starting Backfill",
                    description="Launching backfill script...",
                    color=discord.Color.blue()
                )
                msg = await interaction.followup.send(embed=embed, wait=True)
                
                # Track start time
                start_time = asyncio.get_event_loop().time()
                
                process = await asyncio.create_subprocess_exec(
                    "python3", script_path,
                    "--guild", str(guild.id),
                    "--days", "30",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                stdout, stderr = await process.communicate()
                
                # Calculate elapsed time
                elapsed = asyncio.get_event_loop().time() - start_time
                
                if process.returncode == 0:
                    embed.title = "✅ Backfill Complete"
                    embed.color = discord.Color.green()
                    
                    # Parse output for statistics
                    output = stdout.decode() if stdout else ""
                    
                    # Debug: Print to console what we received
                    print(f"[BACKFILL DEBUG] stdout captured: {len(output)} chars")
                    if output:
                        print(f"[BACKFILL DEBUG] First 500 chars: {output[:500]}")
                        print(f"[BACKFILL DEBUG] Sample lines:")
                        for line in output.split('\n')[:5]:
                            print(f"  -> {line}")
                    
                    lines = output.split('\n')
                    
                    # Extract key metrics from output
                    channels_scanned = 0
                    messages_processed = 0
                    members_found = 0
                    records_updated = 0
                    
                    for line in lines:
                        # Look for "Found X accessible text channels" 
                        if "Found" in line and "accessible text channels" in line:
                            try:
                                # Line format: "2025-08-18 16:10:31,534 - INFO -   Found 8 accessible text channels"
                                import re
                                match = re.search(r'Found (\d+) accessible', line)
                                if match:
                                    channels_scanned = int(match.group(1))
                            except:
                                pass
                        # Look for "Guild scan complete: X members with activity"
                        elif "Guild scan complete:" in line:
                            try:
                                # Line format: "2025-08-18 16:10:42,322 - INFO -   Guild scan complete: 4 members with activity"
                                match = re.search(r'Guild scan complete: (\d+) members', line)
                                if match:
                                    members_found = int(match.group(1))
                            except:
                                pass
                        # Look for "Total messages to store: X"
                        elif "Total messages to store:" in line:
                            try:
                                # Line format: "2025-08-18 16:10:42,324 - INFO - Total messages to store: 38"
                                match = re.search(r'Total messages to store: (\d+)', line)
                                if match:
                                    messages_processed = int(match.group(1))
                            except:
                                pass
                        # Look for "Successfully inserted/updated X activity records"
                        elif "Successfully inserted/updated" in line:
                            try:
                                # Line format: "2025-08-18 16:10:42,343 - INFO - ✓ Successfully inserted/updated 10 activity records"
                                match = re.search(r'inserted/updated (\d+) activity', line)
                                if match:
                                    records_updated = int(match.group(1))
                            except:
                                pass
                    
                    # Build description with results
                    desc_lines = []
                    if channels_scanned > 0:
                        desc_lines.append(f"📁 Scanned **{channels_scanned}** channels")
                    if messages_processed > 0:
                        desc_lines.append(f"💬 Processed **{messages_processed:,}** messages")
                    if members_found > 0:
                        desc_lines.append(f"👥 Found **{members_found}** active members")
                    if records_updated > 0:
                        desc_lines.append(f"📊 Updated **{records_updated}** database records")
                    
                    # Add timing
                    if elapsed < 60:
                        desc_lines.append(f"⏱️ Completed in **{elapsed:.1f}** seconds")
                    else:
                        minutes = int(elapsed // 60)
                        seconds = int(elapsed % 60)
                        desc_lines.append(f"⏱️ Completed in **{minutes}m {seconds}s**")
                    
                    embed.description = "\n".join(desc_lines) if desc_lines else "Backfill completed successfully"
                    
                else:
                    embed.title = "❌ Backfill Failed"
                    embed.description = stderr.decode()[:200] if stderr else "Unknown error"
                    embed.color = discord.Color.red()
                
                await msg.edit(embed=embed)
                
            elif action == "vacation":
                if not member:
                    await interaction.followup.send("❌ Please specify a member for vacation")
                    return
                    
                success, message = await engagement_cog.role_manager.grant_vacation_role(guild, member, days=30)
                await interaction.followup.send(message)
                
            elif action == "test_warning":
                if not member:
                    await interaction.followup.send("❌ Please specify a member to test warning")
                    return
                    
                success, message = await engagement_cog.warning_system.test_warning(guild, member)
                await interaction.followup.send(message)
                
            elif action == "set_intro":
                await self.bot.db.set_setting(guild.id, 'introductions_channel_id', str(interaction.channel.id))
                await interaction.followup.send(
                    f"✅ Set {interaction.channel.mention} as introductions channel\n"
                    f"New members must post 50+ chars here for Member role"
                )
                
            elif action == "settings":
                settings = await self.bot.db.get_engagement_settings(guild.id)
                
                embed = discord.Embed(title="⚙️ Engagement Settings", color=discord.Color.blue())
                
                if settings:
                    embed.add_field(name="Enabled", value="✅" if settings.get('enabled') else "❌", inline=True)
                    embed.add_field(name="Messages Required", value=f"{settings.get('messages_threshold', 10)}", inline=True)
                    embed.add_field(name="Lookback Period", value=f"{settings.get('days_threshold', 30)} days", inline=True)
                    
                    # Show active days requirement if set
                    active_days = settings.get('active_days_threshold')
                    if active_days:
                        embed.add_field(name="Active Days Required", value=f"{active_days} days", inline=True)
                    else:
                        embed.add_field(name="Active Days Required", value="Not set", inline=True)
                else:
                    embed.description = "Using defaults"
                
                intro_id = await self.bot.db.get_setting(guild.id, 'introductions_channel_id')
                if intro_id:
                    channel = guild.get_channel(int(intro_id))
                    if channel:
                        embed.add_field(name="Intro Channel", value=channel.mention, inline=False)
                
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
        
        guild = interaction.guild
        updates = []
        
        try:
            # Update message threshold
            if messages is not None:
                if messages < 1 or messages > 1000:
                    await interaction.followup.send("❌ Messages must be between 1 and 1000")
                    return
                await self.bot.db.set_setting(guild.id, 'messages_threshold', str(messages))
                updates.append(f"✅ Message threshold set to **{messages}**")
            
            # Update active days threshold
            if active_days is not None:
                if active_days < 1 or active_days > 365:
                    await interaction.followup.send("❌ Active days must be between 1 and 365")
                    return
                await self.bot.db.set_setting(guild.id, 'active_days_threshold', str(active_days))
                updates.append(f"✅ Active days requirement set to **{active_days}**")
            
            # Update period (days to look back)
            if period is not None:
                if period < 1 or period > 365:
                    await interaction.followup.send("❌ Period must be between 1 and 365 days")
                    return
                await self.bot.db.set_setting(guild.id, 'days_threshold', str(period))
                updates.append(f"✅ Lookback period set to **{period} days**")
            
            # Get current settings to show
            settings = await self.bot.db.get_engagement_settings(guild.id)
            
            embed = discord.Embed(
                title="⚙️ Engagement Configuration Updated",
                description="\n".join(updates),
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
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error configuring thresholds: {e}")
            await interaction.followup.send(f"❌ Error: {e}")
    
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
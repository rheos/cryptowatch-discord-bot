"""
Auto Role Cog - Automatically assigns roles to new members
"""
import discord
from discord.ext import commands
import logging

logger = logging.getLogger('discord-bot.auto-role')

class AutoRoleCog(commands.Cog):
    def __init__(self, bot, config):
        self.bot = bot
        self.config = config
        self.auto_role_name = "Members"  # The role to auto-assign
        
    @commands.Cog.listener()
    async def on_member_join(self, member):
        """Automatically assign role when a new member joins"""
        try:
            # Find the Members role
            role = discord.utils.get(member.guild.roles, name=self.auto_role_name)
            
            if role:
                # Add the role to the new member
                await member.add_roles(role)
                logger.info(f"Added {self.auto_role_name} role to new member: {member.name} ({member.id})")
            else:
                logger.error(f"Role '{self.auto_role_name}' not found in guild {member.guild.name}")
                
        except discord.errors.Forbidden:
            logger.error(f"No permission to add roles in guild {member.guild.name}")
        except Exception as e:
            logger.error(f"Error adding role to {member.name}: {e}")
    
    @commands.command(name='autorole')
    @commands.has_permissions(administrator=True)
    async def check_auto_role(self, ctx):
        """Check auto-role status (admin only)"""
        role = discord.utils.get(ctx.guild.roles, name=self.auto_role_name)
        
        if role:
            embed = discord.Embed(
                title="✅ Auto-Role Status",
                description=f"Auto-assigning **{self.auto_role_name}** role to new members",
                color=discord.Color.green()
            )
            embed.add_field(
                name="Role Info",
                value=f"Name: {role.name}\nMembers: {len(role.members)}\nColor: {role.color}",
                inline=False
            )
        else:
            embed = discord.Embed(
                title="❌ Auto-Role Status",
                description=f"Role **{self.auto_role_name}** not found!",
                color=discord.Color.red()
            )
            
        await ctx.send(embed=embed)
    
    @commands.command(name='addmissing')
    @commands.has_permissions(administrator=True)
    async def add_role_to_existing(self, ctx):
        """Add Members role to all users who don't have it (admin only)"""
        role = discord.utils.get(ctx.guild.roles, name=self.auto_role_name)
        
        if not role:
            await ctx.send(f"❌ Role '{self.auto_role_name}' not found!")
            return
        
        # Count members without the role
        members_without_role = [m for m in ctx.guild.members if not m.bot and role not in m.roles]
        
        if not members_without_role:
            await ctx.send("✅ All members already have the role!")
            return
        
        # Add role to members
        msg = await ctx.send(f"Adding {self.auto_role_name} role to {len(members_without_role)} members...")
        
        added = 0
        failed = 0
        
        for member in members_without_role:
            try:
                await member.add_roles(role)
                added += 1
            except:
                failed += 1
        
        await msg.edit(content=f"✅ Done! Added role to {added} members. Failed: {failed}")

async def setup(bot):
    pass
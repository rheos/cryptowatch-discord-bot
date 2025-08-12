"""
User-related slash commands: /mystats, /help, /about
"""
import discord
from discord import app_commands
from discord.ext import commands
import logging
from .base import SlashCommandBase

logger = logging.getLogger('discord-bot.user_commands')

class UserCommands(SlashCommandBase):
    """User-related slash commands"""
    
    @app_commands.command(name="mystats", description="Check your engagement statistics")
    async def mystats(self, interaction: discord.Interaction):
        """Get user's stats from database"""
        await interaction.response.defer()
        
        try:
            stats = await self.bot.db.get_member_stats(
                interaction.guild_id, 
                interaction.user.id,
                days=30
            )
            
            embed = discord.Embed(
                title="📊 Your Engagement Stats",
                color=discord.Color.blue()
            )
            
            if stats and stats['total_messages']:
                embed.add_field(
                    name="30-Day Activity",
                    value=f"Messages: {stats['total_messages']}\nActive Days: {stats['active_days']}",
                    inline=False
                )
                
                # Check if qualifies for Active
                active_threshold = 10  # From config
                if stats['total_messages'] >= active_threshold:
                    status = "✅ Qualifies for Active Member"
                else:
                    needed = active_threshold - stats['total_messages']
                    status = f"📈 {needed} more messages needed for Active"
                
                embed.add_field(name="Status", value=status, inline=False)
                
                # Show current roles
                member_roles = [r.name for r in interaction.user.roles if r.name != "@everyone"]
                if member_roles:
                    embed.add_field(
                        name="Current Roles",
                        value=", ".join(member_roles),
                        inline=False
                    )
            else:
                embed.description = "No activity recorded yet. Start chatting to build your stats!"
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error fetching user stats: {e}")
            await interaction.followup.send("❌ Error fetching your stats. Please try again later.")
    
    @app_commands.command(name="about", description="Learn about CryptoWatch Bot")
    async def about_command(self, interaction: discord.Interaction):
        """Show information about the bot"""
        embed = discord.Embed(
            title="🤖 About CryptoWatch Bot (ExampleBot)",
            description="Your AI-powered crypto companion for market analysis and insights",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="Features",
            value=(
                "• Real-time BloFin funding rates\n"
                "• Price volatility tracking\n"
                "• Market trend analysis\n"
                "• AI-powered chat assistant\n"
                "• Engagement tracking"
            ),
            inline=False
        )
        
        embed.add_field(
            name="Data Sources",
            value=(
                "• **BloFin** - Funding rates\n"
                "• **Binance** - Price data\n"
                "• **CryptoWatchTools** - Analytics"
            ),
            inline=False
        )
        
        embed.add_field(
            name="Website",
            value="[example.com](https://example.com)",
            inline=True
        )
        
        embed.add_field(
            name="Support",
            value="Use `/help` for commands",
            inline=True
        )
        
        embed.set_footer(text="Made with ❤️ by CryptoWatchTools")
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="help", description="Show all available commands")
    async def help_command(self, interaction: discord.Interaction):
        """Show help information"""
        embed = discord.Embed(
            title="📚 CryptoWatch Bot Commands",
            description="Here are all available slash commands:",
            color=discord.Color.blue()
        )
        
        # Crypto Commands
        embed.add_field(
            name="💰 Crypto Commands",
            value=(
                "`/price <symbol>` - Get current price\n"
                "`/funding <mode>` - BloFin funding rates\n"
                "`/volatility <mode>` - Price volatility analysis"
            ),
            inline=False
        )
        
        # Funding Modes
        embed.add_field(
            name="📊 Funding Modes",
            value=(
                "• **Most Negative** - Coins with lowest rates\n"
                "• **Scanner** - Overview of all rates\n"
                "• **Improving** - Rates becoming less negative\n"
                "• **Worsening** - Rates becoming more negative\n"
                "• **Turned Positive** - Recently flipped positive\n"
                "• **Check Symbol** - Check specific coin"
            ),
            inline=False
        )
        
        # Volatility Modes
        embed.add_field(
            name="📈 Volatility Modes",
            value=(
                "• **Scanner** - Top movers overview\n"
                "• **Most Volatile** - Highest volatility coins\n"
                "• **Check Symbol** - Check specific coin"
            ),
            inline=False
        )
        
        # User Commands
        embed.add_field(
            name="👤 User Commands",
            value=(
                "`/mystats` - Your engagement statistics\n"
                "`/about` - About this bot\n"
                "`/help` - This help message"
            ),
            inline=False
        )
        
        # Admin Commands (only show if user is admin)
        if interaction.user.guild_permissions.administrator:
            embed.add_field(
                name="⚙️ Admin Commands",
                value=(
                    "`/setup` - Show config or manage engagement\n"
                    "`/setup_timezone` - Configure timezone voice channel\n"
                    "`/setup_alerts` - Configure alert text channels\n"
                    "`/admin` - Engagement management tools"
                ),
                inline=False
            )
            
            # Add admin details
            embed.add_field(
                name="👤 Admin Options",
                value=(
                    "• **Analyze All Members** - Activity overview\n"
                    "• **Show Active/Inactive** - Filter by activity\n"
                    "• **Grant/Remove Role** - Manage member roles\n"
                    "• **Check Member Stats** - Individual stats\n"
                    "• **Refresh All Stats** - Update database"
                ),
                inline=False
            )
        
        # Chat Feature
        embed.add_field(
            name="💬 AI Chat",
            value="Just mention me or DM me to chat! I can help with crypto analysis and questions.",
            inline=False
        )
        
        embed.set_footer(text="Tip: Most commands have additional options you can explore!")
        
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(UserCommands(bot))
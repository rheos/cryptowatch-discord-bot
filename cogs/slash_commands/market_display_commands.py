"""
Market Display Commands - Configure voice channels to show market data
Supports any coin price and market info fields
"""
import discord
from discord import app_commands
from discord.ext import commands
import logging
from typing import Optional, List
from .base import SlashCommandBase

logger = logging.getLogger('discord-bot.market_display_commands')

# Common market info fields for autocomplete
MARKET_INFO_FIELDS = [
    ("Bitcoin Dominance", "btc_dominance"),
    ("Ethereum Dominance", "eth_dominance"),
    ("Fear & Greed Index", "fear_greed"),
    ("Total Market Cap", "total_market_cap"),
    ("Total 24h Volume", "total_volume_24h"),
    ("Alt Season Index", "altseason_index"),
    ("Stablecoin Market Cap", "stablecoin_mcap"),
    ("DeFi Market Cap", "defi_mcap"),
]

# Popular coins for autocomplete
POPULAR_COINS = [
    "BTC", "ETH", "BNB", "SOL", "XRP", "DOGE", "ADA", "AVAX", "DOT", "MATIC",
    "LINK", "UNI", "ATOM", "FTM", "NEAR", "ALGO", "VET", "MANA", "SAND", "AXS",
    "SHIB", "PEPE", "FLOKI", "BONK", "WIF", "ARB", "OP", "INJ", "TIA", "SEI"
]

class MarketDisplayCommands(SlashCommandBase):
    """Market display configuration commands"""
    
    def __init__(self, bot):
        super().__init__(bot)
        self.bot = bot
    
    @app_commands.command(
        name="market_display",
        description="Configure voice channels to display market data"
    )
    @app_commands.describe(
        action="Action to perform",
        channel="Voice channel to configure",
        data_type="Type of data to display",
        symbol="Coin symbol (for prices) or field name (for market info)",
        custom_label="Optional custom label for the channel"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="➕ Add Channel", value="add"),
        app_commands.Choice(name="➖ Remove Channel", value="remove"),
        app_commands.Choice(name="📋 List Channels", value="list"),
        app_commands.Choice(name="⚙️ Set Update Interval", value="interval"),
    ])
    @app_commands.choices(data_type=[
        app_commands.Choice(name="💰 Coin Price", value="coin_price"),
        app_commands.Choice(name="📊 Market Info", value="market_info"),
    ])
    @app_commands.default_permissions(administrator=True)
    async def market_display_command(
        self,
        interaction: discord.Interaction,
        action: str,
        channel: Optional[discord.VoiceChannel] = None,
        data_type: Optional[str] = None,
        symbol: Optional[str] = None,
        custom_label: Optional[str] = None
    ):
        """Main market display configuration command"""
        await interaction.response.defer(ephemeral=True)
        
        if action == "add":
            if not all([channel, data_type, symbol]):
                await interaction.followup.send(
                    "❌ For adding a channel, you must provide: channel, data_type, and symbol",
                    ephemeral=True
                )
                return
            await self._handle_add_channel(interaction, channel, data_type, symbol, custom_label)
        
        elif action == "remove":
            if not channel:
                await interaction.followup.send(
                    "❌ Please specify which channel to remove",
                    ephemeral=True
                )
                return
            await self._handle_remove_channel(interaction, channel)
        
        elif action == "list":
            await self._handle_list_channels(interaction)
        
        elif action == "interval":
            # This would need a modal or separate command for the interval value
            await self._handle_set_interval(interaction)
    
    @market_display_command.autocomplete('symbol')
    async def symbol_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str
    ) -> List[app_commands.Choice[str]]:
        """Provide autocomplete for symbols based on data_type"""
        # Try to get the data_type from the interaction
        data_type = None
        for option in interaction.data.get('options', []):
            if option['name'] == 'data_type':
                data_type = option['value']
                break
        
        choices = []
        
        if data_type == 'market_info':
            # Show market info fields
            for name, value in MARKET_INFO_FIELDS:
                if not current or current.lower() in name.lower() or current.lower() in value.lower():
                    choices.append(app_commands.Choice(name=name, value=value))
        else:
            # Show coin symbols
            for coin in POPULAR_COINS:
                if not current or current.upper() in coin:
                    choices.append(app_commands.Choice(name=coin, value=coin))
            
            # If user typed something not in popular coins, add it as option
            if current and current.upper() not in POPULAR_COINS:
                choices.insert(0, app_commands.Choice(
                    name=f"{current.upper()} (Custom)",
                    value=current.upper()
                ))
        
        return choices[:25]  # Discord limit
    
    async def _handle_add_channel(
        self,
        interaction: discord.Interaction,
        channel: discord.VoiceChannel,
        data_type: str,
        symbol: str,
        custom_label: Optional[str]
    ):
        """Add a market display channel"""
        guild_id = interaction.guild_id
        
        try:
            async with self.bot.db.pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    # Check if channel is already configured
                    await cursor.execute("""
                        SELECT id FROM market_display_channels 
                        WHERE channel_id = %s
                    """, (channel.id,))
                    
                    if await cursor.fetchone():
                        await interaction.followup.send(
                            f"❌ {channel.mention} is already configured for market display",
                            ephemeral=True
                        )
                        return
                    
                    # Add the channel
                    # Use uppercase for coin symbols, lowercase for market info fields
                    if data_type == 'coin_price':
                        symbol_to_store = symbol.upper()
                    else:
                        symbol_to_store = symbol.lower()
                    
                    await cursor.execute("""
                        INSERT INTO market_display_channels 
                        (guild_id, channel_id, display_type, symbol, custom_label)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (guild_id, channel.id, data_type, symbol_to_store, custom_label))
                    
                    await conn.commit()
            
            # Format message
            if data_type == 'coin_price':
                description = f"**Channel**: {channel.mention}\n**Type**: Coin Price\n**Symbol**: {symbol.upper()}"
            else:
                field_name = next((name for name, val in MARKET_INFO_FIELDS if val == symbol), symbol)
                description = f"**Channel**: {channel.mention}\n**Type**: Market Info\n**Field**: {field_name}"
            
            if custom_label:
                description += f"\n**Custom Label**: {custom_label}"
            
            embed = discord.Embed(
                title="✅ Market Display Channel Added",
                description=description,
                color=discord.Color.green()
            )
            
            # Check if feature is enabled
            enabled = await self.bot.db.get_setting(guild_id, 'market_display_enabled')
            if not enabled:
                embed.add_field(
                    name="⚠️ Feature Disabled",
                    value="Use `/setup` → Toggle Market Display to enable updates",
                    inline=False
                )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error adding market display channel: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ Failed to add market display channel: {str(e)}",
                ephemeral=True
            )
    
    async def _handle_remove_channel(
        self,
        interaction: discord.Interaction,
        channel: discord.VoiceChannel
    ):
        """Remove a market display channel"""
        try:
            async with self.bot.db.pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    # Check if channel exists
                    await cursor.execute("""
                        SELECT display_type, symbol FROM market_display_channels 
                        WHERE channel_id = %s
                    """, (channel.id,))
                    
                    result = await cursor.fetchone()
                    if not result:
                        await interaction.followup.send(
                            f"❌ {channel.mention} is not configured for market display",
                            ephemeral=True
                        )
                        return
                    
                    # Remove the channel
                    await cursor.execute("""
                        DELETE FROM market_display_channels 
                        WHERE channel_id = %s
                    """, (channel.id,))
                    
                    await conn.commit()
            
            embed = discord.Embed(
                title="✅ Market Display Channel Removed",
                description=f"Removed {channel.mention} from market display",
                color=discord.Color.green()
            )
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error removing market display channel: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ Failed to remove market display channel: {str(e)}",
                ephemeral=True
            )
    
    async def _handle_list_channels(self, interaction: discord.Interaction):
        """List all configured market display channels"""
        guild_id = interaction.guild_id
        
        try:
            async with self.bot.db.pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        SELECT channel_id, display_type, symbol, custom_label, enabled
                        FROM market_display_channels
                        WHERE guild_id = %s
                        ORDER BY display_type, symbol
                    """, (guild_id,))
                    
                    channels = await cursor.fetchall()
            
            if not channels:
                embed = discord.Embed(
                    title="📊 Market Display Channels",
                    description="No channels configured yet.\nUse `/market_display add` to add channels.",
                    color=discord.Color.blue()
                )
            else:
                embed = discord.Embed(
                    title="📊 Market Display Channels",
                    description=f"**{len(channels)} channel(s) configured**",
                    color=discord.Color.blue()
                )
                
                coin_channels = []
                info_channels = []
                
                for channel_id, display_type, symbol, custom_label, enabled in channels:
                    channel = interaction.guild.get_channel(channel_id)
                    if not channel:
                        continue
                    
                    status = "✅" if enabled else "❌"
                    label = f" ({custom_label})" if custom_label else ""
                    
                    if display_type == 'coin_price':
                        coin_channels.append(f"{status} {channel.mention}: **{symbol}**{label}")
                    else:
                        field_name = next((name for name, val in MARKET_INFO_FIELDS if val == symbol), symbol)
                        info_channels.append(f"{status} {channel.mention}: **{field_name}**{label}")
                
                if coin_channels:
                    embed.add_field(
                        name="💰 Coin Prices",
                        value="\n".join(coin_channels),
                        inline=False
                    )
                
                if info_channels:
                    embed.add_field(
                        name="📈 Market Info",
                        value="\n".join(info_channels),
                        inline=False
                    )
            
            # Show feature status
            enabled = await self.bot.db.get_setting(guild_id, 'market_display_enabled')
            interval = await self.bot.db.get_setting(guild_id, 'market_display_interval') or 5
            
            status_text = f"**Status**: {'✅ Enabled' if enabled else '❌ Disabled'}\n"
            status_text += f"**Update Interval**: {interval} minutes"
            
            embed.add_field(name="⚙️ Settings", value=status_text, inline=False)
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error listing market display channels: {e}", exc_info=True)
            await interaction.followup.send(
                f"❌ Failed to list channels: {str(e)}",
                ephemeral=True
            )
    
    async def _handle_set_interval(self, interaction: discord.Interaction):
        """Set update interval (would need a modal for input)"""
        # For now, just show current interval
        guild_id = interaction.guild_id
        current = await self.bot.db.get_setting(guild_id, 'market_display_interval') or 5
        
        embed = discord.Embed(
            title="⏱️ Update Interval",
            description=f"Current interval: **{current} minutes**\n\nTo change the interval, please use the bot configuration panel.",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="ℹ️ Note",
            value="Minimum interval is 5 minutes to avoid rate limiting",
            inline=False
        )
        
        await interaction.followup.send(embed=embed)

async def setup(bot):
    # This allows the cog to be loaded dynamically
    pass
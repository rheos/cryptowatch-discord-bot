"""
Formatting utilities for Discord embeds and messages
"""
from typing import List, Dict, Any
import discord

def format_funding_list(rates: List[Dict[str, Any]], limit: int = 10) -> List[str]:
    """Format funding rates into a list of strings"""
    lines = []
    for i, item in enumerate(rates[:limit], 1):
        symbol = item.get('symbol', 'Unknown').replace('-USDT', '')
        rate = item.get('rate', 0) * 100  # Convert to percentage
        
        # Format with backticks for number alignment
        lines.append(f"`{i:02d}` **{symbol}**  {rate:.3f}%")
    
    return lines

def format_volatility_list(movers: List[Dict[str, Any]], limit: int = 10) -> List[str]:
    """Format volatility movers into a list of strings"""
    lines = []
    for i, item in enumerate(movers[:limit], 1):
        symbol = item['symbol']
        change = item['priceChangePercent']
        volatility = item.get('volatility', 0)
        
        emoji = "📈" if change > 0 else "📉"
        
        # Format with aligned columns
        lines.append(
            f"`{i:02d}` **{symbol}** {emoji} "
            f"`{change:+.1f}%` vol: `{volatility:.1f}%`"
        )
    
    return lines

def format_price_info(symbol: str, price_data: Dict[str, Any]) -> discord.Embed:
    """Format price information into an embed"""
    price = price_data.get('price', 0)
    change_24h = price_data.get('priceChangePercent', 0)
    volume_24h = price_data.get('volume', 0)
    
    # Determine color based on price change
    if change_24h > 0:
        color = discord.Color.green()
        emoji = "📈"
    elif change_24h < 0:
        color = discord.Color.red()
        emoji = "📉"
    else:
        color = discord.Color.grey()
        emoji = "➡️"
    
    embed = discord.Embed(
        title=f"{emoji} {symbol} Price",
        color=color
    )
    
    # Format price with appropriate decimals
    if price >= 1000:
        price_str = f"${price:,.2f}"
    elif price >= 1:
        price_str = f"${price:.2f}"
    else:
        price_str = f"${price:.8f}".rstrip('0').rstrip('.')
    
    embed.add_field(name="Price", value=price_str, inline=True)
    embed.add_field(name="24h Change", value=f"{change_24h:+.2f}%", inline=True)
    
    if volume_24h:
        embed.add_field(
            name="24h Volume", 
            value=f"${volume_24h:,.0f}", 
            inline=True
        )
    
    return embed

def truncate_list(items: List[str], max_length: int = 1900) -> List[str]:
    """Truncate a list of strings to fit within Discord's character limit"""
    result = []
    current_length = 0
    
    for item in items:
        item_length = len(item) + 1  # +1 for newline
        if current_length + item_length > max_length:
            result.append("... and more")
            break
        result.append(item)
        current_length += item_length
    
    return result
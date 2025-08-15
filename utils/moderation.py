"""
Moderation utility functions
"""
import discord
import asyncio
import logging
from typing import Optional, List

logger = logging.getLogger('discord-bot.moderation')

async def purge_messages(
    channel: discord.TextChannel,
    limit: int = 100,
    max_age_days: int = 14
) -> tuple[int, Optional[str]]:
    """
    Purge messages from a channel
    
    Args:
        channel: The channel to purge messages from
        limit: Maximum number of messages to delete (Discord max: 100)
        max_age_days: Don't delete messages older than this (Discord max: 14)
    
    Returns:
        Tuple of (messages_deleted, error_message)
    """
    try:
        # Discord limits bulk delete to 100 messages and 14 days old
        limit = min(limit, 100)
        
        # Perform the purge
        deleted_messages = await channel.purge(limit=limit)
        deleted_count = len(deleted_messages)
        
        logger.info(f"Purged {deleted_count} messages from {channel.name} in {channel.guild.name}")
        return deleted_count, None
        
    except discord.Forbidden:
        error = "Missing permissions to delete messages"
        logger.warning(f"Purge failed in {channel.name}: {error}")
        return 0, error
        
    except discord.HTTPException as e:
        error = f"Discord API error: {str(e)}"
        logger.error(f"Purge failed in {channel.name}: {error}")
        return 0, error
        
    except Exception as e:
        error = f"Unexpected error: {str(e)}"
        logger.error(f"Purge failed in {channel.name}: {error}", exc_info=True)
        return 0, error

async def send_temporary_message(
    channel: discord.TextChannel,
    content: str = None,
    embed: discord.Embed = None,
    delete_after: float = 5.0
) -> Optional[discord.Message]:
    """
    Send a message that auto-deletes after a specified time
    
    Args:
        channel: Channel to send the message to
        content: Text content of the message
        embed: Embed to send
        delete_after: Seconds to wait before deleting
    
    Returns:
        The message object if successful, None otherwise
    """
    try:
        message = await channel.send(content=content, embed=embed)
        
        # Schedule deletion
        async def delete_message():
            await asyncio.sleep(delete_after)
            try:
                await message.delete()
            except discord.NotFound:
                pass  # Message already deleted
            except Exception as e:
                logger.debug(f"Could not delete temporary message: {e}")
        
        # Start deletion task without awaiting
        asyncio.create_task(delete_message())
        
        return message
        
    except Exception as e:
        logger.error(f"Failed to send temporary message: {e}")
        return None
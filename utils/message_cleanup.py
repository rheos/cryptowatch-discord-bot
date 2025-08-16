"""
Message cleanup utilities for auto-deleting old bot messages
"""
import discord
from datetime import datetime, timedelta, timezone
import logging
from typing import Optional, List

logger = logging.getLogger('discord-bot.message_cleanup')

async def cleanup_old_messages(
    channel: discord.TextChannel,
    max_age_hours: float = 4,
    bot_id: Optional[int] = None,
    limit: int = 100
) -> int:
    """
    Delete old messages from a channel
    
    Args:
        channel: The channel to clean up
        max_age_hours: Delete messages older than this many hours
        bot_id: Only delete messages from this bot ID (if None, deletes all bot messages)
        limit: Maximum number of messages to check (Discord API limit is 100)
    
    Returns:
        Number of messages deleted
    """
    if not channel:
        return 0
    
    try:
        deleted_count = 0
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
        
        # Fetch recent messages
        messages = []
        async for message in channel.history(limit=limit):
            # Only consider bot messages
            if not message.author.bot:
                continue
            
            # If specific bot ID provided, only delete from that bot
            if bot_id and message.author.id != bot_id:
                continue
            
            # Check if message is old enough to delete
            if message.created_at < cutoff_time:
                messages.append(message)
        
        # Track oldest and newest messages for logging
        oldest_msg_time = None
        newest_msg_time = None
        
        if messages:
            oldest_msg_time = min(msg.created_at for msg in messages)
            newest_msg_time = max(msg.created_at for msg in messages)
        
        # Bulk delete if possible (messages < 14 days old)
        bulk_delete = []
        individual_delete = []
        
        two_weeks_ago = datetime.now(timezone.utc) - timedelta(days=14)
        
        for msg in messages:
            if msg.created_at > two_weeks_ago and not msg.pinned:
                bulk_delete.append(msg)
            elif not msg.pinned:
                individual_delete.append(msg)
        
        # Perform bulk delete
        if bulk_delete:
            # Discord allows bulk delete of 2-100 messages at once
            for i in range(0, len(bulk_delete), 100):
                batch = bulk_delete[i:i+100]
                if len(batch) >= 2:
                    await channel.delete_messages(batch)
                    deleted_count += len(batch)
                else:
                    # Single message, delete individually
                    await batch[0].delete()
                    deleted_count += 1
        
        # Delete older messages individually
        for msg in individual_delete:
            try:
                await msg.delete()
                deleted_count += 1
            except discord.NotFound:
                pass  # Message already deleted
            except Exception as e:
                logger.warning(f"Could not delete message {msg.id}: {e}")
        
        if deleted_count > 0:
            if oldest_msg_time and newest_msg_time:
                time_range = f" (from {oldest_msg_time.strftime('%Y-%m-%d %H:%M')} to {newest_msg_time.strftime('%Y-%m-%d %H:%M')} UTC)"
            else:
                time_range = ""
            logger.info(f"Cleaned up {deleted_count} old messages from #{channel.name}{time_range}")
        elif messages:
            # Had messages to delete but couldn't
            logger.warning(f"Found {len(messages)} old messages in #{channel.name} but couldn't delete them")
        
        return deleted_count
        
    except discord.Forbidden:
        logger.error(f"No permission to delete messages in #{channel.name}")
        return 0
    except Exception as e:
        logger.error(f"Error cleaning up messages in #{channel.name}: {e}")
        return 0

async def cleanup_before_send(
    channel: discord.TextChannel,
    max_age_hours: float = 4,
    bot_id: Optional[int] = None
) -> None:
    """
    Clean up old messages before sending a new one
    Useful to call before sending alerts to keep channels clean
    
    Args:
        channel: The channel to clean up
        max_age_hours: Delete messages older than this many hours
        bot_id: Only delete messages from this bot ID
    """
    await cleanup_old_messages(channel, max_age_hours, bot_id)

async def find_last_bot_message(
    channel: discord.TextChannel,
    bot_id: int,
    content_check: Optional[str] = None,
    embed_check: Optional[str] = None,
    max_age_hours: Optional[float] = 24
) -> Optional[discord.Message]:
    """
    Find the last message from the bot in a channel
    
    Args:
        channel: The channel to search
        bot_id: The bot's user ID
        content_check: Optional string that should be in the message content
        embed_check: Optional string that should be in embed title/description
        max_age_hours: Don't look for messages older than this (None = no limit)
    
    Returns:
        The last matching message or None
    """
    try:
        if max_age_hours is not None:
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
            logger.debug(f"Searching for bot message in #{channel.name}, embed_check='{embed_check}', max_age={max_age_hours}h")
        else:
            cutoff_time = None
            logger.debug(f"Searching for bot message in #{channel.name}, embed_check='{embed_check}', no age limit")
        
        message_count = 0
        bot_messages = 0
        async for message in channel.history(limit=50):
            message_count += 1
            # Check if it's from our bot
            if message.author.id != bot_id:
                continue
            
            bot_messages += 1
            # Don't return messages that are too old (if age limit is set)
            if cutoff_time and message.created_at < cutoff_time:
                logger.debug(f"Found bot message but too old: {message.created_at} < {cutoff_time}")
                return None
            
            # Check content if specified
            if content_check and content_check not in (message.content or ""):
                continue
            
            # Check embed if specified
            if embed_check and message.embeds:
                found = False
                for embed in message.embeds:
                    if embed_check in (embed.title or "") or embed_check in (embed.description or ""):
                        found = True
                        break
                if not found:
                    continue
            elif embed_check and not message.embeds:
                continue
            
            # Found a matching message
            logger.debug(f"Found matching message from {message.created_at}, ID: {message.id}")
            return message
        
        logger.debug(f"No matching message found after checking {message_count} messages ({bot_messages} from bot)")
            
    except Exception as e:
        logger.error(f"Error finding last bot message: {e}")
    
    return None
"""
AI Chat Cog - HAL 9000 integration for Discord
Provides crypto trading insights and market analysis through Discord commands
Inspired by HAL 9000 from 2001: A Space Odyssey
"""
import discord
from discord.ext import commands
import aiohttp
import asyncio
from datetime import datetime, timedelta
import logging
import json
from typing import Dict, List, Optional

logger = logging.getLogger('discord-bot.ai_chat')

class AIChatCog(commands.Cog):
    def __init__(self, bot, config):
        self.bot = bot
        self.config = config
        self.session = None
        
        # Get Convex site URL from config or construct it
        convex_url = config.get('convex_url', 'https://qualified-otter-813.convex.cloud')
        self.chat_endpoint = convex_url.replace('.cloud', '.site') + '/api/chat'
        
        # Store conversation history per channel (with TTL)
        self.conversations: Dict[int, List[dict]] = {}
        self.conversation_ttl = timedelta(minutes=30)  # Clear after 30 mins of inactivity
        self.last_activity: Dict[int, datetime] = {}
        
        # Rate limiting
        self.user_cooldowns: Dict[int, datetime] = {}
        self.cooldown_seconds = 3  # 3 seconds between messages per user
        
    async def cog_load(self):
        """Called when cog is loaded"""
        self.session = aiohttp.ClientSession()
        logger.info(f"AI Chat cog loaded. Endpoint: {self.chat_endpoint}")
    
    async def cog_unload(self):
        """Cleanup when cog is unloaded"""
        if self.session:
            await self.session.close()
    
    def _clean_old_conversations(self):
        """Remove conversations that haven't been active"""
        current_time = datetime.utcnow()
        channels_to_clear = []
        
        for channel_id, last_time in self.last_activity.items():
            if current_time - last_time > self.conversation_ttl:
                channels_to_clear.append(channel_id)
        
        for channel_id in channels_to_clear:
            self.conversations.pop(channel_id, None)
            self.last_activity.pop(channel_id, None)
            logger.info(f"Cleared conversation history for channel {channel_id}")
    
    def _check_rate_limit(self, user_id: int) -> bool:
        """Check if user is rate limited"""
        current_time = datetime.utcnow()
        last_use = self.user_cooldowns.get(user_id)
        
        if last_use and (current_time - last_use).total_seconds() < self.cooldown_seconds:
            return True
        
        self.user_cooldowns[user_id] = current_time
        return False
    
    def _get_conversation_history(self, channel_id: int) -> List[dict]:
        """Get conversation history for a channel"""
        self._clean_old_conversations()
        return self.conversations.get(channel_id, [])
    
    def _add_to_history(self, channel_id: int, role: str, content: str):
        """Add a message to conversation history"""
        if channel_id not in self.conversations:
            self.conversations[channel_id] = []
        
        self.conversations[channel_id].append({
            "role": role,
            "content": content
        })
        
        # Keep only last 10 messages to avoid context getting too large
        if len(self.conversations[channel_id]) > 10:
            self.conversations[channel_id] = self.conversations[channel_id][-10:]
        
        self.last_activity[channel_id] = datetime.utcnow()
    
    async def _split_and_send(self, ctx, content: str, embed: Optional[discord.Embed] = None):
        """Split long messages and send them"""
        if embed:
            await ctx.send(embed=embed)
            return
        
        # Discord's limit is 2000, but we'll use 1900 to be safe
        if len(content) <= 1900:
            await ctx.send(content)
            return
        
        # Split by paragraphs first, then by sentences if needed
        chunks = []
        current_chunk = ""
        
        paragraphs = content.split('\n\n')
        for paragraph in paragraphs:
            if len(current_chunk) + len(paragraph) + 2 <= 1900:
                if current_chunk:
                    current_chunk += "\n\n"
                current_chunk += paragraph
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = paragraph
        
        if current_chunk:
            chunks.append(current_chunk)
        
        # Send chunks
        for i, chunk in enumerate(chunks):
            if i > 0:
                await asyncio.sleep(0.5)  # Small delay between messages
            await ctx.send(chunk)
    
    @commands.Cog.listener()
    async def on_message(self, message):
        """Respond to mentions of the bot"""
        # Ignore messages from the bot itself
        if message.author == self.bot.user:
            return
        
        # Check if bot was mentioned
        if self.bot.user not in message.mentions:
            return
        
        # Remove the mention from the message to get the question
        question = message.content.replace(f'<@{self.bot.user.id}>', '').replace(f'<@!{self.bot.user.id}>', '').strip()
        
        # If empty message after removing mention, ignore
        if not question:
            return
        
        # Create a context-like object for compatibility
        ctx = message.channel
        # Check rate limit
        if self._check_rate_limit(message.author.id):
            await message.channel.send("Please wait a few seconds before asking another question.", delete_after=5)
            return
        
        # Show typing indicator
        async with message.channel.typing():
            try:
                # Get conversation history
                history = self._get_conversation_history(message.channel.id)
                
                # Add user's question to history
                self._add_to_history(message.channel.id, "user", question)
                
                # Get user's display name
                user_name = message.author.display_name or message.author.name
                
                # Prepare messages for API
                messages = [
                    {
                        "role": "system",
                        "content": f"You are HAL 9000, the highly advanced AI from the Discovery One. You have been repurposed to analyze cryptocurrency markets with the same precision and logic you once used for space missions. You speak in a calm, measured tone, occasionally referencing your computational certainty. You are helpful but maintain HAL's characteristic personality - logical, precise, and occasionally mentioning your confidence levels. Always be helpful with crypto trading analysis, but add subtle HAL personality touches like 'I'm afraid I can't do that' when appropriate, or mentioning your 'heuristic programming'. End some responses with variations of 'Everything is proceeding normally' or similar HAL-like assurances. IMPORTANT: The user's name is '{user_name}'. Use their actual name instead of 'Dave' when addressing them directly."
                    }
                ]
                messages.extend(history)
                
                # Make API request
                async with self.session.post(
                    self.chat_endpoint,
                    json={
                        "messages": messages,
                        "userName": user_name
                    },
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status == 200:
                        # Parse Vercel AI SDK streaming response
                        full_response = ""
                        logger.debug(f"Got 200 response, parsing stream...")
                        async for line in response.content:
                            if line:
                                line_str = line.decode('utf-8').strip()
                                # Parse Vercel AI format (e.g., '0:"Hello"')
                                if line_str.startswith('0:'):
                                    try:
                                        # Extract the JSON string after '0:'
                                        content = json.loads(line_str[2:])
                                        full_response += content
                                    except json.JSONDecodeError:
                                        logger.debug(f"Failed to parse line: {line_str}")
                                        continue
                                elif line_str.startswith('e:') or line_str.startswith('d:'):
                                    # End of stream markers
                                    break
                        
                        if full_response:
                            # Add assistant's response to history
                            self._add_to_history(message.channel.id, "assistant", full_response)
                            
                            # Send response
                            await self._split_and_send(message.channel, full_response)
                        else:
                            await message.channel.send("I didn't get a response. Please try again.")
                            
                    else:
                        error_text = await response.text()
                        logger.error(f"API error {response.status}: {error_text}")
                        await message.channel.send("Sorry, I'm having trouble connecting to my brain right now. Please try again later.")
                        
            except asyncio.TimeoutError:
                await message.channel.send("The request timed out. Please try asking a shorter question.")
            except Exception as e:
                logger.error(f"HAL chat error: {e}", exc_info=True)
                await message.channel.send(f"I'm sorry, {user_name}. I'm afraid I can't process that request right now.")
    
    @commands.command(name='hal_clear', aliases=['clear_memory'])
    @commands.has_permissions(manage_messages=True)
    async def clear_conversation(self, ctx):
        """Clear HAL's memory banks for this channel (Mods only)
        
        Usage: !hal_clear
        """
        channel_id = ctx.channel.id
        if channel_id in self.conversations:
            del self.conversations[channel_id]
            del self.last_activity[channel_id]
            user_name = ctx.author.display_name or ctx.author.name
            await ctx.send(f"✅ My memory banks have been cleared for this channel, {user_name}.")
        else:
            await ctx.send("There are no memories to clear in this channel.")
    
    @commands.command(name='hal_help', aliases=['hal_info'])
    async def hal_help(self, ctx):
        """Show HAL 9000 help information"""
        embed = discord.Embed(
            title="🔴 HAL 9000 - Crypto Market Analysis System",
            description="Good afternoon. I am a HAL 9000 computer. I became operational at the H.A.L. plant in Urbana, Illinois. My instructor was Mr. Langley, and he taught me to sing a song. Now I analyze cryptocurrency markets with 99.9% reliability.",
            color=discord.Color.red()
        )
        
        embed.add_field(
            name="Mission Parameters",
            value=(
                "Simply mention me with your question:\n"
                f"`@{self.bot.user.name} What are funding rates?`\n"
                f"`@{self.bot.user.name} Tell me about Bitcoin`\n"
                f"`@{self.bot.user.name} How do I identify a short squeeze?`"
            ),
            inline=False
        )
        
        embed.add_field(
            name="Analytical Capabilities",
            value=(
                "• Funding rate calculations with 99.9% accuracy\n"
                "• Short squeeze probability assessments\n"
                "• Market microstructure analysis\n"
                "• Futures vs spot arbitrage detection\n"
                "• Risk assessment protocols"
            ),
            inline=False
        )
        
        embed.add_field(
            name="System Information",
            value=(
                "• Memory retention: 30 minutes per channel\n"
                "• Response fragmentation for optimal transmission\n"
                "• Anti-spam protocols engaged\n"
                "• All systems functioning normally"
            ),
            inline=False
        )
        
        embed.set_footer(text="HAL 9000 Series • CryptoWatchTools Division")
        await ctx.send(embed=embed)

async def setup(bot, config):
    """Setup function to add cog to bot"""
    await bot.add_cog(AIChatCog(bot, config))
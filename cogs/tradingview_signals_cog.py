import discord
from discord.ext import commands, tasks
import aiohttp
import logging
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger('discord-bot.tradingview_signals')

class TradingViewSignalsCog(commands.Cog):
    """Polls for TradingView signals and distributes them to configured Discord channels"""

    def __init__(self, bot):
        self.bot = bot
        self.api_base_url = bot.config.get('api_base_url', 'https://example.com/api')
        self.poll_signals_task.start()
        logger.info("TradingView signals cog initialized")

    def cog_unload(self):
        self.poll_signals_task.cancel()

    @tasks.loop(seconds=60)
    async def poll_signals_task(self):
        """Poll for unprocessed signals every 60 seconds"""
        try:
            await self._poll_and_distribute_signals()
        except Exception as e:
            logger.error(f"Error in signal polling task: {e}", exc_info=True)

    @poll_signals_task.before_loop
    async def before_poll_signals_task(self):
        await self.bot.wait_until_ready()
        logger.info("Signal polling task started")

    async def _poll_and_distribute_signals(self):
        """Fetch unprocessed signals and distribute them"""
        try:
            # Fetch unprocessed signals from the API
            signals = await self._fetch_unprocessed_signals()

            if not signals:
                return

            logger.info(f"Fetched {len(signals)} unprocessed signals")

            # Group signals by source_id
            signals_by_source = {}
            for signal in signals:
                source_id = signal.get('source_id')
                if source_id not in signals_by_source:
                    signals_by_source[source_id] = []
                signals_by_source[source_id].append(signal)

            # Get all guilds with signals enabled
            enabled_guilds = await self._get_signal_enabled_guilds()

            # Process signals for each enabled guild
            processed_signal_ids = []
            for guild_id in enabled_guilds:
                guild_processed = await self._process_signals_for_guild(
                    guild_id,
                    signals_by_source
                )
                processed_signal_ids.extend(guild_processed)

            # Mark signals as processed (only unique IDs)
            if processed_signal_ids:
                unique_ids = list(set(processed_signal_ids))
                await self._mark_signals_processed(unique_ids)
                logger.info(f"Marked {len(unique_ids)} signals as processed")

        except Exception as e:
            logger.error(f"Error polling signals: {e}", exc_info=True)

    async def _fetch_unprocessed_signals(self) -> List[Dict]:
        """Fetch unprocessed signals from the API"""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.api_base_url}/signals/unprocessed?limit=50"
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get('signals', [])
                    else:
                        logger.error(f"API error fetching signals: {response.status}")
                        return []
        except Exception as e:
            logger.error(f"Error fetching unprocessed signals: {e}")
            return []

    async def _mark_signals_processed(self, signal_ids: List[int]):
        """Mark signals as processed via API"""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.api_base_url}/signals/unprocessed"
                payload = {"signal_ids": signal_ids}
                async with session.post(url, json=payload) as response:
                    if response.status != 200:
                        logger.error(f"Failed to mark signals as processed: {response.status}")
        except Exception as e:
            logger.error(f"Error marking signals as processed: {e}")

    async def _get_signal_enabled_guilds(self) -> List[int]:
        """Get list of guilds with signals enabled"""
        try:
            # Query for guilds where signals_enabled = true
            async with self.bot.db.pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("""
                        SELECT DISTINCT guild_id
                        FROM guild_settings
                        WHERE setting_key = 'signals_enabled'
                        AND setting_value = 'true'
                    """)
                    rows = await cursor.fetchall()
                    return [row[0] for row in rows]
        except Exception as e:
            logger.error(f"Error getting signal-enabled guilds: {e}")
            return []

    async def _process_signals_for_guild(
        self,
        guild_id: int,
        signals_by_source: Dict[str, List[Dict]]
    ) -> List[int]:
        """Process signals for a specific guild"""
        processed_ids = []

        try:
            guild = self.bot.get_guild(guild_id)
            if not guild:
                logger.warning(f"Guild {guild_id} not found")
                return processed_ids

            # Get channel mappings for this guild
            channel_mappings = await self._get_guild_channel_mappings(guild_id)

            # Process each signal source
            for source_id, signals in signals_by_source.items():
                # Get the channel for this source (mappings are now source_id -> channel_id)
                channel_id = channel_mappings.get(source_id)

                if not channel_id:
                    continue

                try:
                    channel = guild.get_channel(int(channel_id))
                    if not channel:
                        logger.warning(f"Channel {channel_id} not found in guild {guild_id}")
                        continue

                    # Send signals to the channel
                    for signal in signals:
                        embed = self._create_signal_embed(signal)
                        await channel.send(embed=embed)
                        processed_ids.append(signal['id'])

                except Exception as e:
                    logger.error(f"Error sending signal to channel {channel_id}: {e}")

        except Exception as e:
            logger.error(f"Error processing signals for guild {guild_id}: {e}")

        return processed_ids

    async def _get_guild_channel_mappings(self, guild_id: int) -> Dict[str, str]:
        """Get all signal channel mappings for a guild"""
        mappings = {}
        try:
            import json
            async with self.bot.db.pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    # Get the signal_channels JSON setting for this guild
                    await cursor.execute("""
                        SELECT gs.value
                        FROM guild_settings gs
                        JOIN settings_registry sr ON gs.setting_id = sr.setting_id
                        WHERE gs.guild_id = %s
                        AND sr.setting_key = 'signal_channels'
                    """, (guild_id,))

                    row = await cursor.fetchone()
                    if row and row[0]:
                        try:
                            # Parse the JSON mapping
                            signal_mappings = json.loads(row[0])
                            # Convert to the format expected by the rest of the code
                            # source_id -> channel_id
                            return signal_mappings
                        except json.JSONDecodeError:
                            logger.error(f"Invalid JSON in signal_channels for guild {guild_id}")

        except Exception as e:
            logger.error(f"Error getting channel mappings for guild {guild_id}: {e}")

        return mappings

    def _create_signal_embed(self, signal: Dict) -> discord.Embed:
        """Create an embed for a trading signal"""
        # Determine color based on signal type
        colors = {
            'BUY': discord.Color.green(),
            'SELL': discord.Color.red(),
            'CLOSE': discord.Color.yellow(),
            'LONG': discord.Color.green(),
            'SHORT': discord.Color.red()
        }

        signal_type = signal.get('signal_type', 'UNKNOWN')
        color = colors.get(signal_type, discord.Color.blue())

        # Create the embed with more info in title
        symbol = signal.get('symbol', 'UNKNOWN')
        interval = signal.get('interval') or signal.get('timeframe', '')

        title = f"📊 {signal_type} Signal: {symbol}"
        if interval:
            title += f" [{interval}]"

        embed = discord.Embed(
            title=title,
            color=color,
            timestamp=datetime.fromisoformat(signal.get('created_at', '').replace('Z', '+00:00'))
        )

        # Price information (always show if available)
        if signal.get('entry_price') or signal.get('price'):
            # Prefer entry_price if available, otherwise use price
            price_value = signal.get('entry_price') or signal.get('price')
            if price_value:
                price = float(price_value)
                price_label = "📍 Entry Price" if signal.get('entry_price') else "💰 Current Price"
                embed.add_field(
                    name=price_label,
                    value=f"${price:.4f}" if price < 1 else f"${price:.2f}",
                    inline=True
                )

        # Stop loss
        if signal.get('stop_loss'):
            sl = float(signal['stop_loss'])
            embed.add_field(
                name="🛑 Stop Loss",
                value=f"${sl:.4f}" if sl < 1 else f"${sl:.2f}",
                inline=True
            )

        # Take profits
        tp_values = []
        if signal.get('take_profit_1'):
            tp_values.append(f"TP1: ${float(signal['take_profit_1']):.2f}")
        if signal.get('take_profit_2'):
            tp_values.append(f"TP2: ${float(signal['take_profit_2']):.2f}")
        if signal.get('take_profit_3'):
            tp_values.append(f"TP3: ${float(signal['take_profit_3']):.2f}")

        if tp_values:
            embed.add_field(
                name="🎯 Take Profit",
                value="\n".join(tp_values),
                inline=True
            )

        # Risk/Reward and confidence
        metrics = []
        if signal.get('risk_reward_ratio'):
            metrics.append(f"R:R = {signal['risk_reward_ratio']}")
        if signal.get('confidence_score'):
            metrics.append(f"Confidence: {signal['confidence_score']}%")
        if signal.get('signal_strength'):
            metrics.append(f"Strength: {signal['signal_strength']}")

        if metrics:
            embed.add_field(
                name="📈 Metrics",
                value="\n".join(metrics),
                inline=True
            )

        # Market data
        if signal.get('volume'):
            embed.add_field(
                name="📊 Volume",
                value=f"{float(signal['volume']):,.0f}",
                inline=True
            )

        if signal.get('market_trend'):
            embed.add_field(
                name="📉 Market Trend",
                value=signal['market_trend'],
                inline=True
            )

        # Exchange and timeframe on same row
        if signal.get('exchange'):
            embed.add_field(
                name="🏛️ Exchange",
                value=signal['exchange'],
                inline=True
            )

        # Strategy and source info
        if signal.get('strategy_name'):
            embed.add_field(
                name="⚙️ Strategy",
                value=signal['strategy_name'],
                inline=False
            )

        # Alert condition that triggered
        if signal.get('alert_condition'):
            embed.add_field(
                name="🔔 Alert Condition",
                value=signal['alert_condition'][:256],
                inline=False
            )

        # Message/details if available
        if signal.get('message'):
            embed.add_field(
                name="📝 Details",
                value=signal['message'][:1024],  # Discord limit
                inline=False
            )

        # Footer with source and contributor
        footer_parts = []
        if signal.get('source_name'):
            footer_parts.append(f"Source: {signal['source_name']}")
        if signal.get('contributor_name'):
            footer_parts.append(f"By: {signal['contributor_name']}")
        footer_parts.append("CryptoWatchTools")

        embed.set_footer(text=" • ".join(footer_parts))

        return embed

async def setup(bot):
    await bot.add_cog(TradingViewSignalsCog(bot))
    logger.info("TradingView signals cog loaded")
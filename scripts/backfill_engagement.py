#!/usr/bin/env python3
"""
Engagement Data Backfill Script
Scans Discord message history and populates member_activity_daily table
Designed to run as a subprocess called by the bot
"""
import os
import sys
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from typing import Dict, Set, Optional
import discord
from discord.ext import commands
import pymysql
from pymysql.cursors import DictCursor
from dotenv import load_dotenv
import json
import time

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# When running as subprocess, minimize output
if '--quiet' in sys.argv:
    logging.basicConfig(level=logging.WARNING)

# Load environment variables
load_dotenv()

# Configure logging
# Get the logs directory path (one level up from scripts)
script_dir = os.path.dirname(os.path.abspath(__file__))
logs_dir = os.path.join(os.path.dirname(script_dir), 'logs')

# Create logs directory if it doesn't exist
os.makedirs(logs_dir, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(logs_dir, 'backfill_engagement.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration
BATCH_SIZE = 100  # Messages per batch
CHANNEL_LIMIT = 50  # Max channels to scan per guild
HISTORY_DAYS = 90  # Days of history to scan
RATE_LIMIT_DELAY = 1  # Seconds between channel scans
PROGRESS_FILE = 'backfill_progress.json'

class EngagementBackfill:
    def __init__(self):
        self.bot = None
        self.db = None
        self.progress = self.load_progress()
        
    def load_progress(self) -> Dict:
        """Load progress from file to resume if interrupted"""
        if os.path.exists(PROGRESS_FILE):
            try:
                with open(PROGRESS_FILE, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {'guilds': {}, 'completed_guilds': []}
    
    def save_progress(self):
        """Save current progress"""
        with open(PROGRESS_FILE, 'w') as f:
            json.dump(self.progress, f, indent=2)
    
    def get_db_connection(self):
        """Get database connection"""
        # Load config to determine environment
        # First try CONFIG_FILE env var (set in docker-compose)
        config_filename = os.getenv('CONFIG_FILE')
        if not config_filename:
            # Fallback to BOT_ENV
            env = os.getenv('BOT_ENV', 'development')
            config_filename = f'config.{env}.json'
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            config_filename
        )
        
        # Check if config exists, if not fallback to development
        if not os.path.exists(config_path):
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                'config.development.json'
            )
        
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        # Use environment variables for database connection
        host = os.getenv('MYSQL_HOST', 'localhost')
        password = os.getenv('MYSQL_PASSWORD', '')

        if not password:
            raise ValueError("MYSQL_PASSWORD environment variable is required")
        
        logger.info(f"=== DATABASE CONNECTION DETAILS ===")
        logger.info(f"Host: {host}")
        logger.info(f"Database: cryptowatch_bot")
        logger.info(f"User: cwt_user")
        logger.info(f"Environment: {'PRODUCTION' if host == 'localhost' else 'DEVELOPMENT'}")
        
        conn = pymysql.connect(
            host=host,
            port=3306,
            user='cwt_user',
            password=password,
            database='cryptowatch_bot',  # Always use bot database
            charset='utf8mb4',
            cursorclass=DictCursor,
            autocommit=True
        )
        
        # Verify we're in the right database
        with conn.cursor() as cursor:
            cursor.execute("SELECT DATABASE()")
            db_name = cursor.fetchone()['DATABASE()']
            logger.info(f"✓ Successfully connected to database: {db_name}")
            
            # Check if the table exists
            cursor.execute("SHOW TABLES LIKE 'member_activity_daily'")
            if cursor.fetchone():
                logger.info("✓ Table 'member_activity_daily' exists")
                
                # Show current data stats
                cursor.execute("""
                    SELECT 
                        COUNT(DISTINCT guild_id) as guilds,
                        COUNT(DISTINCT user_id) as users,
                        COUNT(*) as records,
                        MIN(activity_date) as earliest,
                        MAX(activity_date) as latest
                    FROM member_activity_daily
                """)
                stats = cursor.fetchone()
                logger.info(f"  Current table stats: {stats['guilds']} guilds, {stats['users']} users, {stats['records']} records")
                logger.info(f"  Date range: {stats['earliest']} to {stats['latest']}")
            else:
                logger.error("✗ Table member_activity_daily does NOT exist!")
        
        return conn
    
    async def init_bot(self):
        """Initialize Discord bot"""
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.guilds = True
        
        self.bot = commands.Bot(command_prefix='!', intents=intents)
        
        @self.bot.event
        async def on_ready():
            logger.info(f'Bot connected as {self.bot.user}')
            logger.info(f'Connected to {len(self.bot.guilds)} guilds')
    
    async def scan_channel(self, channel: discord.TextChannel, 
                          after_date: datetime) -> Dict[int, Dict[str, int]]:
        """Scan a channel for member activity"""
        member_activity = defaultdict(lambda: defaultdict(int))
        message_count = 0
        
        try:
            # Get message history
            async for message in channel.history(limit=None, after=after_date):
                if message.author.bot:
                    continue
                    
                # Get date in UTC
                msg_date = message.created_at.date()
                member_id = message.author.id
                
                member_activity[member_id][str(msg_date)] += 1
                message_count += 1
                
                # Log progress every 1000 messages
                if message_count % 1000 == 0:
                    logger.debug(f"  Processed {message_count} messages in #{channel.name}")
            
            logger.info(f"  Channel #{channel.name}: {message_count} messages from {len(member_activity)} members")
            
        except discord.Forbidden:
            logger.warning(f"  No access to channel #{channel.name}")
        except Exception as e:
            logger.error(f"  Error scanning channel #{channel.name}: {e}")
        
        return member_activity
    
    async def scan_guild(self, guild: discord.Guild) -> Dict[int, Dict[str, int]]:
        """Scan all channels in a guild"""
        logger.info(f"Scanning guild: {guild.name} (ID: {guild.id})")
        
        # Check if already completed
        if guild.id in self.progress['completed_guilds']:
            logger.info(f"  Guild already completed, skipping")
            return {}
        
        # Calculate date range
        after_date = datetime.now(timezone.utc) - timedelta(days=HISTORY_DAYS)
        
        # Get progress for this guild
        guild_progress = self.progress['guilds'].get(str(guild.id), {
            'scanned_channels': [],
            'total_channels': 0
        })
        
        # Aggregate member activity across all channels
        guild_activity = defaultdict(lambda: defaultdict(int))
        
        # Get text channels
        text_channels = [ch for ch in guild.text_channels 
                        if ch.permissions_for(guild.me).read_messages]
        
        guild_progress['total_channels'] = len(text_channels)
        logger.info(f"  Found {len(text_channels)} accessible text channels")
        
        # Scan each channel
        for i, channel in enumerate(text_channels[:CHANNEL_LIMIT]):
            # Skip if already scanned
            if channel.id in guild_progress['scanned_channels']:
                logger.debug(f"  Channel #{channel.name} already scanned, skipping")
                continue
            
            logger.info(f"  Scanning channel {i+1}/{min(len(text_channels), CHANNEL_LIMIT)}: #{channel.name}")
            
            # Scan channel
            channel_activity = await self.scan_channel(channel, after_date)
            
            # Merge into guild activity
            for member_id, dates in channel_activity.items():
                for date, count in dates.items():
                    guild_activity[member_id][date] += count
            
            # Mark channel as scanned
            guild_progress['scanned_channels'].append(channel.id)
            self.progress['guilds'][str(guild.id)] = guild_progress
            self.save_progress()
            
            # Rate limit delay
            await asyncio.sleep(RATE_LIMIT_DELAY)
        
        # Mark guild as completed
        self.progress['completed_guilds'].append(guild.id)
        self.save_progress()
        
        logger.info(f"  Guild scan complete: {len(guild_activity)} members with activity")
        return guild_activity
    
    def store_activity(self, guild_id: int, member_activity: Dict[int, Dict[str, int]]):
        """Store activity data in database"""
        if not member_activity:
            logger.info(f"No activity data to store for guild {guild_id}")
            return
        
        logger.info(f"=== STORING ACTIVITY DATA ===")
        logger.info(f"Guild ID: {guild_id}")
        logger.info(f"Members with activity: {len(member_activity)}")
        
        # Log sample of data being stored
        total_messages = sum(sum(dates.values()) for dates in member_activity.values())
        logger.info(f"Total messages to store: {total_messages}")
        
        try:
            with self.get_db_connection() as connection:
                with connection.cursor() as cursor:
                    # Prepare batch insert
                    values = []
                    for member_id, dates in member_activity.items():
                        for date_str, message_count in dates.items():
                            values.append((
                                guild_id,
                                member_id,
                                date_str,
                                message_count
                            ))
                    
                    # Batch insert with ON DUPLICATE KEY UPDATE
                    if values:
                        try:
                            # Debug: Check table structure first
                            cursor.execute("DESCRIBE member_activity_daily")
                            fields = cursor.fetchall()
                            field_names = [f['Field'] for f in fields]
                            logger.info(f"  Table fields: {field_names}")
                            
                            cursor.executemany("""
                                INSERT INTO member_activity_daily 
                                (guild_id, user_id, activity_date, message_count)
                                VALUES (%s, %s, %s, %s)
                                ON DUPLICATE KEY UPDATE 
                                message_count = message_count + VALUES(message_count)
                            """, values)
                            
                            logger.info(f"✓ Successfully inserted/updated {len(values)} activity records")
                            
                            # Verify what was stored
                            cursor.execute("""
                                SELECT COUNT(*) as count, SUM(message_count) as total
                                FROM member_activity_daily
                                WHERE guild_id = %s
                            """, (guild_id,))
                            result = cursor.fetchone()
                            logger.info(f"  Guild {guild_id} now has {result['count']} records with {result['total']} total messages")
                        except Exception as e:
                            logger.error(f"✗ Failed to insert records: {e}")
                            logger.error(f"  First value sample: {values[0] if values else 'None'}")
                            raise
                        
        except Exception as e:
            logger.error(f"Database error: {e}")
            raise
    
    def get_enabled_guilds(self) -> Set[int]:
        """Get list of guilds with engagement tracking enabled"""
        enabled_guilds = set()
        
        try:
            with self.get_db_connection() as connection:
                with connection.cursor() as cursor:
                    cursor.execute("""
                        SELECT DISTINCT guild_id 
                        FROM guild_settings 
                        WHERE setting_key = 'engagement.enabled' 
                        AND setting_value = '1'
                    """)
                    
                    for row in cursor.fetchall():
                        enabled_guilds.add(row['guild_id'])
                        
        except Exception as e:
            logger.error(f"Error fetching enabled guilds: {e}")
        
        return enabled_guilds
    
    async def run(self, specific_guild_id: Optional[int] = None):
        """Run the backfill process"""
        logger.info("Starting engagement data backfill")
        
        # Initialize bot
        await self.init_bot()
        
        # Load config to get bot token
        env = os.getenv('BOT_ENV', 'development')
        config_filename = f'config.{env}.json'
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            config_filename
        )
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        # Start bot in background
        bot_task = asyncio.create_task(
            self.bot.start(config['bot_token'])
        )
        
        # Wait for bot to be ready
        await asyncio.sleep(5)
        
        if not self.bot.is_ready():
            logger.error("Bot failed to connect")
            return
        
        try:
            if specific_guild_id:
                # Scan specific guild
                guild = self.bot.get_guild(specific_guild_id)
                if guild:
                    activity = await self.scan_guild(guild)
                    self.store_activity(guild.id, activity)
                else:
                    logger.error(f"Guild {specific_guild_id} not found")
            else:
                # Get guilds with engagement enabled
                enabled_guilds = self.get_enabled_guilds()
                logger.info(f"Found {len(enabled_guilds)} guilds with engagement enabled")
                
                # Scan each guild
                for guild in self.bot.guilds:
                    if guild.id in enabled_guilds:
                        activity = await self.scan_guild(guild)
                        self.store_activity(guild.id, activity)
                    else:
                        logger.info(f"Skipping guild {guild.name} (engagement not enabled)")
            
            logger.info("Backfill complete!")
            
            # Clean up progress file
            if os.path.exists(PROGRESS_FILE):
                os.remove(PROGRESS_FILE)
                logger.info("Cleaned up progress file")
                
        except Exception as e:
            logger.error(f"Error during backfill: {e}", exc_info=True)
        finally:
            # Stop bot
            await self.bot.close()

async def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Backfill engagement data from Discord history')
    parser.add_argument('--guild', type=int, help='Specific guild ID to backfill')
    parser.add_argument('--days', type=int, default=90, help='Days of history to scan (default: 90)')
    parser.add_argument('--reset', action='store_true', help='Reset progress and start fresh')
    parser.add_argument('--quiet', action='store_true', help='Minimize output (for subprocess)')
    
    args = parser.parse_args()
    
    # Update global config
    global HISTORY_DAYS
    HISTORY_DAYS = args.days
    
    # Reset progress if requested
    if args.reset and os.path.exists(PROGRESS_FILE):
        os.remove(PROGRESS_FILE)
        logger.info("Reset progress file")
    
    try:
        # Run backfill
        backfill = EngagementBackfill()
        await backfill.run(args.guild)
        sys.exit(0)  # Success
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)  # Failure

if __name__ == '__main__':
    asyncio.run(main())
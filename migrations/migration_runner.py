"""
Database migration runner for Discord bot
"""
import os
import importlib.util
import logging
from datetime import datetime
from typing import List, Tuple
import aiomysql

logger = logging.getLogger('discord-bot.migrations')

class MigrationRunner:
    def __init__(self, pool):
        self.pool = pool
        
    async def ensure_migrations_table(self):
        """Create migrations tracking table if it doesn't exist"""
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS schema_migrations (
                        version VARCHAR(255) PRIMARY KEY,
                        executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                await conn.commit()
    
    async def get_executed_migrations(self) -> List[str]:
        """Get list of already executed migrations"""
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("SELECT version FROM schema_migrations ORDER BY version")
                result = await cursor.fetchall()
                return [row[0] for row in result]
    
    async def get_pending_migrations(self) -> List[Tuple[str, str]]:
        """Get list of migrations that need to be run"""
        executed = await self.get_executed_migrations()
        
        # Get all migration files
        migrations_dir = os.path.dirname(os.path.abspath(__file__))
        migration_files = []
        
        for filename in sorted(os.listdir(migrations_dir)):
            if filename.endswith('.py') and filename[0].isdigit():
                version = filename[:-3]  # Remove .py extension
                if version not in executed:
                    filepath = os.path.join(migrations_dir, filename)
                    migration_files.append((version, filepath))
        
        return migration_files
    
    async def run_migration(self, version: str, filepath: str):
        """Execute a single migration"""
        logger.info(f"Running migration: {version}")
        
        # Load the migration module
        spec = importlib.util.spec_from_file_location(f"migration_{version}", filepath)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # Run the migration
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                try:
                    # Start transaction
                    await conn.begin()
                    
                    # Run the up() function from the migration
                    await module.up(cursor)
                    
                    # Record migration as executed
                    await cursor.execute(
                        "INSERT INTO schema_migrations (version) VALUES (%s)",
                        (version,)
                    )
                    
                    # Commit transaction
                    await conn.commit()
                    logger.info(f"Migration {version} completed successfully")
                    
                except Exception as e:
                    # Rollback on error
                    await conn.rollback()
                    logger.error(f"Migration {version} failed: {e}")
                    raise
    
    async def run_all_pending(self):
        """Run all pending migrations"""
        await self.ensure_migrations_table()
        
        pending = await self.get_pending_migrations()
        if not pending:
            logger.info("No pending migrations")
            return
        
        logger.info(f"Found {len(pending)} pending migrations")
        
        for version, filepath in pending:
            await self.run_migration(version, filepath)
        
        logger.info("All migrations completed")
    
    async def rollback(self, version: str):
        """Rollback a specific migration"""
        migrations_dir = os.path.dirname(os.path.abspath(__file__))
        filepath = os.path.join(migrations_dir, f"{version}.py")
        
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Migration {version} not found")
        
        # Load the migration module
        spec = importlib.util.spec_from_file_location(f"migration_{version}", filepath)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # Check if migration has down() function
        if not hasattr(module, 'down'):
            raise AttributeError(f"Migration {version} has no down() function")
        
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cursor:
                try:
                    await conn.begin()
                    
                    # Run the down() function
                    await module.down(cursor)
                    
                    # Remove from migrations table
                    await cursor.execute(
                        "DELETE FROM schema_migrations WHERE version = %s",
                        (version,)
                    )
                    
                    await conn.commit()
                    logger.info(f"Rollback of {version} completed")
                    
                except Exception as e:
                    await conn.rollback()
                    logger.error(f"Rollback of {version} failed: {e}")
                    raise
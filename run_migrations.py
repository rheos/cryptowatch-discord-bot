#!/usr/bin/env python3
"""
Run database migrations for Discord bot
Usage: python3 run_migrations.py
"""
import os
import sys
import pymysql
from pymysql.cursors import DictCursor
import subprocess
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def get_applied_versions(connection):
    """Get list of applied migration versions"""
    try:
        with connection.cursor() as cursor:
            # Check if schema_migrations table exists
            cursor.execute("""
                SELECT COUNT(*) as count 
                FROM information_schema.tables 
                WHERE table_schema = 'cryptowatch_bot' 
                AND table_name = 'schema_migrations'
            """)
            
            if cursor.fetchone()['count'] == 0:
                return set()
            
            # Get applied versions
            cursor.execute("SELECT version FROM schema_migrations")
            return set(row['version'] for row in cursor.fetchall())
            
    except Exception:
        return set()

def run_migration(connection, filepath, version):
    """Run a single migration file"""
    migration_name = os.path.basename(filepath)
    
    # Special handling for 001 which uses async
    if version == 1:
        logger.info(f"\nRunning migration {version}: {migration_name}")
        
        try:
            with connection.cursor() as cursor:
                import importlib.util
                spec = importlib.util.spec_from_file_location("migration", filepath)
                migration = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(migration)
                
                # Create sync wrapper
                class SyncCursor:
                    def __init__(self, cursor):
                        self.cursor = cursor
                    
                    async def execute(self, query, params=None):
                        return self.cursor.execute(query, params)
                    
                    async def executemany(self, query, params):
                        return self.cursor.executemany(query, params)
                    
                    async def fetchone(self):
                        return self.cursor.fetchone()
                    
                    async def fetchall(self):
                        return self.cursor.fetchall()
                
                # Run async migration
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                sync_cursor = SyncCursor(cursor)
                loop.run_until_complete(migration.up(sync_cursor))
                loop.close()
                
                connection.commit()
                logger.info(f"✓ Migration {version} completed")
                return True
                
        except Exception as e:
            logger.error(f"❌ Migration {version} failed: {e}")
            connection.rollback()
            return False
    
    else:
        # Regular Python migrations
        logger.info(f"\nRunning migration {version}: {migration_name}")
        result = subprocess.run(
            ["python3", filepath],
            capture_output=False,
            text=True
        )
        
        if result.returncode == 0:
            # Record in schema_migrations
            try:
                with connection.cursor() as cursor:
                    description = migration_name.replace('.py', '').replace('_', ' ')
                    cursor.execute(
                        "INSERT INTO schema_migrations (version, description) VALUES (%s, %s)",
                        (version, description)
                    )
                    connection.commit()
                    logger.info(f"✓ Migration {version} completed")
                    return True
            except Exception as e:
                logger.error(f"Failed to record migration: {e}")
                return False
        else:
            logger.error(f"❌ Migration {version} failed")
            return False

def main():
    """Main entry point"""
    logger.info("\nStarting Discord bot database migrations...")
    
    # Determine if we're in Docker or production
    # In Docker, use 'mysql' service name; in production use 'localhost'
    mysql_host = os.getenv('MYSQL_HOST')
    if not mysql_host:
        # Check if we're in a Docker environment
        if os.path.exists('/.dockerenv') or os.getenv('ENVIRONMENT') == 'dev':
            mysql_host = 'mysql'
        else:
            # Production environment
            mysql_host = 'localhost'
    
    # Connect to database
    connection = pymysql.connect(
        host=mysql_host,
        port=int(os.getenv('MYSQL_PORT', 3306)),
        user=os.getenv('MYSQL_USER', 'cwt_user'),
        password=os.getenv('MYSQL_PASSWORD', 'example_password'),
        database='cryptowatch_bot',
        charset='utf8mb4',
        cursorclass=DictCursor,
        autocommit=False
    )
    
    try:
        # Get applied versions
        applied_versions = get_applied_versions(connection)
        
        # Discover all migration files
        # Use relative path that works both in Docker and production
        script_dir = os.path.dirname(os.path.abspath(__file__))
        migrations_dir = os.path.join(script_dir, "migrations")
        migration_files = sorted([
            f for f in os.listdir(migrations_dir) 
            if f.endswith('.py') and f[0].isdigit()
        ])
        
        # Extract version numbers and create migration list
        migrations = []
        for filename in migration_files:
            try:
                # Extract version from filename (e.g., "001" from "001_complete_schema.py")
                version = int(filename.split('_')[0])
                filepath = os.path.join(migrations_dir, filename)
                migrations.append((version, filepath))
            except ValueError:
                logger.warning(f"Skipping {filename} - couldn't extract version number")
        
        # Find pending migrations
        pending = [(v, f) for v, f in migrations if v not in applied_versions]
        
        if not pending:
            logger.info("✓ All migrations are already applied!")
            logger.info(f"  Applied versions: {sorted(applied_versions)}")
            return
        
        logger.info(f"Applied versions: {sorted(applied_versions)}")
        logger.info(f"Pending migrations: {[v for v, _ in pending]}")
        
        # Run pending migrations
        for version, filepath in pending:
            if not run_migration(connection, filepath, version):
                sys.exit(1)
        
        logger.info("\n" + "=" * 60)
        logger.info("✅ ALL MIGRATIONS COMPLETED SUCCESSFULLY!")
        logger.info("=" * 60)
        
    finally:
        connection.close()

if __name__ == "__main__":
    main()
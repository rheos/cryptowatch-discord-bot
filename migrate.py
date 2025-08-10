#!/usr/bin/env python3
"""
Database migration tool for Discord bot
Usage: python migrate.py [command] [args]
"""
import asyncio
import sys
import json
import aiomysql
from migrations.migration_runner import MigrationRunner
from config_loader import load_config

async def get_db_pool(config_file='config.json'):
    """Create database connection pool"""
    config = load_config(config_file)
    
    db_config = config.get('database', {})
    
    pool = await aiomysql.create_pool(
        host=db_config.get('host', 'localhost'),
        port=db_config.get('port', 3306),
        user=db_config.get('user', 'bot_user'),
        password=db_config.get('password'),
        db=db_config.get('name', 'cryptowatch_bot'),
        minsize=1,
        maxsize=5
    )
    
    return pool

async def run_migrations(config_file='config.json'):
    """Run all pending migrations"""
    pool = await get_db_pool(config_file)
    try:
        runner = MigrationRunner(pool)
        await runner.run_all_pending()
    finally:
        pool.close()
        await pool.wait_closed()

async def rollback_migration(version, config_file='config.json'):
    """Rollback a specific migration"""
    pool = await get_db_pool(config_file)
    try:
        runner = MigrationRunner(pool)
        await runner.rollback(version)
    finally:
        pool.close()
        await pool.wait_closed()

async def list_migrations(config_file='config.json'):
    """List all migrations and their status"""
    pool = await get_db_pool(config_file)
    try:
        runner = MigrationRunner(pool)
        await runner.ensure_migrations_table()
        
        executed = await runner.get_executed_migrations()
        pending = await runner.get_pending_migrations()
        
        print("\nExecuted migrations:")
        for version in executed:
            print(f"  ✓ {version}")
        
        print("\nPending migrations:")
        for version, _ in pending:
            print(f"  - {version}")
        
    finally:
        pool.close()
        await pool.wait_closed()

def main():
    """Main entry point"""
    commands = {
        'migrate': run_migrations,
        'rollback': rollback_migration,
        'list': list_migrations
    }
    
    if len(sys.argv) < 2:
        print("Usage: python migrate.py [migrate|rollback|list] [args]")
        print("  migrate [config.json]  - Run all pending migrations")
        print("  rollback <version> [config.json] - Rollback specific migration")
        print("  list [config.json] - List all migrations")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command not in commands:
        print(f"Unknown command: {command}")
        sys.exit(1)
    
    if command == 'rollback':
        if len(sys.argv) < 3:
            print("Usage: python migrate.py rollback <version> [config.json]")
            sys.exit(1)
        version = sys.argv[2]
        config_file = sys.argv[3] if len(sys.argv) > 3 else 'config.json'
        asyncio.run(rollback_migration(version, config_file))
    else:
        config_file = sys.argv[2] if len(sys.argv) > 2 else 'config.json'
        asyncio.run(commands[command](config_file))

if __name__ == '__main__':
    main()
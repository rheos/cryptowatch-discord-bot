"""
Migration to add left_at field to member_status table for tracking when members leave
This is a synchronous version that should work with the current migration runner
"""

import sys
import os
import pymysql
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('migration')

def main():
    """Add left_at field to member_status table"""
    # Get database connection from environment
    db_host = os.environ.get('MYSQL_HOST', 'mysql')
    db_port = int(os.environ.get('MYSQL_PORT', 3306))
    db_user = os.environ.get('MYSQL_USER', 'cwt_user')
    db_pass = os.environ.get('MYSQL_PASSWORD', '')
    db_name = 'cryptowatch_bot'
    
    try:
        connection = pymysql.connect(
            host=db_host,
            port=db_port,
            user=db_user,
            password=db_pass,
            database=db_name,
            charset='utf8mb4'
        )
        
        with connection.cursor() as cursor:
            logger.info("Checking if left_at column exists...")
            
            # Check if column already exists
            cursor.execute("""
                SELECT COUNT(*) 
                FROM information_schema.columns 
                WHERE table_schema = %s 
                AND table_name = 'member_status' 
                AND column_name = 'left_at'
            """, (db_name,))
            
            count = cursor.fetchone()[0]
            logger.info(f"Column check result: {count}")
            
            if count == 0:
                logger.info("Adding left_at column to member_status table...")
                
                # Add left_at column to member_status
                cursor.execute("""
                    ALTER TABLE member_status 
                    ADD COLUMN left_at TIMESTAMP NULL AFTER joined_at
                """)
                logger.info("Column added successfully")
                
                # Add index for left_at
                logger.info("Adding index for left_at column...")
                cursor.execute("""
                    ALTER TABLE member_status 
                    ADD INDEX idx_left_at (left_at)
                """)
                logger.info("Index added successfully")
                
                connection.commit()
                logger.info("✅ Added left_at column to member_status table")
            else:
                logger.info("ℹ️ left_at column already exists in member_status")
        
        connection.close()
        return 0
                    
    except Exception as e:
        logger.error(f"❌ Failed to add left_at column: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())

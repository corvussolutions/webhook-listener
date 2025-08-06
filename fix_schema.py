#!/usr/bin/env python3
"""
Database schema fix for webhook listener
Adds missing processing_notes column to webhook_logs table
"""

import os
import psycopg2
from urllib.parse import urlparse
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_db_connection():
    """Create database connection"""
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        raise ValueError("DATABASE_URL environment variable is required")
    
    parsed = urlparse(database_url)
    
    try:
        conn = psycopg2.connect(
            host=parsed.hostname,
            database=parsed.path[1:],
            user=parsed.username,
            password=parsed.password,
            port=parsed.port or 5432,
            connect_timeout=10
        )
        return conn
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        raise

def fix_schema():
    """Add missing processing_notes column to webhook_logs table"""
    conn = None
    cursor = None
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if processing_notes column exists
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'webhook_logs' 
            AND column_name = 'processing_notes'
        """)
        
        if cursor.fetchone():
            logger.info("processing_notes column already exists")
            return
        
        logger.info("Adding missing processing_notes column...")
        
        # Add the missing column
        cursor.execute("""
            ALTER TABLE webhook_logs 
            ADD COLUMN processing_notes TEXT
        """)
        
        conn.commit()
        logger.info("Successfully added processing_notes column")
        
        # Verify the fix
        cursor.execute("SELECT COUNT(*) FROM webhook_logs")
        count = cursor.fetchone()[0]
        logger.info(f"webhook_logs table has {count} records")
        
    except Exception as e:
        logger.error(f"Schema fix failed: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

if __name__ == '__main__':
    logger.info("Starting database schema fix...")
    fix_schema()
    logger.info("Schema fix completed successfully")
#!/usr/bin/env python3
"""
Database initialization script for webhook listener
Run this to set up or migrate the PostgreSQL database schema
"""

import os
import sys
import psycopg2
from urllib.parse import urlparse
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_database_url():
    """Get database URL from environment or prompt user"""
    db_url = os.environ.get('DATABASE_URL')
    
    if not db_url:
        print("\nDatabase URL not found in environment.")
        print("You can get this from your Render PostgreSQL dashboard.")
        print("It should look like: postgresql://user:pass@host:port/dbname")
        db_url = input("\nEnter your PostgreSQL database URL: ").strip()
        
        if not db_url:
            logger.error("Database URL is required")
            sys.exit(1)
    
    return db_url

def test_connection(db_url):
    """Test database connection"""
    try:
        parsed = urlparse(db_url)
        conn = psycopg2.connect(
            host=parsed.hostname,
            database=parsed.path[1:],
            user=parsed.username,
            password=parsed.password,
            port=parsed.port or 5432,
            connect_timeout=10
        )
        conn.close()
        logger.info("Database connection successful")
        return True
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return False

def init_schema(db_url):
    """Initialize database schema"""
    parsed = urlparse(db_url)
    
    try:
        conn = psycopg2.connect(
            host=parsed.hostname,
            database=parsed.path[1:],
            user=parsed.username,
            password=parsed.password,
            port=parsed.port or 5432
        )
        cursor = conn.cursor()
        
        # Start transaction
        conn.autocommit = False
        
        logger.info("Creating tables...")
        
        # Create linkedin_contacts table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS linkedin_contacts (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255),
                title VARCHAR(500),
                company VARCHAR(255),
                location VARCHAR(255),
                email VARCHAR(255) UNIQUE,
                linkedin_url VARCHAR(500),
                website VARCHAR(500),
                profile_data TEXT,
                raw_json JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create indexes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_linkedin_contacts_email 
            ON linkedin_contacts(email)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_linkedin_contacts_company 
            ON linkedin_contacts(company)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_linkedin_contacts_created 
            ON linkedin_contacts(created_at DESC)
        """)
        
        # Create webhook_logs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS webhook_logs (
                log_id SERIAL PRIMARY KEY,
                event_type VARCHAR(100),
                contact_email VARCHAR(255),
                contact_id VARCHAR(100),
                webhook_data JSONB,
                received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                processed BOOLEAN DEFAULT FALSE,
                processing_notes TEXT
            )
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_webhook_logs_received 
            ON webhook_logs(received_at DESC)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_webhook_logs_email 
            ON webhook_logs(contact_email)
        """)
        
        # Create update trigger function
        cursor.execute("""
            CREATE OR REPLACE FUNCTION update_updated_at_column()
            RETURNS TRIGGER AS $$
            BEGIN
                NEW.updated_at = CURRENT_TIMESTAMP;
                RETURN NEW;
            END;
            $$ language 'plpgsql';
        """)
        
        # Create trigger
        cursor.execute("""
            DROP TRIGGER IF EXISTS update_linkedin_contacts_updated_at ON linkedin_contacts;
            CREATE TRIGGER update_linkedin_contacts_updated_at 
            BEFORE UPDATE ON linkedin_contacts 
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
        """)
        
        # Check existing data
        cursor.execute("SELECT COUNT(*) FROM linkedin_contacts")
        contact_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM webhook_logs")
        log_count = cursor.fetchone()[0]
        
        # Commit transaction
        conn.commit()
        
        logger.info("Database schema initialized successfully")
        logger.info(f"Existing data: {contact_count} contacts, {log_count} webhook logs")
        
        cursor.close()
        conn.close()
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to initialize schema: {e}")
        if conn:
            conn.rollback()
        return False

def migrate_from_sqlite(db_url, sqlite_path='linkedin_contacts.db'):
    """Migrate data from SQLite to PostgreSQL"""
    if not os.path.exists(sqlite_path):
        logger.info("No SQLite database found to migrate")
        return True
    
    try:
        import sqlite3
        
        # Connect to SQLite
        sqlite_conn = sqlite3.connect(sqlite_path)
        sqlite_cursor = sqlite_conn.cursor()
        
        # Check if there's data to migrate
        sqlite_cursor.execute("SELECT COUNT(*) FROM linkedin_contacts")
        count = sqlite_cursor.fetchone()[0]
        
        if count == 0:
            logger.info("No data to migrate from SQLite")
            return True
        
        logger.info(f"Found {count} contacts to migrate")
        
        # Connect to PostgreSQL
        parsed = urlparse(db_url)
        pg_conn = psycopg2.connect(
            host=parsed.hostname,
            database=parsed.path[1:],
            user=parsed.username,
            password=parsed.password,
            port=parsed.port or 5432
        )
        pg_cursor = pg_conn.cursor()
        
        # Migrate contacts
        sqlite_cursor.execute("""
            SELECT name, title, company, location, email, 
                   linkedin_url, website, profile_data, raw_json,
                   created_at, updated_at
            FROM linkedin_contacts
        """)
        
        migrated = 0
        for row in sqlite_cursor.fetchall():
            try:
                pg_cursor.execute("""
                    INSERT INTO linkedin_contacts 
                    (name, title, company, location, email, linkedin_url, 
                     website, profile_data, raw_json, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (email) DO NOTHING
                """, row)
                migrated += pg_cursor.rowcount
            except Exception as e:
                logger.warning(f"Failed to migrate contact {row[4]}: {e}")
        
        pg_conn.commit()
        
        logger.info(f"Successfully migrated {migrated} contacts")
        
        sqlite_conn.close()
        pg_conn.close()
        
        return True
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        return False

def main():
    """Main initialization process"""
    print("=== Webhook Listener Database Initialization ===\n")
    
    # Get database URL
    db_url = get_database_url()
    
    # Test connection
    print("\nTesting database connection...")
    if not test_connection(db_url):
        print("Failed to connect to database. Please check your URL and try again.")
        sys.exit(1)
    
    # Initialize schema
    print("\nInitializing database schema...")
    if not init_schema(db_url):
        print("Failed to initialize schema.")
        sys.exit(1)
    
    # Ask about migration
    if os.path.exists('linkedin_contacts.db'):
        migrate = input("\nSQLite database found. Migrate existing data? (y/n): ").lower().strip()
        if migrate == 'y':
            print("\nMigrating data from SQLite...")
            migrate_from_sqlite(db_url)
    
    print("\n✅ Database initialization complete!")
    print("\nTo use this database URL in your webhook listener:")
    print("1. Set the DATABASE_URL environment variable in Render")
    print("2. Or add it to your .env file locally")
    print("\nExample:")
    print(f"export DATABASE_URL='{db_url}'")

if __name__ == "__main__":
    main()
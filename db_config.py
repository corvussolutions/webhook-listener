#!/usr/bin/env python3
"""
Database configuration and connection management
Supports both development and production environments
"""

import os
import psycopg2
from psycopg2 import pool
from urllib.parse import urlparse
import logging

logger = logging.getLogger(__name__)

class DatabaseConfig:
    """Manages database configuration and connection pooling"""
    
    _instance = None
    _connection_pool = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabaseConfig, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.initialized = True
            self.database_url = self._get_database_url()
            self._init_connection_pool()
    
    def _get_database_url(self):
        """Get database URL from various sources"""
        
        # 1. Try DATABASE_URL (Render standard)
        db_url = os.environ.get('DATABASE_URL')
        if db_url:
            return db_url
        
        # 2. Try RENDER_DATABASE_URL (custom for shared DB)
        db_url = os.environ.get('RENDER_DATABASE_URL')
        if db_url:
            return db_url
        
        # 3. Try local .env file
        if os.path.exists('.env'):
            try:
                with open('.env', 'r') as f:
                    for line in f:
                        if line.startswith('DATABASE_URL='):
                            return line.strip().split('=', 1)[1]
                        if line.startswith('RENDER_DATABASE_URL='):
                            return line.strip().split('=', 1)[1]
            except Exception:
                pass
        
        # 4. Try webhook config file (for compatibility)
        config_file = os.path.join(os.path.dirname(__file__), '..', 'src', 'unified', 'webhook_config.txt')
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r') as f:
                    db_url = f.read().strip()
                    if db_url:
                        return db_url
            except Exception:
                pass
        
        return None
    
    def _init_connection_pool(self):
        """Initialize connection pool for better performance"""
        if not self.database_url:
            logger.warning("No database URL configured")
            return
        
        try:
            parsed = urlparse(self.database_url)
            
            # Create connection pool
            self._connection_pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=1,
                maxconn=10,
                host=parsed.hostname,
                database=parsed.path[1:],
                user=parsed.username,
                password=parsed.password,
                port=parsed.port or 5432
            )
            logger.info("Database connection pool initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize connection pool: {e}")
            self._connection_pool = None
    
    def get_connection(self):
        """Get a connection from the pool"""
        if not self._connection_pool:
            raise ValueError("Database connection pool not initialized")
        
        return self._connection_pool.getconn()
    
    def return_connection(self, conn):
        """Return a connection to the pool"""
        if self._connection_pool and conn:
            self._connection_pool.putconn(conn)
    
    def close_all_connections(self):
        """Close all connections in the pool"""
        if self._connection_pool:
            self._connection_pool.closeall()
            logger.info("All database connections closed")
    
    @property
    def is_configured(self):
        """Check if database is configured"""
        return self.database_url is not None
    
    def get_connection_info(self):
        """Get connection information for debugging"""
        if not self.database_url:
            return {"configured": False}
        
        parsed = urlparse(self.database_url)
        return {
            "configured": True,
            "host": parsed.hostname,
            "port": parsed.port or 5432,
            "database": parsed.path[1:],
            "user": parsed.username,
            "pool_size": self._connection_pool.maxconn if self._connection_pool else 0
        }


# Singleton instance
db_config = DatabaseConfig()


def get_db_connection():
    """Get a database connection (for backward compatibility)"""
    return db_config.get_connection()


def return_db_connection(conn):
    """Return a database connection (for backward compatibility)"""
    db_config.return_connection(conn)


def test_database_connection():
    """Test database connectivity"""
    try:
        conn = db_config.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        cursor.close()
        db_config.return_connection(conn)
        return True
    except Exception as e:
        logger.error(f"Database connection test failed: {e}")
        return False


if __name__ == "__main__":
    # Test configuration
    print("Database Configuration Test")
    print("-" * 40)
    
    info = db_config.get_connection_info()
    for key, value in info.items():
        print(f"{key}: {value}")
    
    if db_config.is_configured:
        print("\nTesting connection...")
        if test_database_connection():
            print("✅ Connection successful")
        else:
            print("❌ Connection failed")
    else:
        print("\n⚠️  No database URL configured")
        print("Set DATABASE_URL or RENDER_DATABASE_URL environment variable")
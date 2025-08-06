#!/usr/bin/env python3
"""
Test PostgreSQL connection and basic operations
"""

import os
import sys
import json
from datetime import datetime
from db_config import db_config, test_database_connection

def test_webhook_operations():
    """Test webhook database operations"""
    
    print("\n=== Testing Webhook Database Operations ===\n")
    
    # Test connection
    print("1. Testing database connection...")
    if not test_database_connection():
        print("❌ Database connection failed")
        return False
    print("✅ Database connection successful")
    
    # Test data insertion
    print("\n2. Testing data insertion...")
    test_data = {
        "name": "Test User",
        "email": "test@example.com",
        "title": "Software Engineer",
        "company": "Test Company",
        "location": "San Francisco, CA",
        "linkedin_url": "https://linkedin.com/in/testuser",
        "website": "https://example.com"
    }
    
    try:
        conn = db_config.get_connection()
        cursor = conn.cursor()
        
        # Insert test webhook log
        cursor.execute("""
            INSERT INTO webhook_logs (event_type, contact_email, webhook_data)
            VALUES (%s, %s, %s)
            RETURNING log_id
        """, ('test_event', test_data['email'], json.dumps(test_data)))
        
        log_id = cursor.fetchone()[0]
        print(f"✅ Created webhook log with ID: {log_id}")
        
        # Insert test contact
        cursor.execute("""
            INSERT INTO linkedin_contacts 
            (name, title, company, location, email, linkedin_url, website, raw_json)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (email) DO UPDATE SET
                updated_at = CURRENT_TIMESTAMP
            RETURNING id, (xmax = 0) AS inserted
        """, (
            test_data['name'],
            test_data['title'],
            test_data['company'],
            test_data['location'],
            test_data['email'],
            test_data['linkedin_url'],
            test_data['website'],
            json.dumps(test_data)
        ))
        
        contact_id, was_inserted = cursor.fetchone()
        action = "created" if was_inserted else "updated"
        print(f"✅ Contact {action} with ID: {contact_id}")
        
        conn.commit()
        
    except Exception as e:
        print(f"❌ Data insertion failed: {e}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        db_config.return_connection(conn)
    
    # Test data retrieval
    print("\n3. Testing data retrieval...")
    try:
        conn = db_config.get_connection()
        cursor = conn.cursor()
        
        # Count contacts
        cursor.execute("SELECT COUNT(*) FROM linkedin_contacts")
        count = cursor.fetchone()[0]
        print(f"✅ Found {count} contacts in database")
        
        # Get recent logs
        cursor.execute("""
            SELECT COUNT(*) FROM webhook_logs 
            WHERE received_at > CURRENT_TIMESTAMP - INTERVAL '1 hour'
        """)
        recent_logs = cursor.fetchone()[0]
        print(f"✅ Found {recent_logs} recent webhook logs")
        
        # Test cleanup - remove test data
        cursor.execute("DELETE FROM linkedin_contacts WHERE email = %s", (test_data['email'],))
        cursor.execute("DELETE FROM webhook_logs WHERE contact_email = %s", (test_data['email'],))
        
        conn.commit()
        print("✅ Test data cleaned up")
        
    except Exception as e:
        print(f"❌ Data retrieval failed: {e}")
        return False
    finally:
        cursor.close()
        db_config.return_connection(conn)
    
    print("\n✅ All tests passed!")
    return True

def show_connection_info():
    """Display connection information"""
    print("\n=== Database Connection Information ===\n")
    
    info = db_config.get_connection_info()
    
    if not info.get('configured'):
        print("❌ No database configured")
        print("\nTo configure the database:")
        print("1. Set DATABASE_URL environment variable")
        print("2. Or set RENDER_DATABASE_URL environment variable")
        print("3. Or create a .env file with DATABASE_URL=...")
        return
    
    print(f"Host: {info['host']}")
    print(f"Port: {info['port']}")
    print(f"Database: {info['database']}")
    print(f"User: {info['user']}")
    print(f"Pool Size: {info['pool_size']}")

def main():
    """Main test function"""
    
    print("PostgreSQL Webhook Listener Test Suite")
    print("=" * 40)
    
    # Show connection info
    show_connection_info()
    
    if not db_config.is_configured:
        print("\n⚠️  Cannot run tests without database configuration")
        sys.exit(1)
    
    # Run tests
    if test_webhook_operations():
        print("\n✅ All tests completed successfully")
        print("\nYour webhook listener is ready to use PostgreSQL!")
        print("\nNext steps:")
        print("1. Set DATABASE_URL in your Render environment variables")
        print("2. Deploy using: git push")
        print("3. The database will be initialized automatically on first run")
    else:
        print("\n❌ Some tests failed")
        sys.exit(1)

if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
Professional webhook listener with PostgreSQL backend
Designed for persistent storage on Render's managed PostgreSQL
"""

import os
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from datetime import datetime
from urllib.parse import urlparse
import logging
import tempfile

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Database connection configuration
DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    logger.warning("DATABASE_URL not set, some features may not work")

def get_db_connection():
    """Create a new database connection using connection pooling best practices"""
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL environment variable is required")
    
    # Parse the database URL
    parsed = urlparse(DATABASE_URL)
    
    try:
        conn = psycopg2.connect(
            host=parsed.hostname,
            database=parsed.path[1:],  # Remove leading slash
            user=parsed.username,
            password=parsed.password,
            port=parsed.port or 5432,
            # Connection pooling settings
            connect_timeout=10,
            options='-c statement_timeout=30000'  # 30 second statement timeout
        )
        return conn
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        raise

def init_database():
    """Initialize database tables if they don't exist"""
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if tables already exist before trying to create
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'linkedin_contacts'
            )
        """)
        
        tables_exist = cursor.fetchone()[0]
        if tables_exist:
            logger.info("Database tables already exist - running migrations")
        else:
            logger.info("Creating new database tables")
        
        # Create linkedin_contacts table with proper indexes
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS linkedin_contacts (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255),
                title VARCHAR(500),
                company VARCHAR(255),
                location VARCHAR(255),
                email VARCHAR(255),
                linkedin_url VARCHAR(500),
                website VARCHAR(500),
                profile_data TEXT,
                raw_json JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Add constraints if they don't exist (for existing deployments)
        try:
            cursor.execute("""
                DO $$ 
                BEGIN
                    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'unique_email') THEN
                        ALTER TABLE linkedin_contacts ADD CONSTRAINT unique_email UNIQUE(email) DEFERRABLE INITIALLY DEFERRED;
                    END IF;
                    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'unique_linkedin_url') THEN
                        ALTER TABLE linkedin_contacts ADD CONSTRAINT unique_linkedin_url UNIQUE(linkedin_url) DEFERRABLE INITIALLY DEFERRED;
                    END IF;
                END $$;
            """)
        except Exception as constraint_error:
            logger.info(f"Constraint addition note: {constraint_error}")
            # Continue - constraints may already exist or conflict
        
        # Create indexes for better query performance
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_linkedin_contacts_email 
            ON linkedin_contacts(email) WHERE email IS NOT NULL AND email != ''
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_linkedin_contacts_linkedin_url
            ON linkedin_contacts(linkedin_url) WHERE linkedin_url IS NOT NULL AND linkedin_url != ''
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_linkedin_contacts_company 
            ON linkedin_contacts(company)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_linkedin_contacts_created 
            ON linkedin_contacts(created_at DESC)
        """)
        
        # Create webhook_logs table for tracking all webhook activity
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
        
        # Always run migrations for webhook_logs table (even if tables exist)
        logger.info("Running webhook_logs table migrations...")
        try:
            cursor.execute("ALTER TABLE webhook_logs ADD COLUMN IF NOT EXISTS contact_name VARCHAR(255)")
            logger.info("Added contact_name column")
            cursor.execute("ALTER TABLE webhook_logs ADD COLUMN IF NOT EXISTS linkedin_url VARCHAR(500)")
            logger.info("Added linkedin_url column")
            # Try to convert contact_id to INTEGER if it's still VARCHAR
            cursor.execute("""
                DO $$ 
                BEGIN
                    IF EXISTS (SELECT 1 FROM information_schema.columns 
                              WHERE table_name='webhook_logs' AND column_name='contact_id' 
                              AND data_type='character varying') THEN
                        ALTER TABLE webhook_logs ALTER COLUMN contact_id TYPE INTEGER USING 
                            CASE WHEN contact_id ~ '^[0-9]+$' THEN contact_id::INTEGER ELSE NULL END;
                        RAISE NOTICE 'Converted contact_id to INTEGER';
                    END IF;
                END $$;
            """)
            logger.info("Checked contact_id type conversion")
        except Exception as alter_error:
            logger.error(f"Schema alteration error: {alter_error}")
            # Continue - may be type conversion issues on existing data
        
        # Create index for webhook logs
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_webhook_logs_received 
            ON webhook_logs(received_at DESC)
        """)
        
        # Create a function to update the updated_at timestamp
        cursor.execute("""
            CREATE OR REPLACE FUNCTION update_updated_at_column()
            RETURNS TRIGGER AS $$
            BEGIN
                NEW.updated_at = CURRENT_TIMESTAMP;
                RETURN NEW;
            END;
            $$ language 'plpgsql';
        """)
        
        # Create trigger for auto-updating updated_at
        cursor.execute("""
            DROP TRIGGER IF EXISTS update_linkedin_contacts_updated_at ON linkedin_contacts;
            CREATE TRIGGER update_linkedin_contacts_updated_at 
            BEFORE UPDATE ON linkedin_contacts 
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
        """)
        
        conn.commit()
        logger.info("Database tables initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/')
def index():
    """Health check and status endpoint"""
    try:
        # First try to initialize database if needed
        init_database()
    except Exception as e:
        logger.warning(f"Database initialization during health check: {e}")
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get contact count
        cursor.execute("SELECT COUNT(*) FROM linkedin_contacts")
        contact_count = cursor.fetchone()[0]
        
        # Get recent webhook count
        cursor.execute("""
            SELECT COUNT(*) FROM webhook_logs 
            WHERE received_at > CURRENT_TIMESTAMP - INTERVAL '24 hours'
        """)
        recent_webhooks = cursor.fetchone()[0]
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'status': 'healthy',
            'service': 'LinkedIn Webhook Listener (PostgreSQL)',
            'total_contacts': contact_count,
            'webhooks_last_24h': recent_webhooks,
            'database': 'connected'
        })
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        # Return a degraded status instead of error
        return jsonify({
            'status': 'initializing',
            'message': 'Database tables are being created. Please try again in a moment.',
            'database': 'initializing',
            'error_detail': str(e)
        }), 503

@app.route('/webhook', methods=['POST'])
def webhook():
    """Main webhook endpoint for receiving LinkedIn data"""
    try:
        data = request.get_json()
        logger.info(f"Received webhook data: {data}")
        
        if not data:
            logger.error("No JSON data provided in webhook request")
            return jsonify({'error': 'No data provided'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Log the webhook event (extract details for logging)
        contact_info = data.get('contactInfo', {})
        log_email = contact_info.get('email', '') if contact_info else ''
        log_name = data.get('name', '')
        log_linkedin = contact_info.get('linkedinUrl', '') if contact_info else data.get('profileUrl', '')
        
        cursor.execute("""
            INSERT INTO webhook_logs (event_type, contact_email, contact_name, linkedin_url, webhook_data)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING log_id
        """, (
            'linkedin_data',
            log_email,
            log_name,
            log_linkedin,
            json.dumps(data)
        ))
        log_id = cursor.fetchone()[0]
        logger.info(f"Created webhook log with ID: {log_id}")
        
        # Extract contact information from new data structure
        name = data.get('name', '')
        contact_info = data.get('contactInfo', {})
        email = contact_info.get('email', '') if contact_info else ''
        linkedin_url = contact_info.get('linkedinUrl', '') if contact_info else data.get('profileUrl', '')
        
        # Extract websites
        websites = contact_info.get('websites', []) if contact_info else []
        website = websites[0]['url'] if websites else ''
        
        logger.info(f"Processing contact - Name: {name}, Email: {email}, LinkedIn: {linkedin_url}")
        
        # Use email if available, otherwise use LinkedIn URL as unique identifier
        unique_identifier = email if email else linkedin_url
        
        if not unique_identifier:
            conn.commit()
            logger.warning(f"Skipping contact - no email or LinkedIn URL. Data keys: {list(data.keys())}")
            return jsonify({
                'status': 'skipped',
                'message': 'No email or LinkedIn URL provided',
                'log_id': log_id,
                'data_keys': list(data.keys())
            }), 200
        
        # Smart upsert: match by email if available, otherwise by LinkedIn URL
        if email:
            # Try to find existing record by email first
            cursor.execute("""
                INSERT INTO linkedin_contacts 
                (name, title, company, location, email, linkedin_url, website, profile_data, raw_json)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (email) DO UPDATE SET
                    name = EXCLUDED.name,
                    title = EXCLUDED.title,
                    company = EXCLUDED.company,
                    location = EXCLUDED.location,
                    linkedin_url = EXCLUDED.linkedin_url,
                    website = EXCLUDED.website,
                    profile_data = EXCLUDED.profile_data,
                    raw_json = EXCLUDED.raw_json,
                    updated_at = CURRENT_TIMESTAMP
                RETURNING id, (xmax = 0) AS inserted
            """, (
                name,
                data.get('title', ''),
                data.get('company', ''),
                data.get('location', ''),
                email,
                linkedin_url,
                website,
                data.get('profile_data', ''),
                json.dumps(data)
            ))
        else:
            # No email, use LinkedIn URL for matching
            cursor.execute("""
                INSERT INTO linkedin_contacts 
                (name, title, company, location, email, linkedin_url, website, profile_data, raw_json)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (linkedin_url) DO UPDATE SET
                    name = EXCLUDED.name,
                    title = EXCLUDED.title,
                    company = EXCLUDED.company,
                    location = EXCLUDED.location,
                    email = CASE 
                        WHEN EXCLUDED.email != '' THEN EXCLUDED.email 
                        ELSE linkedin_contacts.email 
                    END,
                    website = EXCLUDED.website,
                    profile_data = EXCLUDED.profile_data,
                    raw_json = EXCLUDED.raw_json,
                    updated_at = CURRENT_TIMESTAMP
                RETURNING id, (xmax = 0) AS inserted
            """, (
                name,
                data.get('title', ''),
                data.get('company', ''),
                data.get('location', ''),
                email or None,  # Allow NULL emails
                linkedin_url,
                website,
                data.get('profile_data', ''),
                json.dumps(data)
            ))
        
        result = cursor.fetchone()
        contact_id = result[0]
        was_inserted = result[1]
        logger.info(f"Database operation completed - Contact ID: {contact_id}, Inserted: {was_inserted}")
        
        # Mark webhook as processed with contact_id
        cursor.execute("""
            UPDATE webhook_logs 
            SET processed = TRUE, 
                contact_id = %s,
                processing_notes = %s
            WHERE log_id = %s
        """, (
            contact_id,
            f"Contact {'created' if was_inserted else 'updated'} with ID {contact_id} (matched by {'email' if email else 'LinkedIn URL'})",
            log_id
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        logger.info(f"{'Created' if was_inserted else 'Updated'} contact: {name} (matched by {'email' if email else 'LinkedIn URL'})")
        
        return jsonify({
            'status': 'success',
            'action': 'created' if was_inserted else 'updated',
            'contact_id': contact_id,
            'name': name,
            'email': email,
            'linkedin_url': linkedin_url,
            'matched_by': 'email' if email else 'linkedin_url',
            'log_id': log_id
        }), 201 if was_inserted else 200
        
    except Exception as e:
        logger.error(f"Webhook processing error: {e}", exc_info=True)
        try:
            if 'conn' in locals() and conn:
                conn.rollback()
        except:
            pass
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/export', methods=['GET'])
def export():
    """Export all contacts as JSON"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute("""
            SELECT id, name, title, company, location, email, 
                   linkedin_url, website, profile_data, 
                   created_at, updated_at
            FROM linkedin_contacts
            ORDER BY created_at DESC
        """)
        
        contacts = cursor.fetchall()
        
        # Convert datetime objects to strings
        for contact in contacts:
            if contact['created_at']:
                contact['created_at'] = contact['created_at'].isoformat()
            if contact['updated_at']:
                contact['updated_at'] = contact['updated_at'].isoformat()
        
        cursor.close()
        conn.close()
        
        # Create temporary file for download
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(contacts, f, indent=2)
            temp_filename = f.name
        
        return send_file(
            temp_filename,
            mimetype='application/json',
            as_attachment=True,
            download_name=f'linkedin_contacts_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        )
        
    except Exception as e:
        logger.error(f"Export error: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/stats', methods=['GET'])
def stats():
    """Get detailed statistics about collected data"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Overall statistics
        cursor.execute("""
            SELECT 
                COUNT(*) as total_contacts,
                COUNT(DISTINCT company) as unique_companies,
                COUNT(DISTINCT location) as unique_locations,
                MIN(created_at) as first_contact,
                MAX(created_at) as last_contact
            FROM linkedin_contacts
        """)
        overall_stats = cursor.fetchone()
        
        # Company distribution
        cursor.execute("""
            SELECT company, COUNT(*) as count
            FROM linkedin_contacts
            WHERE company IS NOT NULL AND company != ''
            GROUP BY company
            ORDER BY count DESC
            LIMIT 10
        """)
        top_companies = cursor.fetchall()
        
        # Recent activity
        cursor.execute("""
            SELECT 
                DATE(received_at) as date,
                COUNT(*) as webhook_count
            FROM webhook_logs
            WHERE received_at > CURRENT_TIMESTAMP - INTERVAL '7 days'
            GROUP BY DATE(received_at)
            ORDER BY date DESC
        """)
        recent_activity = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        # Format dates
        if overall_stats['first_contact']:
            overall_stats['first_contact'] = overall_stats['first_contact'].isoformat()
        if overall_stats['last_contact']:
            overall_stats['last_contact'] = overall_stats['last_contact'].isoformat()
        
        for activity in recent_activity:
            activity['date'] = activity['date'].isoformat()
        
        return jsonify({
            'overall': overall_stats,
            'top_companies': top_companies,
            'recent_activity': recent_activity
        })
        
    except Exception as e:
        logger.error(f"Stats error: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/webhook/health', methods=['GET'])
def webhook_health():
    """Health check endpoint specifically for webhook functionality"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Test database connectivity
        cursor.execute("SELECT 1")
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'status': 'healthy',
            'database': 'connected',
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Webhook health check failed: {e}")
        return jsonify({
            'status': 'unhealthy',
            'database': 'error',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/webhook/logs', methods=['GET'])
def webhook_logs():
    """View recent webhook logs"""
    try:
        limit = request.args.get('limit', 50, type=int)
        
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute("""
            SELECT log_id, event_type, contact_email, contact_id, contact_name,
                   linkedin_url, received_at, processed, processing_notes
            FROM webhook_logs
            ORDER BY received_at DESC
            LIMIT %s
        """, (limit,))
        
        logs = cursor.fetchall()
        
        # Format dates
        for log in logs:
            if log['received_at']:
                log['received_at'] = log['received_at'].isoformat()
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'count': len(logs),
            'logs': logs
        })
        
    except Exception as e:
        logger.error(f"Webhook logs error: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

# Initialize database on startup (with singleton pattern)
_db_initialized = False
_init_lock = False

def ensure_db_initialized():
    """Ensure database is initialized only once"""
    global _db_initialized, _init_lock
    
    if _db_initialized:
        return
    
    # Simple lock to prevent multiple workers from initializing
    if _init_lock:
        import time
        time.sleep(2)  # Wait for other worker to finish
        return
    
    _init_lock = True
    try:
        logger.info("Initializing database tables...")
        init_database()
        _db_initialized = True
        logger.info("Database initialization complete")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
    finally:
        _init_lock = False

# Initialize on startup
ensure_db_initialized()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
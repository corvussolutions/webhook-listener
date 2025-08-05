from flask import Flask, request, jsonify, send_file
import json
from datetime import datetime
import logging
import sys
import sqlite3
import os
import io

# Configure logging to ensure output goes to stdout
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

app = Flask(__name__)
logger = logging.getLogger(__name__)

# Database file path - will be created in the app directory
DB_FILE = 'linkedin_contacts.db'

# Initialize database
def init_db():
    """Create the contacts table if it doesn't exist"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS linkedin_contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            title TEXT,
            company TEXT,
            location TEXT,
            email TEXT UNIQUE,
            linkedin_url TEXT,
            website_url TEXT,
            website_text TEXT,
            profile_url TEXT,
            raw_data TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()
    logger.info("Database initialized")

# Initialize DB on startup
init_db()

# Add CORS support
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

@app.route('/', methods=['GET'])
def home():
    """Home endpoint with status info"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM linkedin_contacts")
    count = cursor.fetchone()[0]
    conn.close()
    
    return jsonify({
        "status": "running",
        "message": "LinkedIn webhook listener is active",
        "contacts_collected": count,
        "endpoints": {
            "/webhook": "POST - Receive LinkedIn contact data",
            "/export": "GET - Export all collected contacts as JSON",
            "/stats": "GET - View collection statistics",
            "/clear": "POST - Clear all collected data (requires confirmation)"
        }
    })

@app.route('/webhook', methods=['POST', 'OPTIONS'])
def webhook():
    """Receive and store LinkedIn contact data"""
    # Handle CORS preflight
    if request.method == 'OPTIONS':
        return '', 200
    
    timestamp = datetime.now()
    logger.info(f"Webhook received at {timestamp}")
    
    try:
        # Get JSON data
        data = request.get_json()
        
        if not data:
            logger.error("No JSON data received")
            return jsonify({"error": "No data received"}), 400
        
        # Extract contact info
        contact_info = data.get('contactInfo', {})
        websites = contact_info.get('websites', [])
        website_url = websites[0].get('url', '') if websites else ''
        website_text = websites[0].get('text', '') if websites else ''
        
        # Store in database
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Update if email exists, insert if new
        cursor.execute('''
            INSERT OR REPLACE INTO linkedin_contacts 
            (name, title, company, location, email, linkedin_url, 
             website_url, website_text, profile_url, raw_data, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data.get('name', ''),
            data.get('title', ''),
            data.get('company', ''),
            data.get('location', ''),
            contact_info.get('email', ''),
            contact_info.get('linkedinUrl', ''),
            website_url,
            website_text,
            data.get('profileUrl', ''),
            json.dumps(data),
            timestamp
        ))
        
        conn.commit()
        contact_id = cursor.lastrowid
        conn.close()
        
        logger.info(f"Contact saved: {data.get('name')} - {contact_info.get('email')}")
        
        return jsonify({
            "status": "success",
            "message": "Contact saved",
            "contact_id": contact_id,
            "timestamp": timestamp.isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/export', methods=['GET'])
def export():
    """Export all collected contacts as JSON"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT name, title, company, location, email, linkedin_url,
                   website_url, profile_url, created_at, updated_at
            FROM linkedin_contacts
            ORDER BY updated_at DESC
        ''')
        
        columns = [desc[0] for desc in cursor.description]
        contacts = []
        
        for row in cursor.fetchall():
            contact = dict(zip(columns, row))
            contacts.append(contact)
        
        conn.close()
        
        # Create JSON response
        export_data = {
            "export_timestamp": datetime.now().isoformat(),
            "total_contacts": len(contacts),
            "contacts": contacts
        }
        
        # Return as downloadable file
        output = io.BytesIO()
        output.write(json.dumps(export_data, indent=2).encode('utf-8'))
        output.seek(0)
        
        return send_file(
            output,
            mimetype='application/json',
            as_attachment=True,
            download_name=f'linkedin_contacts_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        )
        
    except Exception as e:
        logger.error(f"Error exporting contacts: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/stats', methods=['GET'])
def stats():
    """Get statistics about collected contacts"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Total contacts
        cursor.execute("SELECT COUNT(*) FROM linkedin_contacts")
        total = cursor.fetchone()[0]
        
        # Contacts by day
        cursor.execute('''
            SELECT DATE(created_at) as date, COUNT(*) as count
            FROM linkedin_contacts
            GROUP BY DATE(created_at)
            ORDER BY date DESC
            LIMIT 30
        ''')
        daily_stats = cursor.fetchall()
        
        # Recent contacts
        cursor.execute('''
            SELECT name, email, created_at
            FROM linkedin_contacts
            ORDER BY created_at DESC
            LIMIT 10
        ''')
        recent = cursor.fetchall()
        
        conn.close()
        
        return jsonify({
            "total_contacts": total,
            "daily_collection": [{"date": d[0], "count": d[1]} for d in daily_stats],
            "recent_contacts": [{"name": r[0], "email": r[1], "created_at": r[2]} for r in recent]
        })
        
    except Exception as e:
        logger.error(f"Error getting stats: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/clear', methods=['POST'])
def clear():
    """Clear all collected data (requires confirmation)"""
    data = request.get_json() or {}
    
    if data.get('confirm') != 'yes-clear-all-data':
        return jsonify({
            "error": "Confirmation required",
            "message": "Send {\"confirm\": \"yes-clear-all-data\"} to clear database"
        }), 400
    
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM linkedin_contacts")
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        
        logger.info(f"Cleared {deleted} contacts from database")
        
        return jsonify({
            "status": "success",
            "message": f"Cleared {deleted} contacts"
        })
        
    except Exception as e:
        logger.error(f"Error clearing database: {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    logger.info(f"Starting Flask app on port {port}")
    app.run(host='0.0.0.0', port=port)
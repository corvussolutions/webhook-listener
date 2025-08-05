from flask import Flask, request, jsonify
import json
from datetime import datetime
import logging
import sys

# Configure logging to ensure output goes to stdout
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

app = Flask(__name__)
logger = logging.getLogger(__name__)

# Add CORS support
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

@app.route('/', methods=['GET'])
def home():
    logger.info("Home endpoint accessed")
    return jsonify({
        "status": "running",
        "message": "Webhook listener is active",
        "endpoints": {
            "/webhook": "POST - Receive webhook data"
        }
    })

@app.route('/webhook', methods=['POST', 'OPTIONS'])
def webhook():
    # Handle CORS preflight
    if request.method == 'OPTIONS':
        logger.info("OPTIONS request received for /webhook")
        return '', 200
    # Log timestamp
    timestamp = datetime.now().isoformat()
    
    logger.info(f"POST request received at /webhook at {timestamp}")
    
    # Get request details
    headers = dict(request.headers)
    method = request.method
    url = request.url
    
    # Log basic info immediately
    logger.info(f"Method: {method}")
    logger.info(f"URL: {url}")
    logger.info(f"Content-Type: {request.content_type}")
    logger.info(f"Content-Length: {request.content_length}")
    
    # Get body data in different formats
    raw_data = request.get_data(as_text=True)
    
    # Try to parse as JSON
    json_data = None
    try:
        json_data = request.get_json()
    except:
        pass
    
    # Try to get form data
    form_data = None
    if request.form:
        form_data = dict(request.form)
    
    # Log everything
    log_data = {
        "timestamp": timestamp,
        "method": method,
        "url": url,
        "headers": headers,
        "raw_body": raw_data,
        "json_data": json_data,
        "form_data": form_data,
        "query_params": dict(request.args)
    }
    
    # Log to console (will appear in Render logs)
    logger.info("="*50)
    logger.info(f"WEBHOOK RECEIVED at {timestamp}")
    logger.info("="*50)
    logger.info(json.dumps(log_data, indent=2))
    logger.info("="*50)
    
    # Also use print with flush to ensure output
    print(f"\nWEBHOOK DATA: {json.dumps(log_data, indent=2)}", flush=True)
    
    # Return success response
    return jsonify({
        "status": "success",
        "message": "Webhook received",
        "timestamp": timestamp
    }), 200

if __name__ == '__main__':
    # Use PORT environment variable for Render
    import os
    port = int(os.environ.get('PORT', 10000))
    logger.info(f"Starting Flask app on port {port}")
    app.run(host='0.0.0.0', port=port)
from flask import Flask, request, jsonify
import json
from datetime import datetime

app = Flask(__name__)

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        "status": "running",
        "message": "Webhook listener is active",
        "endpoints": {
            "/webhook": "POST - Receive webhook data"
        }
    })

@app.route('/webhook', methods=['POST'])
def webhook():
    # Log timestamp
    timestamp = datetime.now().isoformat()
    
    # Get request details
    headers = dict(request.headers)
    method = request.method
    url = request.url
    
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
    
    # Print to console (will appear in Render logs)
    print("\n" + "="*50)
    print(f"WEBHOOK RECEIVED at {timestamp}")
    print("="*50)
    print(json.dumps(log_data, indent=2))
    print("="*50 + "\n")
    
    # Return success response
    return jsonify({
        "status": "success",
        "message": "Webhook received",
        "timestamp": timestamp
    }), 200

if __name__ == '__main__':
    # Use PORT environment variable for Render
    import os
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
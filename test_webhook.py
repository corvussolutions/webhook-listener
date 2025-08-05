#!/usr/bin/env python3
"""
Simple script to test the webhook endpoint
"""
import requests
import json

# Replace with your actual Render URL
WEBHOOK_URL = "https://webhook-listener-6qvy.onrender.com/webhook"

# Test data
test_data = {
    "event": "test",
    "timestamp": "2025-08-05T12:00:00Z",
    "data": {
        "user_id": "12345",
        "action": "page_view",
        "url": "https://example.com/page"
    }
}

print(f"Sending test webhook to: {WEBHOOK_URL}")
print(f"Data: {json.dumps(test_data, indent=2)}")

try:
    response = requests.post(
        WEBHOOK_URL,
        json=test_data,
        headers={"Content-Type": "application/json"}
    )
    
    print(f"\nResponse Status: {response.status_code}")
    print(f"Response Body: {response.text}")
    
except Exception as e:
    print(f"\nError: {e}")
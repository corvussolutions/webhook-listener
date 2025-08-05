#!/bin/bash
# Example of how to integrate LinkedIn email updates into your analytics pipeline

echo "==================================="
echo "LinkedIn Email Update Integration"
echo "==================================="

# 1. First, update LinkedIn emails from webhook data
echo "Step 1: Updating LinkedIn dummy emails with real data from webhooks..."
python3 src/unified/update_linkedin_emails.py

# Check if update was successful
if [ $? -eq 0 ]; then
    echo "✓ LinkedIn emails updated successfully"
else
    echo "✗ Failed to update LinkedIn emails"
    exit 1
fi

# 2. Then run your normal analytics pipeline
echo ""
echo "Step 2: Running full analytics pipeline..."
./src/unified/run_full_analytics_v3.sh "$@"

echo ""
echo "Integration complete!"
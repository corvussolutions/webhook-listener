# LinkedIn Webhook Integration Guide

## Overview

This system allows you to manually scrape LinkedIn profiles and update dummy email addresses in your analytics database with real contact information.

## Architecture

1. **Webhook Service (Render)**: Collects and stores LinkedIn profile data
2. **Integration Script**: Downloads collected data and updates your unified database
3. **Analytics Pipeline**: Processes data with real email addresses

## Deployment Steps

### 1. Deploy Enhanced Webhook to Render

Push the updated code with `app_v2.py` which includes:
- SQLite storage for persistent data
- Export endpoint for downloading collected contacts
- Statistics and management endpoints

### 2. Available Endpoints

- `GET /` - Status and contact count
- `POST /webhook` - Receives LinkedIn data from Chrome extension
- `GET /export` - Download all contacts as JSON
- `GET /stats` - View collection statistics
- `POST /clear` - Clear all data (requires confirmation)

### 3. Integration with Analytics Pipeline

Two options:

#### Option A: Manual Update Before Analytics
```bash
# Update LinkedIn emails first
python3 src/unified/update_linkedin_emails.py

# Then run your normal analytics
./src/unified/run_full_analytics_v3.sh
```

#### Option B: Modify Your Pipeline Script
Add this to the beginning of `run_full_analytics_v3.sh`:
```bash
# Update LinkedIn emails from webhook data
echo "Updating LinkedIn emails from webhook data..."
python3 src/unified/update_linkedin_emails.py
```

## Workflow

1. **Collect Data**: Use Chrome extension to scrape LinkedIn profiles
   - Data is automatically sent to webhook and stored

2. **Review Collection**: Check webhook status
   ```bash
   curl https://webhook-listener-6qvy.onrender.com/stats
   ```

3. **Update Database**: Run integration script
   ```bash
   # Dry run first to see what will be updated
   python3 src/unified/update_linkedin_emails.py --dry-run
   
   # Apply updates
   python3 src/unified/update_linkedin_emails.py
   ```

4. **Run Analytics**: Process with updated emails
   ```bash
   ./src/unified/run_full_analytics_v3.sh
   ```

## Features

- **Persistent Storage**: SQLite database survives deployments
- **Duplicate Prevention**: Updates existing contacts by email
- **Audit Trail**: Tracks when emails were updated from webhook
- **Backup Files**: Automatically saves downloaded data
- **Detailed Reports**: JSON report of all updates and unmatched contacts

## Environment Variables

Optional:
- `WEBHOOK_EXPORT_URL`: Override default webhook URL
- `PORT`: Set by Render automatically

## Monitoring

The integration script provides:
- Count of successful updates
- List of unmatched webhook contacts (not in your DB)
- List of unmatched dummy emails (no webhook data)
- Detailed JSON report file

## Security Note

The webhook accepts data from any source. Consider adding authentication if needed:
- API key validation
- IP whitelist
- Request signing
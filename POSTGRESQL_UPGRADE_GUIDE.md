# PostgreSQL Upgrade Guide for Webhook Listener

## Overview

This guide explains how to upgrade your webhook listener from SQLite (ephemeral) to PostgreSQL (persistent) storage on Render.

## Why Upgrade to PostgreSQL?

1. **Data Persistence**: SQLite data is lost on every Render restart/redeploy
2. **Professional Reliability**: PostgreSQL provides ACID compliance and better concurrency
3. **Shared Database**: Can use the same PostgreSQL instance as your other services
4. **Better Performance**: Connection pooling and optimized queries
5. **Scalability**: Ready for growth with proper indexes and constraints

## New Features with PostgreSQL

- **Persistent Storage**: Data survives restarts and redeployments
- **Connection Pooling**: Better performance under load
- **Webhook Logging**: All webhook events are logged for debugging
- **Auto-timestamps**: Automatic created_at and updated_at tracking
- **Better Indexes**: Optimized queries for email, company, and date searches
- **Migration Support**: Automatic migration from existing SQLite data

## Setup Instructions

### 1. Database Configuration

You have several options for providing the PostgreSQL connection URL:

#### Option A: Share Existing Database (Recommended)
If you already have a PostgreSQL database on Render:

1. Go to your existing PostgreSQL service in Render dashboard
2. Copy the "External Database URL" 
3. Add it as an environment variable to your webhook service:
   - Name: `DATABASE_URL` or `RENDER_DATABASE_URL`
   - Value: `postgresql://user:password@host:port/database`

#### Option B: Create New Database
1. In Render dashboard, create a new PostgreSQL service
2. Choose the appropriate plan (Starter or Standard)
3. Copy the connection URL once created

### 2. Environment Variables

In your webhook service settings on Render, add:

```
DATABASE_URL=postgresql://user:password@host:port/database
```

Or if sharing a database:
```
RENDER_DATABASE_URL=postgresql://user:password@host:port/database
```

### 3. Deploy the PostgreSQL Version

The service will automatically use `app_postgres.py` which includes:
- PostgreSQL connection management
- Connection pooling for performance
- Automatic database initialization
- Error handling and logging

### 4. Database Initialization

The database tables will be created automatically on first run. You can also manually initialize:

```bash
# Local testing
export DATABASE_URL="your-postgresql-url"
python3 init_db.py

# This will:
# - Create linkedin_contacts table with indexes
# - Create webhook_logs table for activity tracking
# - Set up auto-update triggers
# - Optionally migrate existing SQLite data
```

### 5. Test Your Setup

```bash
# Test locally before deploying
python3 test_postgres.py

# This will verify:
# - Database connection
# - Table creation
# - Data insertion/retrieval
# - All endpoints working
```

## Migration from SQLite

If you have existing data in SQLite:

1. The `init_db.py` script will detect your `linkedin_contacts.db` file
2. It will offer to migrate all existing contacts
3. Duplicates are handled gracefully (no data loss)

## Using the PostgreSQL Version

### API Endpoints (Same as Before)

- `GET /` - Health check with database status
- `POST /webhook` - Receive LinkedIn profile data
- `GET /export` - Export contacts as JSON
- `GET /stats` - View detailed statistics
- `GET /webhook/health` - Webhook-specific health check
- `GET /webhook/logs` - View recent webhook activity

### New Features

1. **Webhook Logging**: All incoming webhooks are logged
   ```json
   {
     "log_id": 123,
     "event_type": "linkedin_data",
     "contact_email": "user@example.com",
     "received_at": "2025-08-06T10:30:00Z",
     "processed": true
   }
   ```

2. **Better Statistics**: Enhanced `/stats` endpoint shows:
   - Total contacts and companies
   - Recent webhook activity by day
   - Top companies by contact count

3. **Automatic Timestamps**: 
   - `created_at` - When contact was first seen
   - `updated_at` - Last time contact was updated

## Integration with Analytics Pipeline

The webhook sync process remains the same:

```bash
# Update LinkedIn emails from webhook data
python3 src/unified/update_linkedin_emails.py

# The script will automatically:
# 1. Fetch data from PostgreSQL (not SQLite)
# 2. Update your local analytics database
# 3. Mark dummy emails as resolved
```

## Monitoring and Maintenance

### Check Database Health
```bash
curl https://your-service.onrender.com/webhook/health
```

### View Recent Activity
```bash
curl https://your-service.onrender.com/webhook/logs?limit=10
```

### Export All Data
```bash
curl https://your-service.onrender.com/export -o contacts_backup.json
```

## Troubleshooting

### Connection Issues
1. Verify DATABASE_URL is set correctly in Render
2. Check PostgreSQL service is running
3. Ensure network rules allow connection

### Performance Optimization
- The service uses connection pooling (1-10 connections)
- Indexes are created on email, company, and date fields
- Statement timeout is set to 30 seconds

### Logs
Check Render logs for detailed error messages:
```
[timestamp] INFO - Database tables initialized successfully
[timestamp] INFO - Created contact: user@example.com
```

## Security Considerations

1. **Connection String**: Keep your DATABASE_URL secure
2. **Network Security**: Use Render's private network if possible
3. **Data Privacy**: The webhook logs table can be cleaned periodically
4. **Access Control**: Consider adding authentication to endpoints

## Next Steps

1. Deploy the upgraded service
2. Test with a few webhook submissions
3. Verify data persistence across restarts
4. Set up regular backups if needed
5. Monitor performance and adjust connection pool if necessary

The PostgreSQL version is production-ready and will provide reliable, persistent storage for your LinkedIn webhook data.
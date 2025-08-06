# Fix Deployment Instructions

## Changes Made
1. Created `app_postgres_fixed.py` - handles missing processing_notes column gracefully
2. Updated `render.yaml` to use the fixed app
3. Fixed schema initialization to add missing column automatically

## To Deploy
1. Copy these files to your git repository connected to Render
2. Commit and push:
   ```bash
   git add .
   git commit -m "Fix webhook processing - handle missing processing_notes column"
   git push
   ```

## What the Fix Does
- **Auto-fixes schema**: Adds missing `processing_notes` column during initialization
- **Graceful degradation**: `/webhook/logs` endpoint works with or without the column
- **Better error handling**: Webhooks will process successfully even if schema was incomplete
- **Manual fix endpoint**: `POST /fix-schema` to manually add the missing column

## Expected Results After Deploy
- Webhooks will start processing successfully
- Contacts will be stored in the database
- Export endpoint will return actual contact data
- All 829+ pending webhooks should be processable

## Test After Deploy
```bash
# Check status (should show contacts > 0 after new LinkedIn data comes in)
curl https://webhook-listener-6qvy.onrender.com/ | jq

# Test webhook logs (should work without error)
curl "https://webhook-listener-6qvy.onrender.com/webhook/logs?limit=5" | jq

# Check stats
curl https://webhook-listener-6qvy.onrender.com/stats | jq
```
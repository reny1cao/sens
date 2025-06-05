#!/bin/bash
# Setup daily financial data update cron job

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

echo "Setting up daily financial data update cron job..."
echo "Project root: $PROJECT_ROOT"

# Create log directory
mkdir -p "$PROJECT_ROOT/logs"

# Create cron script that handles environment
cat > "$PROJECT_ROOT/scripts/cron_daily_update.sh" << EOF
#!/bin/bash
# Cron wrapper for daily financial update

cd "$PROJECT_ROOT"

# Log file with date
LOG_FILE="$PROJECT_ROOT/logs/financial_update_\$(date +%Y%m%d).log"

echo "Starting daily update at \$(date)" >> "\$LOG_FILE"

# Run the update with poetry
/usr/local/bin/poetry run python scripts/daily_financial_update.py >> "\$LOG_FILE" 2>&1

echo "Update completed at \$(date)" >> "\$LOG_FILE"
echo "" >> "\$LOG_FILE"

# Keep only last 7 days of logs
find "$PROJECT_ROOT/logs" -name "financial_update_*.log" -mtime +7 -delete
EOF

chmod +x "$PROJECT_ROOT/scripts/cron_daily_update.sh"

# Add to crontab (runs at 6:30 PM ET / 10:30 PM UTC daily)
# This is after market close to get end-of-day data
CRON_JOB="30 22 * * * $PROJECT_ROOT/scripts/cron_daily_update.sh"

# Check if cron job already exists
if crontab -l 2>/dev/null | grep -q "cron_daily_update.sh"; then
    echo "Cron job already exists. Updating..."
    # Remove old job and add new one
    (crontab -l 2>/dev/null | grep -v "cron_daily_update.sh"; echo "$CRON_JOB") | crontab -
else
    echo "Adding new cron job..."
    (crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -
fi

echo "Cron job set up successfully!"
echo "Daily updates will run at 10:30 PM UTC (6:30 PM ET)"
echo ""
echo "To view cron jobs: crontab -l"
echo "To view logs: tail -f $PROJECT_ROOT/logs/financial_update_*.log"
echo "To run manually: poetry run python scripts/daily_financial_update.py"
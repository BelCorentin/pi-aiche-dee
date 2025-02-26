#!/bin/bash

# Define script paths
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PIPELINE_SCRIPT="$SCRIPT_DIR/pipeline.py"

# Make sure the pipeline script is executable
chmod +x "$PIPELINE_SCRIPT"

# Create a temporary crontab file
TEMP_CRONTAB=$(mktemp)

# Export current crontab
crontab -l > "$TEMP_CRONTAB" 2>/dev/null || echo "# MNE Pipeline Crontab" > "$TEMP_CRONTAB"

# Check if entry already exists
if grep -q "$PIPELINE_SCRIPT" "$TEMP_CRONTAB"; then
    echo "Cron job already exists for MNE Pipeline."
else
    # Add new cron job to run daily at 8pm
    echo "0 20 * * * $PIPELINE_SCRIPT >> $SCRIPT_DIR/cron_output.log 2>&1" >> "$TEMP_CRONTAB"
    echo "# MNE Pipeline added $(date)" >> "$TEMP_CRONTAB"
    
    # Install new crontab
    crontab "$TEMP_CRONTAB"
    echo "Cron job installed to run MNE Pipeline daily at 8pm."
fi

# Clean up
rm "$TEMP_CRONTAB"

echo "Crontab setup complete!"
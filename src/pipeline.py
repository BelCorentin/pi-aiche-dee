#!/usr/bin/env python3
import os
import subprocess
from datetime import datetime
import argparse
import traceback
import time

# Import the functions from the previous scripts
from sync_org import (
    sync_figures_from_cluster, organize_figures, logger
)
from gen_report import (
    generate_mne_report, update_github_website, send_email_notification
)

# Constants for messages
STEP_SEPARATOR = "\n=== {step} ==="
PIPELINE_STEPS = {
    "SYNC": "Step 1: Syncing and organizing figures",
    "REPORT": "Step 2: Generating MNE report",
    "WEBSITE": "Step 3: Updating GitHub website"
}

# Error message templates
ERROR_MESSAGES = {
    "sync_failed": "Figure sync failed, aborting pipeline",
    "organization_failed": "Figure organization failed, aborting pipeline",
    "report_failed": "Report generation failed, aborting pipeline",
    "website_failed": "GitHub website update failed",
    "unhandled_error": "Unhandled error in pipeline: {error}"
}

# Email templates
EMAIL_SUBJECTS = {
    "sync_failed": "MNE Pipeline Failed at Sync Step",
    "organization_failed": "MNE Pipeline Failed at Organization Step",
    "unhandled_error": "MNE Pipeline Failed with Unhandled Error"
}

EMAIL_BODIES = {
    "sync_failed": "The pipeline failed during the figure sync step. "
                   "Please check the logs for details.",
    "organization_failed": "The pipeline failed during the figure organization step. "
                           "Please check the logs for details.",
    "unhandled_error": "The pipeline encountered an unhandled error: {error}\n\n{traceback}"
}

# Success messages
SUCCESS_MESSAGES = {
    "pipeline_completed": "\nPipeline completed successfully in {time:.2f} seconds",
    "report_available": "Report available at: {path}",
    "website_updated": "GitHub website updated with the new report"
}

# Error messages
FAILURE_MESSAGES = {
    "pipeline_failed": "\nPipeline completed with errors in {time:.2f} seconds"
}


def run_pipeline(custom_date=None, days_threshold=7):
    """Run the complete MNE report pipeline"""
    start_time = time.time()
    success = True
    logger.info(
        f"Starting MNE report pipeline at "
        f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    
    try:
        # Step 1: Sync and organize figures
        logger.info(STEP_SEPARATOR.format(step=PIPELINE_STEPS["SYNC"]))
        if not sync_figures_from_cluster():
            logger.error(ERROR_MESSAGES["sync_failed"])
            send_email_notification(
                subject=EMAIL_SUBJECTS["sync_failed"],
                body=EMAIL_BODIES["sync_failed"],
                success=False
            )
            return False
        
        if not organize_figures(days_threshold):
            logger.error(ERROR_MESSAGES["organization_failed"])
            send_email_notification(
                subject=EMAIL_SUBJECTS["organization_failed"],
                body=EMAIL_BODIES["organization_failed"],
                success=False
            )
            return False
        
        # Step 2: Generate MNE report
        logger.info(STEP_SEPARATOR.format(step=PIPELINE_STEPS["REPORT"]))
        report_path, date = generate_mne_report(custom_date)
        if not report_path:
            logger.error(ERROR_MESSAGES["report_failed"])
            return False
        
        # Step 3: Update GitHub website
        logger.info(STEP_SEPARATOR.format(step=PIPELINE_STEPS["WEBSITE"]))
        if not update_github_website(report_path, date):
            logger.error(ERROR_MESSAGES["website_failed"])
            success = False
    
    except Exception as e:
        success = False
        error_msg = ERROR_MESSAGES["unhandled_error"].format(error=str(e))
        logger.error(error_msg)
        logger.error(traceback.format_exc())
        
        email_body = EMAIL_BODIES["unhandled_error"].format(
            error=str(e), 
            traceback=traceback.format_exc()
        )
        send_email_notification(
            subject=EMAIL_SUBJECTS["unhandled_error"],
            body=email_body,
            success=False
        )
    
    # Calculate execution time
    execution_time = time.time() - start_time
    
    if success:
        logger.info(SUCCESS_MESSAGES["pipeline_completed"].format(time=execution_time))
        logger.info(SUCCESS_MESSAGES["report_available"].format(path=report_path))
        logger.info(SUCCESS_MESSAGES["website_updated"])
    else:
        logger.error(FAILURE_MESSAGES["pipeline_failed"].format(time=execution_time))
    
    return success


def setup_cron_job():
    """Set up a cron job to run this pipeline automatically"""
    try:
        # Path to this script
        script_path = os.path.abspath(__file__)
        
        # Check if cron job already exists
        current_crontab = subprocess.check_output(
            ['crontab', '-l'], text=True, stderr=subprocess.DEVNULL
        )
        if script_path in current_crontab:
            logger.info("Cron job already exists for this script")
            return True
            
        # Set up cron job to run daily at 8pm
        cron_job = f"0 20 * * * {script_path}\n"
        new_crontab = current_crontab + cron_job
        
        # Write to temp file
        temp_file = '/tmp/mne_pipeline_crontab'
        with open(temp_file, 'w') as f:
            f.write(new_crontab)
        
        # Install new crontab
        subprocess.run(['crontab', temp_file], check=True)
        os.remove(temp_file)
        
        logger.info("Cron job set up to run daily at 8pm")
        return True
    except Exception as e:
        logger.error(f"Failed to set up cron job: {str(e)}")
        return False


if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='MNE Report Pipeline')
    parser.add_argument(
        '--setup-cron', action='store_true',
        help='Setup a cron job to run this pipeline daily'
    )
    parser.add_argument(
        '--force', action='store_true',
        help='Force run even if no new figures'
    )
    parser.add_argument(
        '--date', type=str,
        help='Custom date for the report in YYYY-MM-DD format'
    )
    parser.add_argument(
        '--days', type=int, default=7,
        help='Number of days to consider files as recent (default: 7)'
    )
    args = parser.parse_args()
    
    if args.setup_cron:
        setup_cron_job()
    else:
        # Convert date string to date object if provided
        custom_date = None
        if args.date:
            try:
                custom_date = datetime.strptime(args.date, '%Y-%m-%d').date()
                logger.info(f"Using custom date: {custom_date}")
            except ValueError:
                logger.error(
                    f"Invalid date format: {args.date}. Using current date."
                )
        
        logger.info(
            f"Considering files from the last {args.days} days as recent"
        )
        run_pipeline(custom_date, args.days)
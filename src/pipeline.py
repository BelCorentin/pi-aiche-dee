#!/usr/bin/env python3
import os
import sys
import subprocess
from datetime import datetime
import argparse
import logging
import traceback
import time

# Import the functions from the previous scripts
from sync_org import sync_figures_from_cluster, organize_figures, logger
from gen_report import generate_mne_report, update_github_website, send_email_notification

def run_pipeline():
    """Run the complete MNE report pipeline"""
    start_time = time.time()
    success = True
    logger.info(f"Starting MNE report pipeline at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # Step 1: Sync and organize figures
        logger.info("\n=== Step 1: Syncing and organizing figures ===")
        if not sync_figures_from_cluster():
            logger.error("Figure sync failed, aborting pipeline")
            send_email_notification(
                subject="MNE Pipeline Failed at Sync Step",
                body="The pipeline failed during the figure sync step. Please check the logs for details.",
                success=False
            )
            return False
        
        if not organize_figures():
            logger.error("Figure organization failed, aborting pipeline")
            send_email_notification(
                subject="MNE Pipeline Failed at Organization Step",
                body="The pipeline failed during the figure organization step. Please check the logs for details.",
                success=False
            )
            return False
        
        # Step 2: Generate MNE report
        logger.info("\n=== Step 2: Generating MNE report ===")
        report_path, date = generate_mne_report()
        if not report_path:
            logger.error("Report generation failed, aborting pipeline")
            return False
        
        # Step 3: Update GitHub website
        logger.info("\n=== Step 3: Updating GitHub website ===")
        if not update_github_website(report_path, date):
            logger.error("GitHub website update failed")
            success = False
    
    except Exception as e:
        success = False
        logger.error(f"Unhandled error in pipeline: {str(e)}")
        logger.error(traceback.format_exc())
        send_email_notification(
            subject="MNE Pipeline Failed with Unhandled Error",
            body=f"The pipeline encountered an unhandled error: {str(e)}\n\n{traceback.format_exc()}",
            success=False
        )
    
    # Calculate execution time
    execution_time = time.time() - start_time
    
    if success:
        logger.info(f"\nPipeline completed successfully in {execution_time:.2f} seconds")
        logger.info(f"Report available at: {report_path}")
        logger.info(f"GitHub website updated with the new report")
    else:
        logger.error(f"\nPipeline completed with errors in {execution_time:.2f} seconds")
    
    return success

def setup_cron_job():
    """Set up a cron job to run this pipeline automatically"""
    try:
        # Path to this script
        script_path = os.path.abspath(__file__)
        
        # Check if cron job already exists
        current_crontab = subprocess.check_output(['crontab', '-l'], text=True, stderr=subprocess.DEVNULL)
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
    parser.add_argument('--setup-cron', action='store_true', help='Setup a cron job to run this pipeline daily')
    parser.add_argument('--force', action='store_true', help='Force run even if no new figures')
    args = parser.parse_args()
    
    if args.setup_cron:
        setup_cron_job()
    else:
        run_pipeline()
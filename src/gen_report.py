#!/usr/bin/env python3
import os
import mne
from datetime import datetime
import glob
import shutil
import json
import logging
import traceback
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
import subprocess

# Import logging config
from sync_org import logger

# Configuration
LOCAL_FIG_PATH = "/home/co/data/mne_reports/figures/"
LOCAL_REPORT_PATH = "/home/co/data/mne_reports/"
GITHUB_REPO_PATH = "/home/co/git/pi-aiche-dee/"
GITHUB_FILES_PATH = os.path.join(GITHUB_REPO_PATH, "files")
METADATA_FILE = os.path.join(LOCAL_FIG_PATH, "metadata.json")

# Email configuration
EMAIL_CONFIG = {
    'enabled': True,
    'sender': 'corentiinbel@gmail.com',
    'password': os.getenv('EMAIL_PASSWORD'),  # Use environment variable for password
    'recipients': ['corentin.bel@protonmail.com'],
    'smtp_server': 'smtp.gmail.com',
    'smtp_port': 587
}

def read_metadata():
    """Read the metadata database"""
    try:
        if os.path.exists(METADATA_FILE):
            with open(METADATA_FILE, 'r') as f:
                return json.load(f)
        else:
            logger.warning("Metadata file not found")
            return {}
    except Exception as e:
        logger.error(f"Error reading metadata: {str(e)}")
        return {}

def get_section_title(category_path):
    """Generate a human-readable section title from the path"""
    category = os.path.basename(category_path)
    return category.replace('_', ' ').title()

def group_figures_by_metadata(category_path, metadata_db):
    """Group figures within a category by metadata attributes"""
    figures = glob.glob(os.path.join(category_path, "*.png"))
    
    # Group by task, then by subject
    grouped = {}
    
    for fig_path in figures:
        filename = os.path.basename(fig_path)
        if filename in metadata_db:
            meta = metadata_db[filename]
            task = meta.get('task', 'unknown_task')
            subject = meta.get('subject', 'unknown_subject')
            condition = meta.get('condition', 'unknown_condition')
            
            # Create nested structure
            if task not in grouped:
                grouped[task] = {}
            if subject not in grouped[task]:
                grouped[task][subject] = {}
            if condition not in grouped[task][subject]:
                grouped[task][subject][condition] = []
                
            grouped[task][subject][condition].append((fig_path, filename, meta))
        else:
            # No metadata, add to unknown group
            if 'unknown' not in grouped:
                grouped['unknown'] = {'unknown': {'unknown': []}}
            grouped['unknown']['unknown']['unknown'].append((fig_path, filename, {}))
    
    return grouped

def generate_mne_report():
    """Generate an MNE report from the organized figures with enhanced organization"""
    try:
        # Create a new report
        report = mne.Report(title='MEG/EEG Analysis Report')
        
        # Get current date for report naming
        current_date = datetime.now().strftime("%Y-%m-%d")
        
        # Read metadata database
        metadata_db = read_metadata()
        
        # Get all top-level category directories
        category_dirs = [d for d in os.listdir(LOCAL_FIG_PATH) 
                        if os.path.isdir(os.path.join(LOCAL_FIG_PATH, d))]
        
        # Custom CSS for better formatting
        custom_css = """
        <style>
            .mne-report-section h2 {
                padding: 10px;
                background-color: #f0f0f8;
                border-left: 5px solid #3498db;
            }
            
            .mne-report-section h3 {
                margin-top: 20px;
                border-bottom: 2px solid #7cb9e8;
            }
            
            .mne-report-section h4 {
                margin-top: 15px;
                color: #2980b9;
            }
            
            .mne-report-section figure {
                box-shadow: 0 2px 5px rgba(0,0,0,0.1);
                padding: 10px;
                margin: 15px 0;
                transition: transform 0.2s;
            }
            
            .mne-report-section figure:hover {
                transform: scale(1.02);
            }
            
            .mne-report-section figcaption {
                font-size: 14px;
                margin-top: 8px;
                font-style: italic;
            }
            
            .metadata-table {
                font-size: 13px;
                margin-bottom: 15px;
                width: 100%;
                border-collapse: collapse;
            }
            
            .metadata-table th, .metadata-table td {
                border: 1px solid #ddd;
                padding: 8px;
                text-align: left;
            }
            
            .metadata-table th {
                background-color: #f2f2f2;
            }
        </style>
        """
        
        # Add custom CSS to the report
        report.add_custom_css(custom_css)
        
        # Add overview section
        overview_html = f"""
        <h2>Analysis Overview</h2>
        <p>Report generated on {current_date}</p>
        <p>This report contains MEG/EEG analysis results organized by analysis type.</p>
        <p>Total figures: {sum(len(glob.glob(os.path.join(LOCAL_FIG_PATH, cat, "**/*.png"), recursive=True)) for cat in category_dirs)}</p>
        """
        report.add_html(overview_html, title="Overview")
        
        # Process each category
        for category in category_dirs:
            category_path = os.path.join(LOCAL_FIG_PATH, category)
            section_title = get_section_title(category_path)
            
            # Check if there are any PNG files in this category (including subdirectories)
            all_pngs = glob.glob(os.path.join(category_path, "**/*.png"), recursive=True)
            if not all_pngs:
                continue
                
            # Add category introduction
            category_html = f"<h2>{section_title}</h2>"
            report.add_html(category_html, title=section_title)
            
            # Process direct figures in the category folder
            direct_figures = glob.glob(os.path.join(category_path, "*.png"))
            if direct_figures:
                # Group figures by metadata
                grouped = group_figures_by_metadata(category_path, metadata_db)
                
                for task, subjects in grouped.items():
                    task_title = f"{task.replace('_', ' ').title()} Task"
                    task_html = f"<h3>{task_title}</h3>"
                    report.add_html(task_html, title=f"{section_title} - {task_title}")
                    
                    for subject, conditions in subjects.items():
                        subj_title = f"Subject: {subject}"
                        subj_html = f"<h4>{subj_title}</h4>"
                        report.add_html(subj_html, title=f"{task_title} - {subj_title}")
                        
                        for condition, figures in conditions.items():
                            cond_title = f"Condition: {condition}"
                            cond_html = f"<h5>{cond_title}</h5>"
                            report.add_html(cond_html, title=f"{subj_title} - {cond_title}")
                            
                            # Add figures
                            for fig_path, filename, meta in figures:
                                fig_title = filename.replace('.png', '').replace('_', ' ').title()
                                report.add_image(
                                    image=fig_path,
                                    title=fig_title,
                                    caption=generate_caption(meta)
                                )
            
            # Process subdirectories if any
            subdirs = [d for d in os.listdir(category_path) 
                      if os.path.isdir(os.path.join(category_path, d))]
            
            for subdir in subdirs:
                subdir_path = os.path.join(category_path, subdir)
                subdir_title = f"{section_title} - {subdir.replace('_', ' ').title()}"
                
                # Add subdir introduction
                subdir_html = f"<h3>{subdir_title}</h3>"
                report.add_html(subdir_html, title=subdir_title)
                
                # Add all figures in this subdirectory
                for fig_file in glob.glob(os.path.join(subdir_path, "*.png")):
                    filename = os.path.basename(fig_file)
                    fig_title = filename.replace('.png', '').replace('_', ' ').title()
                    
                    # Get metadata if available
                    meta = metadata_db.get(filename, {})
                    
                    report.add_figure(
                        fig=fig_file,
                        title=fig_title,
                        caption=generate_caption(meta)
                    )
        
        # Save the report
        report_filename = f"mne_report_{current_date}.html"
        report_path = os.path.join(LOCAL_REPORT_PATH, report_filename)
        report.save(report_path, overwrite=True)
        
        logger.info(f"Report generated at: {report_path}")
        return report_path, current_date
    
    except Exception as e:
        logger.error(f"Error generating report: {str(e)}")
        logger.error(traceback.format_exc())
        send_email_notification(
            subject="MNE Report Generation Failed",
            body=f"Error generating MNE report: {str(e)}\n\n{traceback.format_exc()}",
            success=False
        )
        return None, datetime.now().strftime("%Y-%m-%d")

def generate_caption(metadata):
    """Generate a descriptive caption from metadata"""
    if not metadata:
        return "No metadata available"
    
    caption_parts = []
    
    # Add important metadata in a readable format
    for key in ['subject', 'task', 'condition', 'component', 'analysis_type']:
        if key in metadata:
            caption_parts.append(f"{key.replace('_', ' ').title()}: {metadata[key]}")
    
    # Add acquisition date if available
    if 'timestamp' in metadata:
        caption_parts.append(f"Date: {metadata['timestamp']}")
    
    return " | ".join(caption_parts) if caption_parts else "No metadata available"

def update_github_website(report_path, date):
    """Copy the report to the GitHub repo and update the website"""
    try:
        # Create weekly directory structure if needed
        week_dir = get_week_directory(date)
        github_week_dir = os.path.join(GITHUB_FILES_PATH, week_dir)
        os.makedirs(github_week_dir, exist_ok=True)
        
        # Copy the report to the GitHub repo
        report_filename = os.path.basename(report_path)
        github_report_path = os.path.join(github_week_dir, report_filename)
        shutil.copy2(report_path, github_report_path)
        
        # Update index.html
        update_index_html(report_filename, week_dir, date)
        
        # Commit and push changes
        git_commit_and_push(f"Update with MEG/EEG report for {date}")
        
        # Send success notification
        send_email_notification(
            subject=f"MNE Report Updated - {date}",
            body=f"Successfully generated and published MNE report for {date}.\n\nReport is available at: https://your-github-pages-url/files/{week_dir}/{report_filename}",
            success=True
        )
        
        logger.info(f"GitHub website updated with report: {github_report_path}")
        return True
    except Exception as e:
        logger.error(f"Error updating GitHub website: {str(e)}")
        logger.error(traceback.format_exc())
        send_email_notification(
            subject="GitHub Website Update Failed",
            body=f"Error updating GitHub website: {str(e)}\n\n{traceback.format_exc()}",
            success=False
        )
        return False

def get_week_directory(date_str):
    """Convert date to a week directory name"""
    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
    year = date_obj.year
    # Calculate week of year
    week_num = date_obj.isocalendar()[1]
    return f"week{week_num}_{year}"

def update_index_html(report_filename, week_dir, date_str):
    """Update the index.html file to include the new report"""
    try:
        index_path = os.path.join(GITHUB_REPO_PATH, "index.html")
        
        with open(index_path, 'r') as file:
            content = file.read()
        
        # Format date for display
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        formatted_date = date_obj.strftime("%A, %B %d, %Y")
        
        # Get metadata summary for the report
        metadata_db = read_metadata()
        total_figures = len(metadata_db)
        subjects = set(meta.get('subject', 'unknown') for meta in metadata_db.values())
        tasks = set(meta.get('task', 'unknown') for meta in metadata_db.values())
        
        # Create a new meeting section
        new_section = f'''
            <div class="meeting-section">
                <div class="meeting-date">{formatted_date}</div>
                <h3>MEG/EEG Analysis Update</h3>
                <p>This update includes the latest MEG and EEG analyses with {total_figures} figures 
                   from {len(subjects)} subjects across {len(tasks)} tasks. The report includes 
                   preprocessing results, source localization, and statistical analyses.</p>
                <div class="meeting-files">
                    <h4>Files:</h4>
                    <a href="files/{week_dir}/{report_filename}" class="file-link">MNE Analysis Report</a>
                </div>
            </div>
    '''
        
        # Insert the new section after the h2 Weekly Meetings tag
        if '<h2>Weekly Meetings</h2>' in content:
            updated_content = content.replace(
                '<h2>Weekly Meetings</h2>', 
                '<h2>Weekly Meetings</h2>\n' + new_section
            )
            
            with open(index_path, 'w') as file:
                file.write(updated_content)
            
            logger.info(f"Updated index.html with new report link")
            return True
        else:
            logger.warning("Could not find the Weekly Meetings section in index.html")
            return False
    except Exception as e:
        logger.error(f"Error updating index.html: {str(e)}")
        return False

def git_commit_and_push(commit_message):
    """Commit and push changes to GitHub"""
    try:
        os.chdir(GITHUB_REPO_PATH)
        
        # Add all changes
        subprocess.run(["git", "add", "."], check=True)
        
        # Commit
        subprocess.run(["git", "commit", "-m", commit_message], check=True)
        
        # Push
        subprocess.run(["git", "push"], check=True)
        
        logger.info("Changes committed and pushed to GitHub")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Git error: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"Error in git operations: {str(e)}")
        return False

def send_email_notification(subject, body, success=True):
    """Send email notification about pipeline status"""
    if not EMAIL_CONFIG['enabled']:
        logger.info("Email notifications disabled")
        return
    
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_CONFIG['sender']
        msg['To'] = ', '.join(EMAIL_CONFIG['recipients'])
        
        # Add success/failure indicator to subject
        prefix = "✅" if success else "❌"
        msg['Subject'] = f"{prefix} {subject}"
        
        # Body content
        msg.attach(MIMEText(body, 'plain'))
        
        # Attach log file if it exists
        log_file = "pipeline.log"
        if os.path.exists(log_file):
            with open(log_file, 'rb') as f:
                log_attachment = MIMEApplication(f.read(), Name=os.path.basename(log_file))
                log_attachment['Content-Disposition'] = f'attachment; filename="{os.path.basename(log_file)}"'
                msg.attach(log_attachment)
        
        # Connect to server and send
        server = smtplib.SMTP(EMAIL_CONFIG['smtp_server'], EMAIL_CONFIG['smtp_port'])
        server.starttls()
        server.login(EMAIL_CONFIG['sender'], EMAIL_CONFIG['password'])
        server.send_message(msg)
        server.quit()
        
        logger.info(f"Email notification sent: {subject}")
    except Exception as e:
        logger.error(f"Failed to send email notification: {str(e)}")

if __name__ == "__main__":
    report_path, date = generate_mne_report()
    if report_path:
        update_github_website(report_path, date)
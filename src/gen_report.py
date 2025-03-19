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

def get_experiment_description(experiment_name):
    """Get a description for each experiment type based on the experiment name"""
    descriptions = {
        "mindsentences": "An experiment examining neural responses to auditory language processing using MEG. This study focuses on syntax building and word decoding for controlled and naturalistic stimuli.",
        "distraction": "This experiment investigates how distractions impact neural dynamics of speech comprehension. Different types of distractions (math, memory tasks, etc.) are presented every other normal listening run.",
        "probe": "An experiment where we try to probe both the brain and language models looking for syntactic cues.",
        "expertlm": "Research exploring how preprompting a LLM with some expert qualification would change its embeddings, processing of information, and ultimately brain scores.",
        # Add more experiment descriptions as needed
    }
    
    # Default description for unrecognized experiments
    return descriptions.get(experiment_name.lower(), "MEG Weekly Analysis MNE Report.")

def generate_mne_report(custom_date=None):
    """Generate an MNE report from the organized figures with improved organization and layout"""
    try:
        # Create a new report with a more specific title
        report = mne.Report(title='MEG Weekly Analysis Report')
        
        # Get current date for report naming, or use custom date if provided
        if custom_date:
            current_date = custom_date.strftime("%Y-%m-%d")
        else:
            current_date = datetime.now().strftime("%Y-%m-%d")
        
        # Read metadata database
        metadata_db = read_metadata()
        
        # Get all top-level category directories
        category_dirs = [d for d in os.listdir(LOCAL_FIG_PATH) 
                        if os.path.isdir(os.path.join(LOCAL_FIG_PATH, d))]
        
        # Custom CSS for better formatting and smaller figures
        custom_css = """
        <style>
            body {
                font-family: Arial, sans-serif;
                margin: 20px;
                line-height: 1.6;
                color: #333;
                background-color: #f8f9fa;
            }
            
            .mne-report-section {
                margin-bottom: 30px;
                background-color: white;
                padding: 20px;
                border-radius: 8px;
                box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            }
            
            .mne-report-section h2 {
                padding: 10px 15px;
                background-color: #e7f5ff;
                border-left: 5px solid #1e88e5;
                margin: 20px 0;
                border-radius: 0 4px 4px 0;
                font-size: 1.5em;
            }
            
            .mne-report-section h3 {
                margin-top: 25px;
                border-bottom: 2px solid #bbdefb;
                padding-bottom: 5px;
                color: #1976d2;
                font-size: 1.3em;
            }
            
            .mne-report-section h4 {
                margin-top: 15px;
                color: #2962ff;
                font-size: 1.1em;
            }
            
            .mne-report-section figure {
                box-shadow: 0 1px 3px rgba(0,0,0,0.12);
                padding: 15px;
                margin: 15px 0;
                transition: transform 0.2s;
                max-width: 650px;
                background-color: white;
                border-radius: 4px;
            }
            
            .mne-report-section figure:hover {
                transform: translateY(-2px);
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            }
            
            .mne-report-section img {
                max-width: 100%;
                height: auto;
            }
            
            .mne-report-section figcaption {
                font-size: 13px;
                margin-top: 10px;
                font-style: italic;
                color: #505050;
                border-top: 1px solid #eee;
                padding-top: 8px;
            }
            
            .experiment-description {
                background-color: #f0f7fb;
                padding: 15px;
                border-left: 3px solid #1e88e5;
                margin: 15px 0;
                font-size: 14px;
                border-radius: 0 4px 4px 0;
            }
            
            .figure-grid {
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
                grid-gap: 20px;
                margin: 20px 0;
            }
            
            .overview-container {
                background-color: #e3f2fd;
                border-radius: 8px;
                padding: 20px;
                margin-bottom: 25px;
                border-left: 5px solid #1e88e5;
                color: #0d47a1;
            }
            
            .overview-container h2 {
                margin-top: 0;
                color: #0d47a1;
                background: none;
                border-left: none;
                padding: 0;
            }
            
            .toc-container {
                background-color: #fff;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                padding: 20px;
                margin: 20px 0;
                box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            }
            
            .toc-container h3 {
                margin-top: 0;
                border-bottom: 1px solid #e0e0e0;
                padding-bottom: 10px;
                color: #1976d2;
            }
            
            .toc-container ul {
                list-style-type: none;
                padding-left: 5px;
            }
            
            .toc-container li {
                margin-bottom: 8px;
                padding-left: 15px;
                position: relative;
            }
            
            .toc-container li:before {
                content: '•';
                position: absolute;
                left: 0;
                color: #1e88e5;
            }
            
            .toc-container a {
                text-decoration: none;
                color: #1976d2;
                font-weight: 500;
                transition: all 0.2s;
            }
            
            .toc-container a:hover {
                color: #0d47a1;
                padding-left: 3px;
            }
            
            .date-stamp {
                color: #666;
                font-style: italic;
                margin-bottom: 15px;
            }
            
            .figures-summary {
                display: flex;
                flex-wrap: wrap;
                gap: 10px;
                margin: 15px 0;
            }
            
            .figure-stat {
                background-color: #bbdefb;
                padding: 8px 15px;
                border-radius: 20px;
                font-weight: 500;
                color: #0d47a1;
            }
        </style>
        """
        
        # Add custom CSS to the report
        report.add_custom_css(custom_css)
        
        # Create table of contents list for later
        toc_items = []
        
        # Count total figures
        total_figures = 0
        for category in category_dirs:
            category_path = os.path.join(LOCAL_FIG_PATH, category)
            figures = glob.glob(os.path.join(category_path, "**/*.png"), recursive=True)
            total_figures += len(figures)
        
        # Get unique subjects and tasks
        subjects = set()
        tasks = set()
        for meta in metadata_db.values():
            if 'subject' in meta:
                subjects.add(meta['subject'])
            if 'task' in meta:
                tasks.add(meta['task'])
        
        # Add overview section
        overview_html = f"""
        <div class="overview-container">
            <h2>MEG Weekly Analysis Report</h2>
            <p class="date-stamp">Generated on {datetime.strptime(current_date, '%Y-%m-%d').strftime('%A, %B %d, %Y')}</p>
            
            <p>This report contains MEG/EEG analysis results from the past week.</p>
            
            <div class="figures-summary">
                <span class="figure-stat">{total_figures} figures</span>
                <span class="figure-stat">{len(subjects)} subjects</span>
                <span class="figure-stat">{len(tasks)} experimental tasks</span>
            </div>
        </div>
        """
        report.add_html(overview_html, title="Overview")
        
        # Filter out empty categories and prepare table of contents
        valid_categories = []
        for category in category_dirs:
            category_path = os.path.join(LOCAL_FIG_PATH, category)
            all_pngs = glob.glob(os.path.join(category_path, "**/*.png"), recursive=True)
            if all_pngs:
                valid_categories.append(category)
                section_title = get_section_title(category_path)
                toc_items.append(f'<li><a href="#{category.lower()}">{section_title}</a></li>')
        
        # Add table of contents
        toc_html = f"""
        <div class="toc-container">
            <h3>Contents</h3>
            <ul>
                {''.join(toc_items)}
            </ul>
        </div>
        """
        report.add_html(toc_html, title="Table of Contents")
        
        # Simplify the organization by processing each category
        for category in valid_categories:
            category_path = os.path.join(LOCAL_FIG_PATH, category)
            section_title = get_section_title(category_path)
            
            # Add category introduction with anchor for TOC
            category_html = f"""
            <div id="{category.lower()}">
                <h2>{section_title}</h2>
                <div class="experiment-description">
                    {get_experiment_description(category)}
                </div>
            </div>
            """
            report.add_html(category_html, title=section_title)
            
            # Get all figures in this category, including subdirectories
            all_figures = glob.glob(os.path.join(category_path, "**/*.png"), recursive=True)
            
            # Group figures by subcategory (if in a subdirectory)
            grouped_figures = {}
            for fig_path in all_figures:
                # Determine if the figure is in a subdirectory
                rel_path = os.path.relpath(fig_path, category_path)
                subdir = os.path.dirname(rel_path)
                
                if subdir == "":  # Not in a subdirectory
                    subdir = "main"
                
                if subdir not in grouped_figures:
                    grouped_figures[subdir] = []
                grouped_figures[subdir].append(fig_path)
            
            # Process each group of figures
            for subdir, figures in grouped_figures.items():
                if subdir == "main":
                    subdir_title = f"General {section_title}"
                else:
                    subdir_title = subdir.replace('_', ' ').title()
                
                # Add subheading for the group
                if len(grouped_figures) > 1:  # Only add subheading if there are multiple groups
                    report.add_html(f"<h3>{subdir_title}</h3>", title=f"{section_title} - {subdir_title}")
                
                # Add the figures
                for fig_path in figures:
                    filename = os.path.basename(fig_path)
                    meta = metadata_db.get(filename, {})
                    
                    # Create a more descriptive title from the filename
                    title_parts = filename.replace('.png', '').split('_')
                    fig_title = ' '.join(word.capitalize() for word in title_parts if not word.startswith('sub-') and not word.startswith('task-'))
                    
                    # Add the figure
                    report.add_image(
                        image=fig_path,
                        title=fig_title or filename,
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
        return None, datetime.now().strftime("%Y-%m-%d")

def generate_caption(metadata):
    """Generate a concise, descriptive caption from metadata"""
    if not metadata:
        return "No metadata available"
    
    # Focus on the most important fields and make caption concise
    important_fields = ['task', 'condition', 'analysis_type']
    secondary_fields = ['subject', 'component', 'timestamp']
    
    caption_parts = []
    
    # Add primary information first
    for key in important_fields:
        if key in metadata and metadata[key]:
            # Format and add field
            value = metadata[key]
            # Make task and analysis_type more readable
            if key == 'task' or key == 'analysis_type':
                value = value.replace('_', ' ').title()
            caption_parts.append(f"{key.replace('_', ' ').title()}: {value}")
    
    # Add secondary information if available
    for key in secondary_fields:
        if key in metadata and metadata[key]:
            # Format date differently
            if key == 'timestamp':
                caption_parts.append(f"Date: {metadata[key]}")
            else:
                caption_parts.append(f"{key.replace('_', ' ').title()}: {metadata[key]}")
    
    # Join parts with a separator
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
        git_commit_and_push(f"Update MNE report on the {date}")
        
        # Send success notification
        # send_email_notification(
        #     subject=f"MNE Report Updated - {date}",
        #     body=f"Successfully generated and published MNE report for {date}.\n\nReport is available at: https://your-github-pages-url/files/{week_dir}/{report_filename}",
        #     success=True
        # )
        
        logger.info(f"GitHub website updated with report: {github_report_path}")
        return True
    except Exception as e:
        logger.error(f"Error updating GitHub website: {str(e)}")
        logger.error(traceback.format_exc())
        # send_email_notification(
        #     subject="GitHub Website Update Failed",
        #     body=f"Error updating GitHub website: {str(e)}\n\n{traceback.format_exc()}",
        #     success=False
        # )
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
                <h3>Weekly Update</h3>
                <p>This update includes the latest MEG analyses with {total_figures} figures 
                   from {len(subjects)} subjects across {len(tasks)} tasks. The report includes 
                   preprocessing results, source localization, and statistical analyses.</p>
                <div class="meeting-files">
                    <h4>Files:</h4>
                    <a href="files/{week_dir}/{report_filename}" class="file-link">MNE Analysis Report</a>
                </div>
            </div>
    '''
        
        # Insert the new section after the h2 Weekly meetings tag
        if '<h2>Weekly meetings</h2>' in content:
            updated_content = content.replace(
                '<h2>Weekly meetings</h2>', 
                '<h2>Weekly meetings</h2>\n' + new_section
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
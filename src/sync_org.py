#!/usr/bin/env python3
import os
import subprocess
import re
import shutil
from datetime import datetime, timedelta
import glob
import logging
import json

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("pipeline.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("mne_pipeline")

# Configuration
REMOTE_FIG_PATH = "/home/cbel/results/figs_for_report/"
LOCAL_FIG_PATH = "/home/co/data/mne_reports/figures/"
LOCAL_REPORT_PATH = "/home/co/data/mne_reports/"
GITHUB_REPO_PATH = "/home/co/git/pi-aiche-dee/"
GITHUB_FILES_PATH = os.path.join(GITHUB_REPO_PATH, "files")
METADATA_FILE = os.path.join(LOCAL_FIG_PATH, "metadata.json")

# Figure metadata patterns
METADATA_PATTERNS = {
    'subject': r'sub-(\w+)',
    'task': r'task-(\w+)',
    'condition': r'cond-(\w+)',
    'analysis_type': r'(meg|eeg|source|topo)',
    'component': r'(N[0-9]+|P[0-9]+)',
    'timestamp': r'([0-9]{8}T[0-9]{6})'
}

def sync_figures_from_cluster():
    """Sync figures from the cluster to local machine"""
    try:
        os.makedirs(LOCAL_FIG_PATH, exist_ok=True)
        
        rsync_command = [
            "rsync", "-vr", "--progress", "--ignore-existing",
            f"cbel@frontex:{REMOTE_FIG_PATH}", LOCAL_FIG_PATH
        ]
        
        logger.info("Syncing figures from cluster...")
        result = subprocess.run(rsync_command, capture_output=True, text=True)
        
        if result.returncode == 0:
            logger.info("Sync complete!")
            # Log number of new files
            new_files = [line for line in result.stdout.split('\n') if line.endswith('.png')]
            logger.info(f"Synced {len(new_files)} new figure(s)")
            return True
        else:
            logger.error(f"Sync failed with error: {result.stderr}")
            return False
    except Exception as e:
        logger.error(f"Error during sync: {str(e)}")
        return False

def extract_metadata(filename):
    """Extract metadata from filename using regex patterns"""
    metadata = {
        'filename': filename,
        'added_date': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    for key, pattern in METADATA_PATTERNS.items():
        match = re.search(pattern, filename)
        if match:
            metadata[key] = match.group(1)
    
    return metadata

def update_metadata_db(new_file_metadata):
    """Update the metadata JSON database with new file information"""
    try:
        if os.path.exists(METADATA_FILE):
            with open(METADATA_FILE, 'r') as f:
                metadata_db = json.load(f)
        else:
            metadata_db = {}
        
        # Update with new files
        for metadata in new_file_metadata:
            filename = metadata['filename']
            metadata_db[filename] = metadata
            
        # Save updated metadata
        with open(METADATA_FILE, 'w') as f:
            json.dump(metadata_db, f, indent=2)
            
        logger.info(f"Updated metadata database with {len(new_file_metadata)} entries")
        return metadata_db
    except Exception as e:
        logger.error(f"Error updating metadata database: {str(e)}")
        return {}

def is_recent_file(file_path, days=7):
    """
    Check if a file was created or modified within the specified number of days
    
    Parameters:
    -----------
    file_path : str
        Path to the file
    days : int
        Number of days to consider a file as recent
        
    Returns:
    --------
    bool
        True if the file is recent, False otherwise
    """
    try:
        # Get file's modification time
        file_mtime = os.path.getmtime(file_path)
        file_date = datetime.fromtimestamp(file_mtime)
        
        # Calculate the cutoff date
        cutoff_date = datetime.now() - timedelta(days=days)
        
        # Return True if file is newer than cutoff date
        return file_date >= cutoff_date
    except Exception as e:
        logger.error(f"Error checking if file is recent: {str(e)}")
        # If there's an error, return True to include the file by default
        return True

def organize_figures(days_threshold=7):
    """Organize figures into categories based on filename patterns and metadata"""
    try:
        # Primary categories based on analysis type
        categories = {
            'language_processing': ['mindsentences', 'language', 'semantic', 'syntactic'],
            'eeg_analysis': ['eeg', 'erp'],
            'meg_analysis': ['meg', 'event'],
            'source_localization': ['source', 'mne', 'dics', 'lcmv'],
            'topographic_maps': ['topo', 'map'],
            'connectivity': ['connect', 'network'],
            'time_frequency': ['tf', 'frequency', 'power', 'tfr']
        }
        
        # Secondary categories for sub-organization
        subcategories = {
            'subject': r'sub-(\w+)',
            'task': r'task-(\w+)',
            'condition': r'cond-(\w+)'
        }
        
        # Create category directories
        for category in categories.values():
            os.makedirs(os.path.join(LOCAL_FIG_PATH, category[0]), exist_ok=True)
        
        # Find all PNG files
        all_png_files = glob.glob(os.path.join(LOCAL_FIG_PATH, "*.png"))
        logger.info(f"Found {len(all_png_files)} PNG files to organize")
        
        # Filter to only include recent files
        recent_png_files = [f for f in all_png_files if is_recent_file(f, days_threshold)]
        logger.info(f"Filtered to {len(recent_png_files)} recent files (within {days_threshold} days)")
        
        # Track metadata for all files
        all_metadata = []
        
        # Categorize files
        for file in recent_png_files:
            filename = os.path.basename(file)
            metadata = extract_metadata(filename)
            all_metadata.append(metadata)
            
            # Determine primary category
            assigned = False
            for category_name, keywords in categories.items():
                for keyword in keywords:
                    if keyword in filename.lower():
                        # Create category dir if it doesn't exist
                        category_path = os.path.join(LOCAL_FIG_PATH, category_name)
                        os.makedirs(category_path, exist_ok=True)
                        
                        # Check for subcategory organization
                        for subcat, pattern in subcategories.items():
                            if subcat in metadata:
                                subcat_value = metadata[subcat]
                                subcat_path = os.path.join(category_path, f"{subcat}_{subcat_value}")
                                os.makedirs(subcat_path, exist_ok=True)
                                dest_path = os.path.join(subcat_path, filename)
                                break
                        else:
                            # No subcategory found
                            dest_path = os.path.join(category_path, filename)
                        
                        # Move file if destination doesn't exist
                        if not os.path.exists(dest_path):
                            shutil.move(file, dest_path)
                        
                        assigned = True
                        break
                
                if assigned:
                    break
            
            # If no category matched, put in misc
            if not assigned:
                misc_path = os.path.join(LOCAL_FIG_PATH, "misc")
                os.makedirs(misc_path, exist_ok=True)
                dest_path = os.path.join(misc_path, filename)
                if not os.path.exists(dest_path):
                    shutil.move(file, dest_path)
        
        # Update metadata database
        update_metadata_db(all_metadata)
        
        logger.info("Files organized successfully")
        return True
    except Exception as e:
        logger.error(f"Error organizing figures: {str(e)}")
        return False

if __name__ == "__main__":
    if sync_figures_from_cluster():
        organize_figures()
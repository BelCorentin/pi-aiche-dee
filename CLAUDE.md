# Pi-AICHE-DEE Repository Guidelines

## Commands
- Run pipeline: `python src/pipeline.py`
- Set up cron job: `python src/pipeline.py --setup-cron` or `bash src/crontab_setup.sh`
- Force run pipeline: `python src/pipeline.py --force`
- View logs: `cat src/pipeline.log`

## Code Style Guidelines
- **Imports**: Group imports in order: standard library, third-party libraries, local modules
- **Docstrings**: Use triple quotes for all functions and classes
- **Error Handling**: Use try/except blocks with specific error types and informative messages
- **Logging**: Use the existing logger from sync_org.py for consistent logging
- **Naming**: snake_case for variables/functions, UPPER_CASE for constants
- **Function Length**: Keep functions focused on single responsibility
- **Path Handling**: Use os.path.join() for cross-platform compatibility
- **Credentials**: Store sensitive data as environment variables, never hardcoded

## Codebase Structure
This repository contains code for automatic MEG/EEG data processing and report generation:
- `src/pipeline.py`: Main pipeline script that orchestrates the full workflow
- `src/sync_org.py`: Handles syncing and organizing figures from remote cluster
- `src/gen_report.py`: Generates HTML reports using MNE and updates website
- `src/crontab_setup.sh`: Helper script for setting up automated runs
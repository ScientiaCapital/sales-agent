#!/usr/bin/env python3
"""
Output Directory Cleanup Tool
==============================
Maintains clean output directory structure:
- Archives old/test files to _archive/
- Keeps only current Gold Standard files
- Sets up proper log directory structure

SAFE BY DEFAULT: --dry-run shows what would be cleaned

Usage:
    python cleanup_output_files.py --dry-run    # Preview changes
    python cleanup_output_files.py              # Execute cleanup
    python cleanup_output_files.py --aggressive # Also clean filtered_* older than 7 days

Author: Claude + Tim
Date: Nov 29, 2025
"""

import os
import shutil
from pathlib import Path
from datetime import datetime, timedelta
import argparse
import logging

# Setup
OUTPUT_DIR = Path("data/final_enrichment_output")
ARCHIVE_DIR = OUTPUT_DIR / "_archive"
LOG_DIR = Path("data/logs")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)


# Files to ALWAYS keep (glob patterns)
KEEP_PATTERNS = [
    "GOLD_STANDARD_TOP_*.csv",       # Current tier lists
    "all_leads_scored_*.csv",        # Master scored list
    "leads_for_enrichment_*.csv",    # Enrichment queue
    "enriched_batch_*_*.csv",        # Enrichment results (current run)
    "change_report_*.json",          # Change tracking
    "filtered_*.csv",                # OEM filter results (keep recent)
    "schneider_icp_analysis_*.md",   # Analysis reports
]

# Files to ALWAYS archive (old test patterns)
ARCHIVE_PATTERNS = [
    "MASTER_enriched_*.csv",         # Old test files
    "MEP_enriched_*.csv",            # Old MEP test files
    "test_*.csv",                    # Test outputs
    "debug_*.csv",                   # Debug outputs
    "temp_*.csv",                    # Temp files
    "pipeline_*.log",                # Old pipeline logs -> move to data/logs/
]


def setup_directories():
    """Create archive and log directories if they don't exist."""
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # Create dated archive subdirectory
    date_dir = ARCHIVE_DIR / datetime.now().strftime("%Y-%m-%d")
    date_dir.mkdir(exist_ok=True)

    return date_dir


def should_keep(filepath: Path) -> bool:
    """Check if file matches a KEEP pattern."""
    for pattern in KEEP_PATTERNS:
        if filepath.match(pattern):
            return True
    return False


def should_archive(filepath: Path) -> bool:
    """Check if file matches an ARCHIVE pattern."""
    for pattern in ARCHIVE_PATTERNS:
        if filepath.match(pattern):
            return True
    return False


def get_file_age_days(filepath: Path) -> int:
    """Get file age in days."""
    mtime = datetime.fromtimestamp(filepath.stat().st_mtime)
    return (datetime.now() - mtime).days


def cleanup_output_directory(dry_run: bool = True, aggressive: bool = False):
    """
    Clean up the output directory.

    Args:
        dry_run: If True, only print what would be done
        aggressive: If True, also archive filtered_* files older than 7 days
    """
    if not OUTPUT_DIR.exists():
        logger.error(f"Output directory not found: {OUTPUT_DIR}")
        return

    archive_dir = setup_directories()

    # Collect files to process
    to_archive = []
    to_keep = []
    unknown = []

    for filepath in OUTPUT_DIR.glob("*"):
        # Skip directories
        if filepath.is_dir():
            continue

        # Skip non-data files
        if filepath.suffix not in ['.csv', '.json', '.log', '.md']:
            continue

        if should_keep(filepath):
            to_keep.append(filepath)
        elif should_archive(filepath):
            to_archive.append(filepath)
        elif aggressive and filepath.name.startswith("filtered_"):
            # In aggressive mode, archive old filtered files
            if get_file_age_days(filepath) > 7:
                to_archive.append(filepath)
            else:
                to_keep.append(filepath)
        else:
            unknown.append(filepath)

    # Report
    logger.info("=" * 60)
    logger.info("OUTPUT DIRECTORY CLEANUP")
    logger.info("=" * 60)

    logger.info(f"\n📁 Keeping ({len(to_keep)} files):")
    for f in sorted(to_keep):
        size_kb = f.stat().st_size / 1024
        logger.info(f"  ✅ {f.name} ({size_kb:.1f} KB)")

    logger.info(f"\n📦 Archiving ({len(to_archive)} files):")
    for f in sorted(to_archive):
        size_kb = f.stat().st_size / 1024
        age = get_file_age_days(f)
        logger.info(f"  🗄️  {f.name} ({size_kb:.1f} KB, {age} days old)")

    if unknown:
        logger.info(f"\n❓ Unknown ({len(unknown)} files):")
        for f in sorted(unknown):
            logger.info(f"  ?  {f.name}")

    # Execute if not dry run
    if dry_run:
        logger.info("\n⚠️  DRY RUN - No files moved")
        logger.info("Run without --dry-run to execute cleanup")
        return

    # Move files to archive
    archived_count = 0
    for filepath in to_archive:
        dest = archive_dir / filepath.name
        shutil.move(str(filepath), str(dest))
        archived_count += 1

    logger.info(f"\n✅ Archived {archived_count} files to {archive_dir}")

    # Calculate space saved
    total_archived_size = sum((archive_dir / f.name).stat().st_size
                              for f in to_archive if (archive_dir / f.name).exists())
    logger.info(f"💾 Space cleaned: {total_archived_size / 1024:.1f} KB")


def setup_logging_structure():
    """Set up proper logging directory structure."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # Create subdirectories for different log types
    (LOG_DIR / "enrichment").mkdir(exist_ok=True)
    (LOG_DIR / "sync").mkdir(exist_ok=True)
    (LOG_DIR / "scoring").mkdir(exist_ok=True)

    logger.info(f"\n📋 Log directories created:")
    logger.info(f"  {LOG_DIR}/enrichment/ - Hunter.io batch logs")
    logger.info(f"  {LOG_DIR}/sync/ - Supabase/Close sync logs")
    logger.info(f"  {LOG_DIR}/scoring/ - ICP scoring run logs")


def main():
    parser = argparse.ArgumentParser(description='Clean up output directory')
    parser.add_argument('--dry-run', action='store_true', default=True,
                        help='Preview changes without executing (default)')
    parser.add_argument('--execute', action='store_true',
                        help='Actually execute the cleanup')
    parser.add_argument('--aggressive', action='store_true',
                        help='Also archive filtered_* files older than 7 days')
    parser.add_argument('--setup-logs', action='store_true',
                        help='Set up logging directory structure')

    args = parser.parse_args()

    # --execute overrides default dry-run
    dry_run = not args.execute

    if args.setup_logs:
        setup_logging_structure()

    cleanup_output_directory(dry_run=dry_run, aggressive=args.aggressive)


if __name__ == "__main__":
    main()

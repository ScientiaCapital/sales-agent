#!/usr/bin/env python3
"""
Project Audit Script - Analyzes all files and categorizes by usage.

Generates three lists:
1. DELETE_LIST.txt - Files to delete (unused/stale)
2. ARCHIVE_CANDIDATES.txt - Files to ask user about archiving
3. KEEP_LIST.txt - Files confirmed as active
"""

import os
import re
from pathlib import Path
from collections import defaultdict
from typing import Set, List, Dict

# Project root
ROOT = Path(__file__).parent.parent.parent

# Critical files that should NEVER be deleted
CRITICAL_PATTERNS = [
    r'README\.md$',
    r'TASK\.md$',
    r'CLAUDE\.md$',
    r'\.env',
    r'docker-compose.*\.yml$',
    r'requirements.*\.txt$',
    r'supabase/migrations/.*\.sql$',
    r'alembic/versions/.*\.py$',
    r'\.git',
]

# Core documentation (always keep)
CORE_DOCS = {
    'README.md',
    'TASK.md',
    'CLAUDE.md',
    'BACKLOG.md',
    'QUICK_START.md',
    'SETUP_GUIDE.md',
    'DOCUMENTATION_INDEX.md',
}

# Completion summaries (archive candidates)
COMPLETION_SUMMARIES = [
    'WEEK_1_COMPLETION_SUMMARY.md',
    'WEEK_2_COMPLETION_SUMMARY.md',
    'WEEK_3_COMPLETION_SUMMARY.md',
    'WEEK_4_COMPLETION_SUMMARY.md',
    'WEEK_4_CICD_DEBUGGING.md',
    'WEEK_5_TESTING_RESULTS.md',
    'TASK-014B-AUTH-PROTECTION-SUMMARY.md',
    'TASK_011_SUMMARY.md',
    'CLOSE_CRM_IMPLEMENTATION_SUMMARY.md',
    'AGENT_7_RLS_SECURITY_FIXES_REPORT.md',
    'CODE_QUALITY_BASELINE_REPORT.md',
    'API_KEYS_VALIDATION_REPORT.md',
    'BDR_WORKQUEUE_REVIEW_SUMMARY.md',
    'BDR_WORKQUEUE_FIXES_REQUIRED.md',
    'CODE_REVIEW_BDR_WORK_QUEUE.md',
    'REVIEW_COMPLETE.txt',
    'RLS_MIGRATION_SUMMARY.txt',
]

# Active backend scripts (keep)
ACTIVE_BACKEND_SCRIPTS = {
    'run_enrichment.py',
    'enrich_apollo.py',
    'enrich_linkedin.py',
    'enrich_hunter.py',
    'enrich_apollo_paid.py',
    'scrape_domain.py',
    'batch_scrape_runner.py',
    'create_gold_standard_lists.py',
    'enrich_gold_standard_batch.py',
    'sync_gold_standard_to_supabase.py',
    'create_prioritized_list.py',
    'cleanup_output_files.py',
    'score_and_export_top30.py',
    'export_hot_leads_top30.py',
    'export_non_close_hot_leads.py',
    'sync_close_contacts_to_supabase.py',
    'sync_close_to_star_schema.py',
    'deduplicate_leads.py',
    'import_from_scraper.py',
    'import_single_lead.py',
    'run_supervised_enrichment.py',
}

# Active root scripts (keep)
ACTIVE_ROOT_SCRIPTS = {
    'start_server.py',
    'agent_cli.py',  # Referenced in docs
    'notify.py',  # Imported in start_server.py
    'validate_api_keys.py',  # Referenced in docs
}

def is_critical_file(filepath: Path) -> bool:
    """Check if file matches critical patterns."""
    rel_path = str(filepath.relative_to(ROOT))
    for pattern in CRITICAL_PATTERNS:
        if re.search(pattern, rel_path):
            return True
    return False

def find_all_files() -> Dict[str, List[Path]]:
    """Find all files in project, excluding venv, node_modules, .git."""
    files = defaultdict(list)
    
    exclude_dirs = {'.git', 'venv', '__pycache__', 'node_modules', '.pytest_cache', '.mypy_cache'}
    
    for root, dirs, filenames in os.walk(ROOT):
        # Filter out excluded directories
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        
        root_path = Path(root)
        if any(excluded in root_path.parts for excluded in exclude_dirs):
            continue
            
        for filename in filenames:
            filepath = root_path / filename
            rel_path = str(filepath.relative_to(ROOT))
            
            # Skip critical files
            if is_critical_file(filepath):
                continue
                
            ext = filepath.suffix
            if ext == '.md':
                files['markdown'].append(filepath)
            elif ext == '.py':
                files['python'].append(filepath)
            elif ext in ['.txt', '.log', '.csv', '.json']:
                files['data'].append(filepath)
            else:
                files['other'].append(filepath)
    
    return files

def check_python_imports(filepath: Path, all_python_files: List[Path]) -> Set[str]:
    """Check if a Python file is imported anywhere."""
    if not filepath.exists():
        return set()
    
    # Get module name
    rel_path = filepath.relative_to(ROOT)
    if 'backend' in rel_path.parts:
        # Backend module
        parts = list(rel_path.parts)
        if parts[0] == 'backend':
            parts = parts[1:]
        module_name = '.'.join(parts).replace('.py', '').replace('/', '.')
    else:
        # Root script
        module_name = rel_path.stem
    
    imports_found = set()
    
    try:
        content = filepath.read_text(encoding='utf-8', errors='ignore')
        
        # Check for imports
        for py_file in all_python_files:
            if py_file == filepath:
                continue
            try:
                py_content = py_file.read_text(encoding='utf-8', errors='ignore')
                
                # Check various import patterns
                patterns = [
                    rf'import\s+{re.escape(module_name)}',
                    rf'from\s+{re.escape(module_name)}\s+import',
                    rf'import\s+.*{re.escape(rel_path.name)}',
                    rf'from\s+.*{re.escape(rel_path.stem)}',
                ]
                
                for pattern in patterns:
                    if re.search(pattern, py_content):
                        imports_found.add(str(py_file.relative_to(ROOT)))
                        break
            except Exception:
                continue
    except Exception:
        pass
    
    return imports_found

def check_markdown_references(filepath: Path, all_markdown_files: List[Path]) -> Set[str]:
    """Check if a markdown file is referenced in other docs."""
    if not filepath.exists():
        return set()
    
    filename = filepath.name
    references = set()
    
    try:
        content = filepath.read_text(encoding='utf-8', errors='ignore')
        
        for md_file in all_markdown_files:
            if md_file == filepath:
                continue
            try:
                md_content = md_file.read_text(encoding='utf-8', errors='ignore')
                
                # Check if filename is mentioned
                if filename in md_content or filepath.stem in md_content:
                    references.add(str(md_file.relative_to(ROOT)))
            except Exception:
                continue
    except Exception:
        pass
    
    return references

def categorize_files(files: Dict[str, List[Path]]) -> Dict[str, List[Path]]:
    """Categorize files into KEEP, ARCHIVE, DELETE."""
    categorized = {
        'keep': [],
        'archive': [],
        'delete': [],
    }
    
    all_python = files['python']
    all_markdown = files['markdown']
    
    # Process markdown files
    for md_file in all_markdown:
        rel_path = str(md_file.relative_to(ROOT))
        filename = md_file.name
        
        # Core docs - always keep
        if filename in CORE_DOCS:
            categorized['keep'].append(md_file)
            continue
        
        # Completion summaries - archive candidates
        if filename in COMPLETION_SUMMARIES:
            categorized['archive'].append(md_file)
            continue
        
        # Check references
        refs = check_markdown_references(md_file, all_markdown)
        if refs:
            categorized['keep'].append(md_file)
        else:
            # Check if it's in root and likely stale
            if md_file.parent == ROOT:
                # Check if it's an implementation guide that might be outdated
                if any(keyword in filename.upper() for keyword in ['GUIDE', 'SETUP', 'INTEGRATION', 'IMPLEMENTATION']):
                    categorized['archive'].append(md_file)
                else:
                    categorized['delete'].append(md_file)
            else:
                categorized['keep'].append(md_file)
    
    # Process Python files
    for py_file in all_python:
        rel_path = str(py_file.relative_to(ROOT))
        filename = py_file.name
        
        # Check if it's an active script
        if filename in ACTIVE_BACKEND_SCRIPTS or filename in ACTIVE_ROOT_SCRIPTS:
            categorized['keep'].append(py_file)
            continue
        
        # Check if it's in archive - already archived
        if 'archive' in py_file.parts:
            continue
        
        # Check if it's a test file
        if 'test' in py_file.parts or py_file.name.startswith('test_'):
            categorized['keep'].append(py_file)
            continue
        
        # Check if it's in backend/app - likely used
        if 'backend/app' in rel_path:
            # Check imports
            imports = check_python_imports(py_file, all_python)
            if imports:
                categorized['keep'].append(py_file)
            else:
                # Check if it's a model, schema, or core file
                if any(part in rel_path for part in ['models', 'schemas', 'core', 'api']):
                    categorized['keep'].append(py_file)
                else:
                    categorized['delete'].append(py_file)
        elif py_file.parent == ROOT:
            # Root Python scripts
            if filename in ACTIVE_ROOT_SCRIPTS:
                categorized['keep'].append(py_file)
            else:
                # Check imports
                imports = check_python_imports(py_file, all_python)
                if imports:
                    categorized['keep'].append(py_file)
                else:
                    categorized['delete'].append(py_file)
        else:
            # Other Python files - check imports
            imports = check_python_imports(py_file, all_python)
            if imports:
                categorized['keep'].append(py_file)
            else:
                categorized['delete'].append(py_file)
    
    return categorized

def write_lists(categorized: Dict[str, List[Path]]):
    """Write categorized lists to files."""
    output_dir = ROOT / 'backend' / 'scripts' / 'audit_results'
    output_dir.mkdir(exist_ok=True)
    
    # Write DELETE list
    delete_file = output_dir / 'DELETE_LIST.txt'
    with open(delete_file, 'w') as f:
        f.write("# Files to DELETE (unused/stale)\n\n")
        for filepath in sorted(categorized['delete']):
            f.write(f"{filepath.relative_to(ROOT)}\n")
    
    # Write ARCHIVE candidates
    archive_file = output_dir / 'ARCHIVE_CANDIDATES.txt'
    with open(archive_file, 'w') as f:
        f.write("# Files to ARCHIVE (ask user for approval)\n\n")
        for filepath in sorted(categorized['archive']):
            f.write(f"{filepath.relative_to(ROOT)}\n")
    
    # Write KEEP list
    keep_file = output_dir / 'KEEP_LIST.txt'
    with open(keep_file, 'w') as f:
        f.write("# Files to KEEP (active/referenced)\n\n")
        for filepath in sorted(categorized['keep']):
            f.write(f"{filepath.relative_to(ROOT)}\n")
    
    print(f"\n✅ Audit complete!")
    print(f"📄 DELETE_LIST.txt: {len(categorized['delete'])} files")
    print(f"📦 ARCHIVE_CANDIDATES.txt: {len(categorized['archive'])} files")
    print(f"✅ KEEP_LIST.txt: {len(categorized['keep'])} files")
    print(f"\nResults saved to: {output_dir}")

def main():
    print("🔍 Starting project audit...")
    print(f"📁 Project root: {ROOT}")
    
    files = find_all_files()
    print(f"\n📊 Found files:")
    print(f"  - Markdown: {len(files['markdown'])}")
    print(f"  - Python: {len(files['python'])}")
    print(f"  - Data: {len(files['data'])}")
    print(f"  - Other: {len(files['other'])}")
    
    print("\n🔎 Categorizing files...")
    categorized = categorize_files(files)
    
    print(f"\n📋 Categorization:")
    print(f"  - KEEP: {len(categorized['keep'])}")
    print(f"  - ARCHIVE: {len(categorized['archive'])}")
    print(f"  - DELETE: {len(categorized['delete'])}")
    
    write_lists(categorized)

if __name__ == '__main__':
    main()


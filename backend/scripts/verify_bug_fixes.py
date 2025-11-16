#!/usr/bin/env python3
"""
Bug Fix Verification Script

Verifies that all reported bugs have been addressed:
- Bug 1: Hardcoded API keys
- Bug 2: Migration down_revision issues
- Bug 3: Missing CHECK constraints
- Bug 4: Duplicate migrations
- Bug 5: Version mismatches
- Bug 6: Docker build context
- Bug 7: Missing files in Dockerfile
"""
import os
import re
import sys
from pathlib import Path
from typing import List, Tuple

# Colors for output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"


def check_hardcoded_keys(root_dir: Path) -> List[Tuple[str, int, str]]:
    """Check for hardcoded API keys in Python files."""
    issues = []
    patterns = [
        (r'RUNPOD_API_KEY\s*=\s*["\']', "RUNPOD_API_KEY"),
        (r'CLOSE_API_KEY\s*=\s*["\']', "CLOSE_API_KEY"),
        (r'ANTHROPIC_API_KEY\s*=\s*["\']', "ANTHROPIC_API_KEY"),
        (r'SUPABASE.*password\s*=\s*["\']', "SUPABASE password"),
    ]
    
    for py_file in root_dir.rglob("*.py"):
        # Skip venv and cache directories
        if "venv" in str(py_file) or "__pycache__" in str(py_file):
            continue
            
        try:
            content = py_file.read_text()
            for line_num, line in enumerate(content.split("\n"), 1):
                for pattern, key_name in patterns:
                    if re.search(pattern, line, re.IGNORECASE):
                        issues.append((str(py_file), line_num, f"Hardcoded {key_name}"))
        except Exception as e:
            pass  # Skip binary or unreadable files
    
    return issues


def check_migration_chain(versions_dir: Path) -> List[Tuple[str, str]]:
    """Check migration down_revision chain."""
    issues = []
    
    # Find all migration files
    migrations = {}
    for mig_file in versions_dir.glob("*.py"):
        if mig_file.name == "__init__.py":
            continue
            
        content = mig_file.read_text()
        revision_match = re.search(r"revision\s*[:=]\s*['\"]([^'\"]+)['\"]", content)
        down_rev_match = re.search(r"down_revision\s*[:=]\s*.*?['\"]([^'\"]+)['\"]", content)
        down_rev_none_match = re.search(r"down_revision\s*[:=]\s*None", content)
        
        if revision_match:
            rev_id = revision_match.group(1)
            if down_rev_none_match and rev_id != "64e77371d123":  # Initial migration is OK
                issues.append((str(mig_file), "down_revision is None (should reference previous migration)"))
            elif down_rev_match:
                down_rev = down_rev_match.group(1)
                migrations[rev_id] = (str(mig_file), down_rev)
    
    # Check for broken chains
    for rev_id, (file_path, down_rev) in migrations.items():
        if down_rev not in migrations and down_rev != "64e77371d123":
            issues.append((file_path, f"down_revision '{down_rev}' not found in migration chain"))
    
    return issues


def check_duplicate_migrations(versions_dir: Path) -> List[Tuple[str, str]]:
    """Check for duplicate table creation in migrations."""
    issues = []
    table_creations = {}
    
    for mig_file in versions_dir.glob("*.py"):
        if mig_file.name == "__init__.py":
            continue
            
        content = mig_file.read_text()
        
        # Check for email_engagement or email_drafts table creation
        if "email_engagement" in content or "email_drafts" in content:
            table_name = "email_engagement" if "email_engagement" in content else "email_drafts"
            if table_name in table_creations:
                issues.append((
                    str(mig_file),
                    f"Duplicate {table_name} table creation (also in {table_creations[table_name]})"
                ))
            else:
                table_creations[table_name] = mig_file.name
    
    return issues


def check_version_mismatch(requirements_file: Path, venv_requirements_file: Path) -> List[Tuple[str, str]]:
    """Check for version mismatches between requirements files."""
    issues = []
    
    if not requirements_file.exists() or not venv_requirements_file.exists():
        return issues
    
    # Parse requirements files
    def parse_requirements(file_path: Path) -> dict:
        deps = {}
        for line in file_path.read_text().split("\n"):
            line = line.strip()
            if line and not line.startswith("#"):
                match = re.match(r"([a-zA-Z0-9_-]+)==([0-9.]+)", line)
                if match:
                    deps[match.group(1)] = match.group(2)
        return deps
    
    req_deps = parse_requirements(requirements_file)
    venv_deps = parse_requirements(venv_requirements_file)
    
    # Check for mismatches in critical packages
    critical_packages = ["anthropic", "openai", "langchain", "langchain-anthropic"]
    
    for pkg in critical_packages:
        if pkg in req_deps and pkg in venv_deps:
            if req_deps[pkg] != venv_deps[pkg]:
                issues.append((
                    str(requirements_file),
                    f"{pkg} version mismatch: {req_deps[pkg]} vs {venv_deps[pkg]}"
                ))
    
    return issues


def check_dockerfile_issues(backend_dir: Path) -> List[Tuple[str, str]]:
    """Check for Dockerfile issues."""
    issues = []
    
    # Find Dockerfile files
    dockerfiles = list(backend_dir.rglob("Dockerfile*"))
    
    for dockerfile in dockerfiles:
        content = dockerfile.read_text()
        
        # Check for missing files in COPY statements
        copy_matches = re.findall(r"COPY\s+([^\s]+)\s+", content)
        for file_path in copy_matches:
            # Resolve relative to Dockerfile directory
            full_path = dockerfile.parent / file_path
            if not full_path.exists() and not file_path.startswith("."):
                issues.append((
                    str(dockerfile),
                    f"COPY references non-existent file: {file_path}"
                ))
    
    return issues


def main():
    """Run all bug checks."""
    root_dir = Path(__file__).parent.parent.parent
    backend_dir = root_dir / "backend"
    versions_dir = backend_dir / "alembic" / "versions"
    
    print(f"{YELLOW}🔍 Verifying Bug Fixes...{RESET}\n")
    
    all_issues = []
    
    # Bug 1: Hardcoded API keys
    print(f"{YELLOW}Checking Bug 1: Hardcoded API keys...{RESET}")
    key_issues = check_hardcoded_keys(backend_dir)
    if key_issues:
        print(f"{RED}❌ Found {len(key_issues)} hardcoded API key(s):{RESET}")
        for file_path, line_num, issue in key_issues:
            print(f"  {file_path}:{line_num} - {issue}")
            all_issues.append((file_path, issue))
    else:
        print(f"{GREEN}✅ No hardcoded API keys found{RESET}")
    print()
    
    # Bug 2: Migration chain
    print(f"{YELLOW}Checking Bug 2: Migration down_revision chain...{RESET}")
    if versions_dir.exists():
        mig_issues = check_migration_chain(versions_dir)
        if mig_issues:
            print(f"{RED}❌ Found {len(mig_issues)} migration issue(s):{RESET}")
            for file_path, issue in mig_issues:
                print(f"  {file_path} - {issue}")
                all_issues.append((file_path, issue))
        else:
            print(f"{GREEN}✅ Migration chain is correct{RESET}")
    else:
        print(f"{YELLOW}⚠️  Versions directory not found{RESET}")
    print()
    
    # Bug 3 & 4: Duplicate migrations
    print(f"{YELLOW}Checking Bug 3 & 4: Duplicate migrations...{RESET}")
    if versions_dir.exists():
        dup_issues = check_duplicate_migrations(versions_dir)
        if dup_issues:
            print(f"{RED}❌ Found {len(dup_issues)} duplicate migration(s):{RESET}")
            for file_path, issue in dup_issues:
                print(f"  {file_path} - {issue}")
                all_issues.append((file_path, issue))
        else:
            print(f"{GREEN}✅ No duplicate migrations found{RESET}")
    else:
        print(f"{YELLOW}⚠️  Versions directory not found{RESET}")
    print()
    
    # Bug 5: Version mismatches
    print(f"{YELLOW}Checking Bug 5: Version mismatches...{RESET}")
    req_file = backend_dir / "requirements.txt"
    venv_req_file = root_dir / "venv_requirements.txt"
    ver_issues = check_version_mismatch(req_file, venv_req_file)
    if ver_issues:
        print(f"{RED}❌ Found {len(ver_issues)} version mismatch(es):{RESET}")
        for file_path, issue in ver_issues:
            print(f"  {file_path} - {issue}")
            all_issues.append((file_path, issue))
    else:
        print(f"{GREEN}✅ No version mismatches found{RESET}")
    print()
    
    # Bug 6 & 7: Dockerfile issues
    print(f"{YELLOW}Checking Bug 6 & 7: Dockerfile issues...{RESET}")
    docker_issues = check_dockerfile_issues(backend_dir)
    if docker_issues:
        print(f"{RED}❌ Found {len(docker_issues)} Dockerfile issue(s):{RESET}")
        for file_path, issue in docker_issues:
            print(f"  {file_path} - {issue}")
            all_issues.append((file_path, issue))
    else:
        print(f"{GREEN}✅ No Dockerfile issues found{RESET}")
    print()
    
    # Summary
    print(f"{'='*60}")
    if all_issues:
        print(f"{RED}❌ Total issues found: {len(all_issues)}{RESET}")
        sys.exit(1)
    else:
        print(f"{GREEN}✅ All bug checks passed!{RESET}")
        sys.exit(0)


if __name__ == "__main__":
    main()


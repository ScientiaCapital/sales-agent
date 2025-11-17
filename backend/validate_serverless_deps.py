#!/usr/bin/env python3
"""
Validate that requirements-serverless.txt has all dependencies needed by handler.py
"""
import ast
import sys
from pathlib import Path
from typing import Set, Dict

def extract_imports_from_file(filepath: Path) -> Set[str]:
    """Extract all import statements from a Python file."""
    imports = set()
    try:
        with open(filepath) as f:
            tree = ast.parse(f.read())

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name.split('.')[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module.split('.')[0])
    except Exception as e:
        print(f"Warning: Could not parse {filepath}: {e}")

    return imports

def get_package_name(requirement_line: str) -> str:
    """Extract package name from requirement line."""
    # Remove comments
    line = requirement_line.split('#')[0].strip()
    if not line:
        return None

    # Extract package name (before ==, >=, etc.)
    for sep in ['==', '>=', '<=', '~=', '!=', '<', '>']:
        if sep in line:
            return line.split(sep)[0].strip()
    return line.strip()

def parse_requirements(filepath: Path) -> Dict[str, str]:
    """Parse requirements file into dict of package -> full line."""
    packages = {}
    with open(filepath) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                pkg = get_package_name(line)
                if pkg:
                    packages[pkg.lower()] = line
    return packages

def main():
    backend_dir = Path(__file__).parent

    # Files to check for imports
    files_to_check = [
        backend_dir / 'handler.py',
        backend_dir / 'social_intelligence_runner.py',
        backend_dir / 'check_email_engagement.py',
    ]

    # Extract all imports
    all_imports = set()
    for filepath in files_to_check:
        if filepath.exists():
            imports = extract_imports_from_file(filepath)
            all_imports.update(imports)
            print(f"Imports from {filepath.name}: {sorted(imports)}")

    print(f"\n{'='*80}")
    print(f"All unique imports: {sorted(all_imports)}")
    print(f"{'='*80}\n")

    # Parse requirements files
    main_reqs = parse_requirements(backend_dir / 'requirements.txt')
    serverless_reqs = parse_requirements(backend_dir / 'requirements-serverless.txt')

    # Map import names to package names (some differ)
    import_to_package = {
        'bs4': 'beautifulsoup4',
        'dotenv': 'python-dotenv',
        'dateutil': 'python-dateutil',
        'sklearn': 'scikit-learn',
        'PIL': 'pillow',
    }

    # Check for missing packages
    missing = []
    for imp in all_imports:
        # Skip standard library
        if imp in ['os', 'sys', 'json', 'asyncio', 'logging', 'datetime', 'typing',
                   'time', 'traceback', 'pathlib', 'collections', 're', 'io']:
            continue

        # Map to package name
        pkg = import_to_package.get(imp, imp).lower()

        # Check if in serverless requirements
        if pkg not in serverless_reqs:
            # Check if it's in main requirements
            if pkg in main_reqs:
                missing.append((pkg, main_reqs[pkg]))
                print(f"❌ MISSING: {pkg} (used in code, in main requirements, NOT in serverless)")
            else:
                print(f"⚠️  WARNING: {pkg} imported but not in ANY requirements file")

    if missing:
        print(f"\n{'='*80}")
        print("MISSING PACKAGES IN SERVERLESS REQUIREMENTS:")
        print(f"{'='*80}")
        for pkg, req_line in missing:
            print(f"  {req_line}")
        print(f"\nAdd these {len(missing)} packages to requirements-serverless.txt")
        sys.exit(1)
    else:
        print(f"\n✅ All imported packages are in requirements-serverless.txt")
        sys.exit(0)

if __name__ == '__main__':
    main()

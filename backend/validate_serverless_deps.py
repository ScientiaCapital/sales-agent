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
    """Extract package name from requirement line, stripping extras like [binary]."""
    # Remove comments
    line = requirement_line.split('#')[0].strip()
    if not line:
        return None

    # Extract package name (before ==, >=, etc.)
    for sep in ['==', '>=', '<=', '~=', '!=', '<', '>']:
        if sep in line:
            pkg = line.split(sep)[0].strip()
            # Strip package extras like [binary], [fastapi], [standard]
            if '[' in pkg:
                pkg = pkg.split('[')[0].strip()
            return pkg

    # No version specifier found, strip extras from bare package name
    pkg = line.strip()
    if '[' in pkg:
        pkg = pkg.split('[')[0].strip()
    return pkg

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

    # Files to check for imports - start with top-level files
    files_to_check = [
        backend_dir / 'handler.py',
        backend_dir / 'social_intelligence_runner.py',
        backend_dir / 'check_email_engagement.py',
    ]

    # Add all Python files in app/ directory recursively
    app_dir = backend_dir / 'app'
    if app_dir.exists():
        files_to_check.extend(app_dir.rglob('*.py'))

    # Extract all imports
    all_imports = set()
    file_count = 0
    for filepath in files_to_check:
        if filepath.exists() and filepath.name != '__init__.py':
            imports = extract_imports_from_file(filepath)
            if imports:
                all_imports.update(imports)
                file_count += 1

    print(f"Scanned {file_count} Python files for imports")

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
        'yaml': 'pyyaml',
        'cv2': 'opencv-python',
        'skimage': 'scikit-image',
        'langchain_anthropic': 'langchain-anthropic',
        'langchain_cerebras': 'langchain-cerebras',
        'langchain_community': 'langchain-community',
        'langchain_core': 'langchain-core',
        'langchain_huggingface': 'langchain-huggingface',
        'langchain_ollama': 'langchain-ollama',
        'langchain_openai': 'langchain-openai',
        'langchain_postgres': 'langchain-postgres',
        'langchain_text_splitters': 'langchain-text-splitters',
        'langchain_google_genai': 'langchain-google-genai',
        'pydantic_settings': 'pydantic-settings',
        'sentry_sdk': 'sentry-sdk',
        'sentence_transformers': 'sentence-transformers',
        'docx': 'python-docx',
        'PyPDF2': 'pypdf2',
    }

    # Extended standard library list (Python 3.11+)
    stdlib = {
        'os', 'sys', 'json', 'asyncio', 'logging', 'datetime', 'typing',
        'time', 'traceback', 'pathlib', 'collections', 're', 'io', 'uuid',
        'abc', 'enum', 'dataclasses', 'functools', 'itertools', 'operator',
        'contextlib', 'warnings', 'copy', 'hashlib', 'hmac', 'secrets',
        'base64', 'binascii', 'struct', 'codecs', 'socket', 'ssl', 'email',
        'urllib', 'http', 'html', 'xml', 'csv', 'configparser', 'argparse',
        'tempfile', 'shutil', 'glob', 'subprocess', 'threading', 'multiprocessing',
        'queue', 'signal', 'inspect', 'ast', 'importlib', 'pkgutil', 'platform',
        'concurrent', 'decimal', 'random', 'math', 'difflib', 'typing_extensions'
    }

    # Track which packages are actually used
    used_packages = set()

    # Local modules (part of the app, not external packages)
    local_modules = {
        'app', 'database', 'providers', 'base', 'base_provider', 'base_router',
        'circuit_breaker', 'cost_router', 'task_router', 'retry_handler',
        'analysis_agent', 'search_agent', 'memory', 'subagents',
        'ai_cost_optimizer', 'cartesia_service', 'check_email_engagement',
        'social_intelligence_runner'
    }

    # Check for missing packages
    missing = []
    for imp in all_imports:
        # Skip standard library
        if imp in stdlib:
            continue

        # Skip local modules
        if imp in local_modules:
            continue

        # Map to package name
        pkg = import_to_package.get(imp, imp).lower()
        used_packages.add(pkg)

        # Check if in serverless requirements
        if pkg not in serverless_reqs:
            # Check if it's in main requirements
            if pkg in main_reqs:
                missing.append((pkg, main_reqs[pkg]))
                print(f"❌ MISSING: {pkg} (used in code, in main requirements, NOT in serverless)")
            else:
                print(f"⚠️  WARNING: {pkg} imported but not in ANY requirements file")

    # Check for unused packages in serverless requirements
    unused = []
    for pkg in serverless_reqs.keys():
        if pkg not in used_packages:
            unused.append(pkg)

    # Report findings
    if missing:
        print(f"\n{'='*80}")
        print("MISSING PACKAGES IN SERVERLESS REQUIREMENTS:")
        print(f"{'='*80}")
        for pkg, req_line in missing:
            print(f"  {req_line}")
        print(f"\nAdd these {len(missing)} packages to requirements-serverless.txt")

    if unused:
        print(f"\n{'='*80}")
        print(f"UNUSED PACKAGES IN SERVERLESS REQUIREMENTS ({len(unused)}):")
        print(f"{'='*80}")
        for pkg in sorted(unused):
            print(f"  ⚠️  {pkg} - Not imported anywhere (can potentially be removed)")

    if missing:
        sys.exit(1)
    else:
        print(f"\n✅ All imported packages are in requirements-serverless.txt")
        if not unused:
            print(f"✅ No unused packages detected")
        sys.exit(0)

if __name__ == '__main__':
    main()

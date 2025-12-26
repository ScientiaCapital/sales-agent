#!/usr/bin/env python3
"""Inline vlm-ai-core modules to target projects.

Copies vlm_core modules to target project's lib/ directory for
self-contained deployment without cross-repo dependencies.

Usage:
    python scripts/inline_to_project.py /path/to/project --modules providers preprocessing
    python scripts/inline_to_project.py /path/to/project --dry-run
    python scripts/inline_to_project.py /path/to/project --force

NOTE: For middleware (circuit breaker, retry), use lang-core instead:
    python ~/lang-core/scripts/inline_to_project.py /path/to/project --modules middleware
"""

import argparse
import shutil
import sys
from pathlib import Path

# Source directory for Python package
PYTHON_PKG = "packages/python/vlm_core"

# Available modules to inline
AVAILABLE_MODULES = {
    "providers": f"{PYTHON_PKG}/providers",
    "vision": f"{PYTHON_PKG}/providers",  # Alias
    "preprocessing": f"{PYTHON_PKG}/preprocessing",
    "types": f"{PYTHON_PKG}/types",
    # NOTE: middleware should come from lang-core, not here
    # "middleware": f"{PYTHON_PKG}/middleware",  # DEPRECATED - use lang-core
}

# Shared modules (cross-language)
SHARED_MODULES = {
    "agents": "shared/agents",
    "audit": "shared/audit",
    "config": "shared/config",
}

# Core files always needed
CORE_FILES = [
    f"{PYTHON_PKG}/__init__.py",
    f"{PYTHON_PKG}/exceptions.py",
]


def inline_modules(
    target_project: Path,
    modules: list[str],
    include_shared: bool = False,
    dry_run: bool = False,
    force: bool = False,
) -> None:
    """Copy selected vlm_core modules to target project."""
    source_root = Path(__file__).parent.parent
    target_lib = target_project / "lib" / "vlm_core"

    # Check if target exists
    if target_lib.exists() and not force:
        print(f"ERROR: {target_lib} already exists. Use --force to overwrite.")
        sys.exit(1)

    # Resolve modules
    resolved_modules = set()
    for mod in modules:
        if mod in AVAILABLE_MODULES:
            resolved_modules.add(AVAILABLE_MODULES[mod])
        elif mod in SHARED_MODULES and include_shared:
            resolved_modules.add(SHARED_MODULES[mod])
        elif mod == "middleware":
            print("WARNING: middleware should be inlined from lang-core, not vlm-ai-core")
            print("         Run: python ~/lang-core/scripts/inline_to_project.py --modules middleware")
        else:
            print(f"WARNING: Unknown module '{mod}', skipping")

    if not resolved_modules:
        print("ERROR: No valid modules specified")
        print(f"Available: {', '.join(AVAILABLE_MODULES.keys())}")
        if include_shared:
            print(f"Shared: {', '.join(SHARED_MODULES.keys())}")
        sys.exit(1)

    print(f"Source: {source_root}")
    print(f"Target: {target_lib}")
    print(f"Modules: {', '.join(resolved_modules)}")
    print()

    if dry_run:
        print("DRY RUN - No files will be copied")
        print()

    # Create target directory
    if not dry_run:
        target_lib.mkdir(parents=True, exist_ok=True)

    # Copy core files
    print("Copying core files:")
    for core_file in CORE_FILES:
        src = source_root / core_file
        if src.exists():
            # Map to target structure
            dst_file = core_file.replace(f"{PYTHON_PKG}/", "")
            dst = target_lib / dst_file
            print(f"  {dst_file}")
            if not dry_run:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)

    # Copy modules
    print("\nCopying modules:")
    for module_path in resolved_modules:
        src = source_root / module_path

        # Determine target path
        if module_path.startswith(PYTHON_PKG):
            # Python package module
            rel_path = module_path.replace(f"{PYTHON_PKG}/", "")
            dst = target_lib / rel_path
        else:
            # Shared module
            dst = target_lib / module_path.split("/")[-1]

        if src.exists() and src.is_dir():
            print(f"  {module_path}/")
            if not dry_run:
                if dst.exists():
                    shutil.rmtree(dst)
                shutil.copytree(src, dst)
        else:
            print(f"  WARNING: {module_path} not found")

    print()
    if dry_run:
        print("DRY RUN complete. Run without --dry-run to copy files.")
    else:
        print("Done! VLM modules inlined to project.")
        print()
        print("Usage in your project:")
        print("  from lib.vlm_core.providers import QwenVL, GeminiVision")
        print("  from lib.vlm_core.preprocessing import ImageProcessor")
        print()
        print("IMPORTANT: For middleware, also inline from lang-core:")
        print("  python ~/lang-core/scripts/inline_to_project.py . --modules middleware")


def main():
    parser = argparse.ArgumentParser(
        description="Inline vlm-ai-core modules to target project",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "target",
        type=Path,
        help="Target project directory",
    )
    parser.add_argument(
        "--modules",
        nargs="+",
        default=["providers", "preprocessing", "types"],
        help=f"Modules to copy. Available: {', '.join(AVAILABLE_MODULES.keys())}",
    )
    parser.add_argument(
        "--include-shared",
        action="store_true",
        help="Also include shared modules (agents, audit, config)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be copied without copying",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing lib/vlm_core directory",
    )

    args = parser.parse_args()

    if not args.target.exists():
        print(f"ERROR: Target directory does not exist: {args.target}")
        sys.exit(1)

    inline_modules(
        target_project=args.target.resolve(),
        modules=args.modules,
        include_shared=args.include_shared,
        dry_run=args.dry_run,
        force=args.force,
    )


if __name__ == "__main__":
    main()

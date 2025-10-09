#!/usr/bin/env python3
"""
Build complete Mintlify documentation site.

This script:
1. Copies docs/mintlify-src/* to docs/target/
2. Runs mintlifier to generate SDK documentation into docs/target/
3. Results in a complete, deployable documentation site
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def find_pixeltable_repo() -> Path:
    """Find the pixeltable repository root."""
    # Assume we're running from within pixeltable repo via conda
    cwd = Path.cwd()

    # Check if we're already in pixeltable repo
    if (cwd / 'docs' / 'mintlify-src').exists():
        return cwd

    # Walk up to find it
    current = cwd
    for _ in range(5):  # Don't go up more than 5 levels
        if (current / 'docs' / 'mintlify-src').exists():
            return current
        current = current.parent

    raise FileNotFoundError(
        "Could not find pixeltable repository. "
        "Make sure you're running this from within the pixeltable repo, "
        "or that docs/mintlify-src/ exists."
    )


def build_mintlify(target: str) -> None:
    """
    Build Mintlify documentation site.

    Args:
        target: Build target - 'local', 'dev', 'stage', or 'prod'
    """
    print(f"Building Mintlify documentation for target: {target}")

    # Find pixeltable repo
    repo_root = find_pixeltable_repo()
    print(f"Found pixeltable repository at: {repo_root}")

    source_dir = repo_root / 'docs' / 'mintlify-src'
    target_dir = repo_root / 'docs' / 'target'
    opml_file = repo_root / 'docs' / 'public_api.opml'

    # Verify source exists
    if not source_dir.exists():
        raise FileNotFoundError(f"Source directory not found: {source_dir}")

    if not opml_file.exists():
        raise FileNotFoundError(f"OPML file not found: {opml_file}")

    # Step 1: Clean and create target directory
    print(f"\n📁 Preparing target directory: {target_dir}")
    if target_dir.exists():
        shutil.rmtree(target_dir)
    target_dir.mkdir(parents=True)

    # Step 2: Copy mintlify-src to target
    print(f"\n📋 Copying source files from {source_dir} to {target_dir}")

    # Copy all contents of mintlify-src to target
    for item in source_dir.iterdir():
        if item.name.startswith('.'):
            continue  # Skip hidden files

        dest = target_dir / item.name
        if item.is_dir():
            shutil.copytree(item, dest)
            print(f"   Copied directory: {item.name}/")
        else:
            shutil.copy2(item, dest)
            print(f"   Copied file: {item.name}")

    # Step 3: Run mintlifier to generate SDK docs
    # Mintlifier now writes directly to docs/target/sdk/latest and updates docs/target/docs.json
    print(f"\n🔨 Running mintlifier to generate SDK documentation...")
    print(f"   OPML: {opml_file}")
    print(f"   Output: {target_dir}")

    try:
        # Run mintlifier - it writes directly to target
        result = subprocess.run(
            ['mintlifier'],
            cwd=str(repo_root),  # Run from repo root
            capture_output=True,
            text=True,
            check=True
        )
        print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
    except subprocess.CalledProcessError as e:
        print(f"❌ Error running mintlifier:", file=sys.stderr)
        print(e.stdout, file=sys.stderr)
        print(e.stderr, file=sys.stderr)
        raise

    print(f"\n✅ Documentation build complete!")
    print(f"   Output directory: {target_dir}")
    print(f"\n   To preview locally, run:")
    print(f"   cd {target_dir} && npx mintlify dev")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Build complete Mintlify documentation site'
    )
    parser.add_argument(
        '--target',
        choices=['local', 'dev', 'stage', 'prod'],
        default='local',
        help='Build target (default: local)'
    )

    args = parser.parse_args()

    try:
        build_mintlify(args.target)
    except Exception as e:
        print(f"\n❌ Build failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()

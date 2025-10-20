#!/usr/bin/env python3
"""
Build complete Mintlify documentation site.

This script:
1. Copies docs/mintlify/* to docs/target/
2. Runs mintlifier to generate SDK documentation into docs/target/
3. Results in a complete, deployable documentation site
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from doctools.config import get_mintlify_source_path, get_mintlify_target_path


def deploy_docs(target_dir: Path, target: str) -> None:
    """
    Deploy documentation to pixeltable-docs-www repository.

    Args:
        target_dir: Directory containing built documentation
        target: Deployment target - 'dev', 'stage', or 'prod'
    """
    # Map target to branch name
    branch_map = {
        'dev': 'dev',
        'stage': 'stage',
        'prod': 'main'
    }
    branch = branch_map[target]

    print(f"\n📤 Deploying documentation to {target} environment...")
    print(f"   Branch: {branch}")

    # Create temporary directory for the docs repo
    import tempfile
    with tempfile.TemporaryDirectory() as tmp_dir:
        docs_repo_dir = Path(tmp_dir) / 'pixeltable-docs-www'

        # Clone the docs repository
        print(f"\n📥 Cloning pixeltable-docs-www repository...")
        result = subprocess.run(
            ['git', 'clone', '-b', branch, 'https://github.com/pixeltable/pixeltable-docs-www.git', str(docs_repo_dir)],
            capture_output=True,
            text=True
        )

        # If branch doesn't exist, clone main and create the branch
        if result.returncode != 0:
            print(f"   Branch {branch} doesn't exist, creating it...")
            subprocess.run(
                ['git', 'clone', 'https://github.com/pixeltable/pixeltable-docs-www.git', str(docs_repo_dir)],
                capture_output=True,
                text=True,
                check=True
            )
            subprocess.run(
                ['git', 'checkout', '-b', branch],
                cwd=str(docs_repo_dir),
                capture_output=True,
                text=True,
                check=True
            )

        # Remove all existing files (except .git)
        print(f"\n🧹 Cleaning target repository...")
        for item in docs_repo_dir.iterdir():
            if item.name != '.git':
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()

        # Copy new documentation
        print(f"\n📋 Copying documentation files...")
        for item in target_dir.iterdir():
            dest = docs_repo_dir / item.name
            if item.is_dir():
                shutil.copytree(item, dest)
                print(f"   Copied: {item.name}/")
            else:
                shutil.copy2(item, dest)
                print(f"   Copied: {item.name}")

        # Commit and push
        print(f"\n💾 Committing changes...")
        subprocess.run(['git', 'add', '-A'], cwd=str(docs_repo_dir), check=True)

        # Check if there are changes to commit
        result = subprocess.run(
            ['git', 'diff', '--staged', '--quiet'],
            cwd=str(docs_repo_dir)
        )

        if result.returncode != 0:  # There are changes
            subprocess.run(
                ['git', 'commit', '-m', f'Deploy documentation to {target}\n\n🤖 Auto-deployed from pixeltable/pixeltable'],
                cwd=str(docs_repo_dir),
                check=True
            )

            print(f"\n🚀 Pushing to {branch} branch...")
            subprocess.run(
                ['git', 'push', 'origin', branch],
                cwd=str(docs_repo_dir),
                check=True
            )

            # Map target to preview URL
            preview_urls = {
                'dev': 'https://pixeltable-dev.mintlify.app/',
                'stage': 'https://pixeltable-stage.mintlify.app/',
                'prod': 'https://docs.pixeltable.com'
            }
            preview_url = preview_urls.get(target, '')

            print(f"\n✅ Documentation deployed successfully to {target}!")
            if preview_url:
                print(f"   View preview at: {preview_url}")
        else:
            print(f"\n   No changes to deploy.")


def find_pixeltable_repo() -> Path:
    """Find the pixeltable repository root."""
    # Assume we're running from within pixeltable repo via conda
    cwd = Path.cwd()

    # Check if we're already in pixeltable repo
    if get_mintlify_source_path(cwd).exists():
        return cwd

    # Walk up to find it
    current = cwd
    for _ in range(5):  # Don't go up more than 5 levels
        if get_mintlify_source_path(current).exists():
            return current
        current = current.parent

    raise FileNotFoundError(
        "Could not find pixeltable repository. "
        "Make sure you're running this from within the pixeltable repo, "
        "or that docs/mintlify/ exists."
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

    source_dir = get_mintlify_source_path(repo_root)
    target_dir = get_mintlify_target_path(repo_root)
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

    # Step 2: Copy mintlify source to target
    print(f"\n📋 Copying source files from {source_dir} to {target_dir}")

    # Copy all contents of mintlify to target
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
        # For stage/prod targets, hide errors from generated docs
        mintlifier_cmd = ['mintlifier']
        if target in ['stage', 'prod']:
            mintlifier_cmd.append('--no-errors')

        result = subprocess.run(
            mintlifier_cmd,
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

    # Deploy if target is dev, stage, or prod
    if target in ['dev', 'stage', 'prod']:
        deploy_docs(target_dir, target)
    else:
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

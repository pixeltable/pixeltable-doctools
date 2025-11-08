#!/usr/bin/env python3
"""
Deploy documentation to dev environment for pre-release validation.

This script is for PRE-RELEASE validation and differs from deploy_docs_stage.py:
- Builds from CURRENT WORKING DIRECTORY (not a git tag)
- Does NOT require a version number
- Does NOT use --no-errors flag when running mintlifier
- Shows all MDX parsing errors so they can be reviewed before release
- Broken pages still display in Mintlify (with errors visible)
- Deploys to pixeltable-docs-www/dev branch

Workflow:
1. Run this BEFORE creating a release tag
2. Review docs at https://pixeltable-dev.mintlify.app/
3. Fix any MDX errors in docstrings
4. Create release tag
5. Run `make docs-stage VERSION=x.y.z` to deploy clean docs to staging
"""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from time import sleep
from typing import Any

from doctools.build_mintlify.build_mintlify import build_mintlify
from doctools.config import get_mintlify_source_path


def deploy(pxt_repo_dir: Path, temp_dir: Path, branch: str) -> None:
    """
    Deploy generated docs.

    Args:
        output_dir: Directory containing generated docs
    """
    docs_target_dir = pxt_repo_dir / 'docs' / 'target'
    if not docs_target_dir.exists():
        print(f"Error: Docs target directory {docs_target_dir} does not exist. Please build the docs first.")
        sys.exit(1)

    print(f"\nDeploying to {branch!r} branch ...")

    docs_repo_dir = Path(temp_dir) / 'pixeltable-docs-www'

    # Clone the docs repository
    print(f"   Cloning into {docs_repo_dir} ...")
    subprocess.run(
        ('git', 'clone', '-b', branch, 'https://github.com/pixeltable/pixeltable-docs-www.git', str(docs_repo_dir)),
        capture_output=True,
        text=True,
        check=True
    )

    # Clean existing repo dir
    for item in docs_repo_dir.iterdir():
        if item.name.startswith('.git'):
            continue  # Skip .git directory
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()

    # Copy all docs from output
    # TODO: What if there are files in the repo that don't exist in the output?
    print(f"   Copying documentation files...")
    for item in docs_target_dir.iterdir():
        dest = docs_repo_dir / item.name
        print(f"  {item} -> {dest}")
        if item.is_dir():
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(item, dest)
        else:
            shutil.copy2(item, dest)

    # Add changes to local repo
    subprocess.run(('git', 'add', '-A'), cwd=str(docs_repo_dir), check=True)
    result = subprocess.run(
        ('git', 'diff', '--staged', '--quiet'),
        cwd=str(docs_repo_dir)
    )

    if result.returncode != 0:  # There are changes
        print(f"   Committing changes...")
        subprocess.run(
            ('git', 'commit', '-m', 'Deploy dev documentation for pre-release validation'),
            cwd=str(docs_repo_dir),
            check=True
        )
        print(f"   Pushing to {branch!r} branch ...")
        subprocess.run(
            ('git', 'push', 'origin', 'dev'),
            cwd=str(docs_repo_dir),
            check=True
        )
        print(f"   Deployed successfully")
    else:
        print(f"   No changes to deploy")


def main():
    """Main entry point."""

    print(f"Deploying documentation to dev for pre-release validation")

    try:
        import pixeltable as pxt

    except ImportError:
        print(f"Error: `pixeltable` package not found.")
        sys.exit(1)

    # Get current working dir
    pxt_repo_dir = Path(pxt.__file__).parent.parent.resolve()
    if pxt_repo_dir != Path.cwd():
        print(f"Error: Please run this script from the pixeltable repository root.")
        sys.exit(1)

    with tempfile.TemporaryDirectory() as temp_dir:
        deploy(pxt_repo_dir, temp_dir, 'dev')

    print(f"\nDeployment complete.")
    print(f"   View at: https://pixeltable-dev.mintlify.app/sdk/latest")
    print(f"   Note: This deployment shows ALL MDX errors for review")
    print(f"   Fix any errors in docstrings before creating a release tag")


if __name__ == '__main__':
    main()

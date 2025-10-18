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

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def find_pixeltable_repo() -> Path:
    """
    Find the pixeltable repository from current working directory.

    Returns:
        Path to pixeltable repository

    Raises:
        RuntimeError: If not in a pixeltable repository
    """
    cwd = Path.cwd()

    # Check if we're in pixeltable repo
    if (cwd / 'pixeltable' / '__init__.py').exists():
        return cwd

    # Walk up to find it
    current = cwd
    for _ in range(5):
        if (current / 'pixeltable' / '__init__.py').exists():
            return current
        current = current.parent

    raise RuntimeError(
        "Could not find pixeltable repository. "
        "Please run this command from the pixeltable repository root."
    )


def create_venv_and_install(temp_dir: Path, pixeltable_dir: Path) -> Path:
    """
    Create virtual environment and install pixeltable + doctools from current working directory.

    Args:
        temp_dir: Temporary directory
        pixeltable_dir: Path to current pixeltable repository

    Returns:
        Path to venv directory
    """
    print(f"\n⚡ Creating virtual environment...")
    venv_dir = temp_dir / 'venv'

    result = subprocess.run(
        [sys.executable, '-m', 'venv', str(venv_dir)],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        raise RuntimeError(f"Failed to create venv: {result.stderr}")

    # Get pip and python paths
    pip_path = venv_dir / 'bin' / 'pip'

    print(f"   Installing pixeltable from current directory: {pixeltable_dir}...")
    result = subprocess.run(
        [str(pip_path), 'install', '-q', str(pixeltable_dir)],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        raise RuntimeError(f"Failed to install pixeltable: {result.stderr}")

    print(f"   Installing pixeltable-doctools...")
    result = subprocess.run(
        [str(pip_path), 'install', '-q', '--no-cache-dir', '--force-reinstall', 'git+https://github.com/pixeltable/pixeltable-doctools.git'],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        raise RuntimeError(f"Failed to install pixeltable-doctools: {result.stderr}")

    print(f"   💯 Environment ready")
    return venv_dir


def generate_docs(venv_dir: Path, pixeltable_dir: Path, output_dir: Path):
    """
    Generate SDK documentation from current working directory.

    Args:
        venv_dir: Path to virtual environment
        pixeltable_dir: Path to current pixeltable repository
        output_dir: Where to output generated docs
    """
    print(f"\n🔥 Generating documentation from current working directory...")

    # Create output structure - use 'latest' so navigation works
    sdk_output = output_dir / 'sdk' / 'latest'
    sdk_output.mkdir(parents=True)

    # Use docs structure from current repo
    mintlify_src = pixeltable_dir / 'docs' / 'mintlify-src'
    opml_path = pixeltable_dir / 'docs' / 'public_api.opml'

    if not mintlify_src.exists():
        raise RuntimeError(
            f"mintlify-src not found at {mintlify_src}\n"
            f"Please run this command from the pixeltable repository."
        )

    # Create docs/target directory
    target_dir = pixeltable_dir / 'docs' / 'target'
    target_dir.mkdir(parents=True, exist_ok=True)

    # Copy base documentation to output
    print(f"   Copying base documentation to output...")
    for item in mintlify_src.iterdir():
        if item.name.startswith('.'):
            continue
        dest = output_dir / item.name
        if item.is_dir():
            shutil.copytree(item, dest)
        else:
            shutil.copy2(item, dest)

    # Run mintlifier using venv's Python (WITHOUT --no-errors to show all issues)
    mintlifier_path = venv_dir / 'bin' / 'mintlifier'

    print(f"   Running mintlifier (with errors visible for review)...")
    result = subprocess.run(
        [str(mintlifier_path)],
        cwd=str(pixeltable_dir),
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        # Still raise error, but errors will be in generated MDX
        print(f"   Warning: Mintlifier completed with errors (check dev site for details)")
        print(f"   {result.stderr}")

    # Copy newly generated SDK docs
    # Mintlifier generates to target/sdk/latest, copy that to our latest output
    src_sdk = pixeltable_dir / 'docs' / 'target' / 'sdk' / 'latest'
    if src_sdk.exists():
        print(f"   Copying newly generated docs to sdk/latest/...")
        shutil.copytree(src_sdk, sdk_output, dirs_exist_ok=True)

    # Copy docs.json to output
    docs_json = pixeltable_dir / 'docs' / 'target' / 'docs.json'
    if docs_json.exists():
        shutil.copy2(docs_json, output_dir / 'docs.json')

    print(f"   💪 Documentation generated")


def deploy_to_dev(output_dir: Path):
    """
    Deploy generated docs to pixeltable-docs-www/dev branch.

    Args:
        output_dir: Directory containing generated docs
    """
    print(f"\n🚀 Deploying to dev branch...")

    with tempfile.TemporaryDirectory() as temp_dir:
        docs_repo_dir = Path(temp_dir) / 'pixeltable-docs-www'

        # Clone the docs repository
        print(f"   Cloning pixeltable-docs-www...")
        result = subprocess.run(
            ['git', 'clone', '-b', 'dev', 'https://github.com/pixeltable/pixeltable-docs-www.git', str(docs_repo_dir)],
            capture_output=True,
            text=True
        )

        # If dev branch doesn't exist, create it from main
        if result.returncode != 0:
            print(f"   Creating dev branch...")
            subprocess.run(
                ['git', 'clone', 'https://github.com/pixeltable/pixeltable-docs-www.git', str(docs_repo_dir)],
                capture_output=True,
                text=True,
                check=True
            )
            subprocess.run(
                ['git', 'checkout', '-b', 'dev'],
                cwd=str(docs_repo_dir),
                capture_output=True,
                text=True,
                check=True
            )

        # Remove sdk/latest before deploying (it's only for local preview)
        latest_sdk = output_dir / 'sdk' / 'latest'
        if latest_sdk.exists():
            print(f"   Removing sdk/latest (local preview only)...")
            shutil.rmtree(latest_sdk)

        # Copy all docs from output (mintlifier already merged docs.json)
        print(f"   Copying documentation files...")
        for item in output_dir.iterdir():
            dest = docs_repo_dir / item.name
            if item.is_dir():
                if dest.exists():
                    shutil.rmtree(dest)
                shutil.copytree(item, dest)
            else:
                shutil.copy2(item, dest)

        # Commit and push
        print(f"   Committing changes...")
        subprocess.run(['git', 'add', '-A'], cwd=str(docs_repo_dir), check=True)

        result = subprocess.run(
            ['git', 'diff', '--staged', '--quiet'],
            cwd=str(docs_repo_dir)
        )

        if result.returncode != 0:  # There are changes
            subprocess.run(
                ['git', 'commit', '-m', 'Deploy dev documentation for pre-release validation'],
                cwd=str(docs_repo_dir),
                check=True
            )

            print(f"   Pushing to dev branch...")
            subprocess.run(
                ['git', 'push', 'origin', 'dev'],
                cwd=str(docs_repo_dir),
                check=True
            )

            print(f"   ✨ Deployed successfully")
        else:
            print(f"   No changes to deploy")


def main():
    """Main entry point."""
    try:
        print(f"🚀 Deploying documentation to dev for pre-release validation")

        # Find pixeltable repo in current directory
        pixeltable_dir = find_pixeltable_repo()
        print(f"   Using pixeltable from: {pixeltable_dir}")

        # Create temporary workspace
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create venv and install pixeltable from current directory
            venv_dir = create_venv_and_install(temp_path, pixeltable_dir)

            # Generate documentation
            output_dir = temp_path / 'docs_output'
            output_dir.mkdir()
            generate_docs(venv_dir, pixeltable_dir, output_dir)

            # Deploy to dev
            deploy_to_dev(output_dir)

        print(f"\n🎉 Documentation deployed successfully!")
        print(f"   View at: https://pixeltable-dev.mintlify.app/")
        print(f"   Note: This deployment shows ALL MDX errors for review")
        print(f"   Fix any errors in docstrings before creating a release tag")

    except Exception as e:
        print(f"\n💀 Deployment failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

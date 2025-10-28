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

from doctools.changelog.fetch_releases import generate_changelog_to_dir
from doctools.config import get_mintlify_source_path
from doctools.convert_notebooks.convert_notebooks import convert_notebooks_to_dir


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
        [str(pip_path), 'install', '-q', '--upgrade', '--no-cache-dir', '--force-reinstall', 'git+https://github.com/pixeltable/pixeltable-doctools.git@main'],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        raise RuntimeError(f"Failed to install pixeltable-doctools: {result.stderr}")

    print(f"   💯 Environment ready")
    return venv_dir


def generate_docs(venv_dir: Path, pixeltable_dir: Path, output_dir: Path) -> str:
    """
    Generate SDK documentation from current working directory.

    Args:
        venv_dir: Path to virtual environment
        pixeltable_dir: Path to current pixeltable repository
        output_dir: Where to output generated docs

    Returns:
        commit_hash: Short commit hash used as version
    """
    print(f"\n🔥 Generating documentation from current working directory...")

    # Get current commit hash as version
    result = subprocess.run(
        ['git', 'rev-parse', '--short', 'HEAD'],
        cwd=str(pixeltable_dir),
        capture_output=True,
        text=True
    )
    commit_hash = result.stdout.strip()
    print(f"   Using commit hash as version: {commit_hash}")

    # Create output structure - use commit hash as version
    sdk_output = output_dir / 'sdk' / commit_hash
    sdk_output.mkdir(parents=True)

    # Use docs structure from current repo
    mintlify_src = get_mintlify_source_path(pixeltable_dir)
    opml_path = pixeltable_dir / 'docs' / 'public_api.opml'

    if not mintlify_src.exists():
        raise RuntimeError(
            f"Mintlify source not found at {mintlify_src}\n"
            f"Please run this command from the pixeltable repository."
        )

    # Create docs/target directory
    target_dir = pixeltable_dir / 'docs' / 'target'
    target_dir.mkdir(parents=True, exist_ok=True)

    # Generate notebooks to docs/mintlify/notebooks/
    print(f"   Generating notebooks...")
    notebooks_output = mintlify_src / 'notebooks'
    convert_notebooks_to_dir(pixeltable_dir, notebooks_output)
    print(f"   ✅ Notebooks generated")

    # Generate changelog to docs/mintlify/changelog/
    print(f"   Generating changelog from GitHub releases...")
    changelog_output = mintlify_src / 'changelog'
    generate_changelog_to_dir(changelog_output)
    print(f"   ✅ Changelog generated")

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

    # Copy docs.json from docs/mintlify/ to docs/target/ for mintlifier
    # Mintlifier will update this file with SDK navigation structure
    source_docs_json = mintlify_src / 'docs.json'
    target_docs_json = target_dir / 'docs.json'
    if source_docs_json.exists():
        shutil.copy2(source_docs_json, target_docs_json)
        print(f"   ✓ Copied docs.json to target directory for mintlifier")

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
    # Mintlifier generates to target/sdk/latest, copy that to our commit hash output
    src_sdk = pixeltable_dir / 'docs' / 'target' / 'sdk' / 'latest'
    if src_sdk.exists():
        print(f"   Copying newly generated docs to sdk/{commit_hash}/...")
        shutil.copytree(src_sdk, sdk_output, dirs_exist_ok=True)

    # Merge SDK section from mintlifier output into our source docs.json
    import json

    # Load the source docs.json that was copied to output_dir (has notebooks/changelog)
    output_docs_json = output_dir / 'docs.json'
    mintlifier_docs_json = pixeltable_dir / 'docs' / 'target' / 'docs.json'

    if output_docs_json.exists() and mintlifier_docs_json.exists():
        print(f"   Merging SDK section into docs.json...")

        with open(output_docs_json, 'r') as f:
            docs_config = json.load(f)

        with open(mintlifier_docs_json, 'r') as f:
            mintlifier_config = json.load(f)

        # Extract SDK tab from mintlifier output
        sdk_tab = None
        for tab in mintlifier_config.get('navigation', {}).get('tabs', []):
            if tab.get('tab') == 'Pixeltable SDK':
                sdk_tab = tab
                break

        # Replace SDK tab in our source docs.json with mintlifier's version
        # IMPORTANT: Keep all other tabs from source (Documentation with notebooks, Changelog, etc.)
        if sdk_tab:
            tabs = docs_config.setdefault('navigation', {}).setdefault('tabs', [])
            sdk_tab_found = False

            for i, tab in enumerate(tabs):
                if tab.get('tab') == 'Pixeltable SDK':
                    tabs[i] = sdk_tab
                    sdk_tab_found = True
                    break

            if not sdk_tab_found:
                # SDK tab doesn't exist in source, add it after Documentation tab
                for i, tab in enumerate(tabs):
                    if tab.get('tab') == 'Documentation':
                        tabs.insert(i + 1, sdk_tab)
                        break
                else:
                    # No Documentation tab, just append
                    tabs.append(sdk_tab)

        # Update all SDK paths from sdk/latest/ to sdk/{commit_hash}/
        # Also update dropdown label from "latest" to commit hash
        docs_str = json.dumps(docs_config)
        docs_str = docs_str.replace('sdk/latest/', f'sdk/{commit_hash}/')
        docs_str = docs_str.replace('"dropdown": "latest"', f'"dropdown": "{commit_hash[:8]}"')
        docs_config = json.loads(docs_str)

        with open(output_dir / 'docs.json', 'w') as f:
            json.dump(docs_config, f, indent=2)

        print(f"   ✅ docs.json updated with SDK section")

    print(f"   💪 Documentation generated")
    return commit_hash


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

            # Generate documentation (returns commit hash)
            output_dir = temp_path / 'docs_output'
            output_dir.mkdir()
            commit_hash = generate_docs(venv_dir, pixeltable_dir, output_dir)

            # Deploy to dev
            deploy_to_dev(output_dir)

        print(f"\n🎉 Documentation deployed successfully!")
        print(f"   View at: https://pixeltable-dev.mintlify.app/sdk/{commit_hash}")
        print(f"   Commit: {commit_hash}")
        print(f"   Note: This deployment shows ALL MDX errors for review")
        print(f"   Fix any errors in docstrings before creating a release tag")

    except Exception as e:
        print(f"\n💀 Deployment failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
Deploy versioned documentation to staging environment.

This script:
1. Takes a version tag (e.g., v0.4.17)
2. Extracts major.minor prefix (e.g., v0.4) for version management
3. Clones pixeltable repo and checks out the full version tag
4. Creates temporary environment and installs that version
5. Generates SDK documentation using the full version
6. Removes any existing docs with the same major.minor prefix (keeps other major versions)
7. Deploys to pixeltable-docs-www/stage branch

Version Strategy:
- Full version (v0.4.17) is used for all paths, GitHub links, and dropdowns
- When deploying v0.4.17, any existing v0.4.x versions are removed
- Other major.minor versions (e.g., v0.3.14) are preserved
"""

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from doctools.changelog.fetch_releases import generate_changelog_to_dir
from doctools.config import get_mintlify_source_path
from doctools.convert_notebooks.convert_notebooks import convert_notebooks_to_dir


def merge_docs_json(production_docs: dict, local_docs: dict, generated_docs: dict) -> dict:
    """
    Merge docs.json from three sources:
    1. Production (main branch) - has all historical SDK versions
    2. Local (current repo) - has latest navigation structure (notebooks, etc.)
    3. Generated (mintlifier) - has new SDK version being deployed

    Strategy:
    - Use local navigation (tabs) for non-SDK content
    - Use generated SDK tab to get new version
    - Merge SDK versions from production + generated
    - Keep other settings from local (colors, logo, etc.)

    Args:
        production_docs: docs.json from production (main branch)
        local_docs: docs.json from current repo
        generated_docs: docs.json after mintlifier

    Returns:
        Merged docs.json
    """
    import copy
    result = copy.deepcopy(local_docs)

    # Find SDK tab in each version
    def find_sdk_tab(docs):
        if 'navigation' in docs and 'tabs' in docs['navigation']:
            for tab in docs['navigation']['tabs']:
                if tab.get('tab') == 'Pixeltable SDK':
                    return tab
        return None

    prod_sdk_tab = find_sdk_tab(production_docs)
    gen_sdk_tab = find_sdk_tab(generated_docs)
    local_sdk_tab = find_sdk_tab(result)

    if gen_sdk_tab and local_sdk_tab:
        # Replace local SDK tab with generated one (has new version)
        for i, tab in enumerate(result['navigation']['tabs']):
            if tab.get('tab') == 'Pixeltable SDK':
                result['navigation']['tabs'][i] = gen_sdk_tab
                break

        # Merge version dropdowns from production into generated
        if prod_sdk_tab and 'dropdowns' in prod_sdk_tab:
            gen_dropdowns = gen_sdk_tab.get('dropdowns', [])
            prod_dropdowns = prod_sdk_tab.get('dropdowns', [])

            # Collect all unique versions (keyed by dropdown name)
            versions = {}
            for dropdown in prod_dropdowns:
                versions[dropdown.get('dropdown')] = dropdown
            for dropdown in gen_dropdowns:
                versions[dropdown.get('dropdown')] = dropdown

            # Sort by version number (newest first)
            sorted_versions = sorted(
                versions.values(),
                key=lambda d: d.get('dropdown', ''),
                reverse=True
            )

            # Update the SDK tab with merged versions
            for tab in result['navigation']['tabs']:
                if tab.get('tab') == 'Pixeltable SDK':
                    tab['dropdowns'] = sorted_versions
                    break

    return result


def parse_version(version: str) -> tuple[str, str]:
    """
    Parse version string to extract major.minor prefix.

    Args:
        version: Full version like 'v0.4.17'

    Returns:
        Tuple of (full_version, major_minor_prefix) like ('v0.4.17', 'v0.4')
    """
    if not version.startswith('v'):
        version = f'v{version}'

    # Extract major.minor prefix from v0.4.17 -> v0.4
    match = re.match(r'(v\d+\.\d+)', version)
    if not match:
        raise ValueError(f"Invalid version format: {version}. Expected format: v0.4.17")

    major_minor_prefix = match.group(1)
    return version, major_minor_prefix


def clone_pixeltable(temp_dir: Path, version: str) -> Path:
    """
    Clone pixeltable repository and checkout specific version.

    Args:
        temp_dir: Temporary directory for clone
        version: Git tag to checkout

    Returns:
        Path to cloned repository
    """
    print(f"\n📥 Cloning pixeltable repository...")
    repo_dir = temp_dir / 'pixeltable'

    result = subprocess.run(
        ['git', 'clone', 'https://github.com/pixeltable/pixeltable.git', str(repo_dir)],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        raise RuntimeError(f"Failed to clone pixeltable: {result.stderr}")

    print(f"   Checking out {version}...")
    result = subprocess.run(
        ['git', 'checkout', version],
        cwd=str(repo_dir),
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        raise RuntimeError(f"Failed to checkout {version}: {result.stderr}")

    print(f"   ✓ Checked out {version}")
    return repo_dir


def create_venv_and_install(temp_dir: Path, pixeltable_dir: Path) -> Path:
    """
    Create virtual environment and install pixeltable + doctools.

    Args:
        temp_dir: Temporary directory
        pixeltable_dir: Path to pixeltable repository

    Returns:
        Path to venv directory
    """
    print(f"\n🔧 Creating virtual environment...")
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
    python_path = venv_dir / 'bin' / 'python'

    print(f"   Installing pixeltable from {pixeltable_dir}...")
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

    print(f"   ✓ Environment ready")
    return venv_dir


def find_current_pixeltable_repo() -> Path:
    """
    Find the current pixeltable repository (not the cloned version).

    This is used to get the latest docs structure from the working directory.
    """
    # Start from current working directory
    cwd = Path.cwd()

    # Check if we're in pixeltable repo
    if get_mintlify_source_path(cwd).exists():
        return cwd

    # Walk up to find it
    current = cwd
    for _ in range(5):
        if get_mintlify_source_path(current).exists():
            return current
        current = current.parent

    # Not found - user should run from pixeltable repo or we use main branch
    return None


def generate_docs(venv_dir: Path, pixeltable_dir: Path, output_dir: Path, full_version: str, major_minor_prefix: str):
    """
    Generate SDK documentation for the specified version.

    Args:
        venv_dir: Path to virtual environment
        pixeltable_dir: Path to cloned pixeltable repository (versioned)
        output_dir: Where to output generated docs
        full_version: Full version string (e.g., 'v0.4.17')
        major_minor_prefix: Major.minor prefix (e.g., 'v0.4') - used to find old versions to delete
    """
    print(f"\n📝 Generating documentation for {full_version}...")

    # Create output structure using full version
    sdk_output = output_dir / 'sdk' / full_version
    sdk_output.mkdir(parents=True)

    # Get docs structure from current working directory (if available)
    # This allows us to use the latest doc structure for old code versions
    current_repo = find_current_pixeltable_repo()

    if current_repo:
        print(f"   Using documentation structure from: {current_repo}")
        mintlify_src = get_mintlify_source_path(current_repo)
        opml_path = current_repo / 'docs' / 'public_api.opml'
    else:
        print(f"   Using documentation structure from cloned repo")
        mintlify_src = get_mintlify_source_path(pixeltable_dir)
        opml_path = pixeltable_dir / 'docs' / 'public_api.opml'

    if not mintlify_src.exists():
        raise RuntimeError(
            f"Mintlify source not found at {mintlify_src}\n"
            f"Please run this command from the pixeltable repository, or ensure docs/mintlify/ exists."
        )

    # Copy OPML to cloned repo so mintlifier can find it
    if opml_path.exists():
        dest_opml = pixeltable_dir / 'docs' / 'public_api.opml'
        dest_opml.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(opml_path, dest_opml)
        print(f"   Using API structure from: {opml_path}")
    else:
        print(f"   Warning: OPML not found at {opml_path}, using version from cloned repo")

    # Copy mintlify source to cloned repo
    dest_mintlify = get_mintlify_source_path(pixeltable_dir)
    if dest_mintlify.exists():
        shutil.rmtree(dest_mintlify)
    shutil.copytree(mintlify_src, dest_mintlify)

    # Create docs/target directory
    target_dir_in_clone = pixeltable_dir / 'docs' / 'target'
    target_dir_in_clone.mkdir(parents=True, exist_ok=True)

    # Fetch docs.json and existing SDK versions from production (main branch)
    # This preserves version dropdown and other minor versions (e.g., v0.3.14)
    print(f"   Fetching docs.json and SDK versions from production (main branch)...")
    production_docs_json = None
    with tempfile.TemporaryDirectory() as temp_dir:
        docs_repo_dir = Path(temp_dir) / 'pixeltable-docs-www'

        result = subprocess.run(
            ['git', 'clone', '--depth=1', 'https://github.com/pixeltable/pixeltable-docs-www.git', str(docs_repo_dir)],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            raise RuntimeError(f"Failed to fetch production docs from main branch: {result.stderr}")

        # Load production docs.json (we'll merge it later)
        import json
        docs_json = docs_repo_dir / 'docs.json'
        if docs_json.exists():
            with open(docs_json, 'r') as f:
                production_docs_json = json.load(f)

        # Preserve existing SDK versions to final output
        # But remove any previous versions with the same major.minor prefix
        existing_sdk = docs_repo_dir / 'sdk'
        if existing_sdk.exists():
            print(f"   Copying existing SDK versions to output...")
            # Copy all versions first
            shutil.copytree(existing_sdk, output_dir / 'sdk', dirs_exist_ok=True)

            # Then remove any existing versions with the same major.minor prefix
            output_sdk = output_dir / 'sdk'
            if output_sdk.exists():
                for version_dir in output_sdk.iterdir():
                    if version_dir.is_dir() and version_dir.name.startswith(major_minor_prefix):
                        # Don't delete the version we're about to create
                        if version_dir.name != full_version:
                            print(f"   Removing old version: {version_dir.name}")
                            shutil.rmtree(version_dir)

        print(f"   ✓ Fetched production docs.json and SDK versions")

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

    # Also copy to final output
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
    source_docs_json = dest_mintlify / 'docs.json'
    target_docs_json = target_dir_in_clone / 'docs.json'
    if source_docs_json.exists():
        shutil.copy2(source_docs_json, target_docs_json)
        print(f"   ✓ Copied docs.json to target directory for mintlifier")

    # Run mintlifier using venv's Python
    python_path = venv_dir / 'bin' / 'python'
    mintlifier_path = venv_dir / 'bin' / 'mintlifier'

    print(f"   Running mintlifier for {full_version}...")
    result = subprocess.run(
        [str(mintlifier_path), '--no-errors', '--version', full_version],
        cwd=str(pixeltable_dir),
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        raise RuntimeError(f"Mintlifier failed: {result.stderr}")

    # Copy newly generated SDK docs for this version
    # Mintlifier generates to target/sdk/latest, copy that to our versioned output
    src_sdk = pixeltable_dir / 'docs' / 'target' / 'sdk' / 'latest'
    if src_sdk.exists():
        print(f"   Copying newly generated docs to sdk/{full_version}/...")
        shutil.copytree(src_sdk, sdk_output, dirs_exist_ok=True)

    # Merge docs.json from three sources: production, local, and generated
    print(f"   Merging docs.json from production, local, and generated sources...")
    generated_docs_json_path = pixeltable_dir / 'docs' / 'target' / 'docs.json'
    local_docs_json_path = mintlify_src / 'docs.json'

    if generated_docs_json_path.exists() and local_docs_json_path.exists():
        import json

        # Load all three versions
        with open(generated_docs_json_path, 'r') as f:
            generated_docs_json = json.load(f)
        with open(local_docs_json_path, 'r') as f:
            local_docs_json = json.load(f)

        # Merge them
        if production_docs_json:
            merged_docs_json = merge_docs_json(
                production_docs_json,
                local_docs_json,
                generated_docs_json
            )
        else:
            # No production docs, just merge local + generated
            merged_docs_json = merge_docs_json(
                {},
                local_docs_json,
                generated_docs_json
            )

        # Write merged version
        with open(output_dir / 'docs.json', 'w') as f:
            json.dump(merged_docs_json, f, indent=2)

        print(f"   ✓ Merged docs.json successfully")
    elif generated_docs_json_path.exists():
        # Fallback: just copy generated
        shutil.copy2(generated_docs_json_path, output_dir / 'docs.json')

    print(f"   ✓ Documentation generated")


def deploy_to_stage(output_dir: Path, full_version: str):
    """
    Deploy generated docs to pixeltable-docs-www/stage branch.

    Args:
        output_dir: Directory containing generated docs
        full_version: Full version string (e.g., 'v0.4.17')
    """
    print(f"\n📤 Deploying to stage branch...")

    with tempfile.TemporaryDirectory() as temp_dir:
        docs_repo_dir = Path(temp_dir) / 'pixeltable-docs-www'

        # Clone the docs repository
        print(f"   Cloning pixeltable-docs-www...")
        result = subprocess.run(
            ['git', 'clone', '-b', 'stage', 'https://github.com/pixeltable/pixeltable-docs-www.git', str(docs_repo_dir)],
            capture_output=True,
            text=True
        )

        # If stage branch doesn't exist, create it from main
        if result.returncode != 0:
            print(f"   Creating stage branch...")
            subprocess.run(
                ['git', 'clone', 'https://github.com/pixeltable/pixeltable-docs-www.git', str(docs_repo_dir)],
                capture_output=True,
                text=True,
                check=True
            )
            subprocess.run(
                ['git', 'checkout', '-b', 'stage'],
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
                ['git', 'commit', '-m', f'Deploy documentation for {full_version}'],
                cwd=str(docs_repo_dir),
                check=True
            )

            print(f"   Pushing to stage branch...")
            subprocess.run(
                ['git', 'push', 'origin', 'stage'],
                cwd=str(docs_repo_dir),
                check=True
            )

            print(f"   ✓ Deployed successfully")
        else:
            print(f"   No changes to deploy")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Deploy versioned documentation to staging'
    )
    parser.add_argument(
        '--version',
        required=True,
        help='Version tag to deploy (e.g., v0.4.17)'
    )

    args = parser.parse_args()

    try:
        # Parse version
        full_version, major_minor_prefix = parse_version(args.version)
        print(f"🚀 Deploying documentation for {full_version} (major.minor: {major_minor_prefix})")

        # Create temporary workspace
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Clone and checkout pixeltable
            pixeltable_dir = clone_pixeltable(temp_path, full_version)

            # Create venv and install pixeltable
            venv_dir = create_venv_and_install(temp_path, pixeltable_dir)

            # Generate documentation
            output_dir = temp_path / 'docs_output'
            output_dir.mkdir()
            generate_docs(venv_dir, pixeltable_dir, output_dir, full_version, major_minor_prefix)

            # Deploy to stage
            deploy_to_stage(output_dir, full_version)

        print(f"\n✅ Documentation deployed successfully!")
        print(f"   View at: https://pixeltable-stage.mintlify.app/")

    except Exception as e:
        print(f"\n❌ Deployment failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

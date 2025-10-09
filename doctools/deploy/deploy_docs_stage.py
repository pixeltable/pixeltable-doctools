#!/usr/bin/env python3
"""
Deploy versioned documentation to staging environment.

This script:
1. Takes a version tag (e.g., v0.4.17)
2. Extracts major version (e.g., v0.4)
3. Clones pixeltable repo and checks out the tag
4. Creates temporary environment and installs that version
5. Generates SDK and LLM documentation
6. Deploys to pixeltable-docs-www/stage branch
"""

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def parse_version(version: str) -> tuple[str, str]:
    """
    Parse version string to extract major version.

    Args:
        version: Full version like 'v0.4.17'

    Returns:
        Tuple of (full_version, major_version) like ('v0.4.17', 'v0.4')
    """
    if not version.startswith('v'):
        version = f'v{version}'

    # Extract major.minor from v0.4.17 -> v0.4
    match = re.match(r'(v\d+\.\d+)', version)
    if not match:
        raise ValueError(f"Invalid version format: {version}. Expected format: v0.4.17")

    major_version = match.group(1)
    return version, major_version


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
        [str(pip_path), 'install', '-q', 'git+https://github.com/pixeltable/pixeltable-doctools.git'],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        raise RuntimeError(f"Failed to install pixeltable-doctools: {result.stderr}")

    print(f"   ✓ Environment ready")
    return venv_dir


def generate_docs(venv_dir: Path, pixeltable_dir: Path, output_dir: Path, major_version: str):
    """
    Generate SDK documentation for the specified version.

    Args:
        venv_dir: Path to virtual environment
        pixeltable_dir: Path to pixeltable repository
        output_dir: Where to output generated docs
        major_version: Major version string (e.g., 'v0.4')
    """
    print(f"\n📝 Generating documentation for {major_version}...")

    # Create output structure
    sdk_output = output_dir / 'sdk' / major_version
    sdk_output.mkdir(parents=True)

    # Copy mintlify-src to output
    mintlify_src = pixeltable_dir / 'docs' / 'mintlify-src'
    if not mintlify_src.exists():
        raise RuntimeError(
            f"mintlify-src not found in {pixeltable_dir}\n"
            f"This version of Pixeltable doesn't support the Mintlify documentation structure.\n"
            f"Only versions with docs/mintlify-src/ can be deployed (typically v0.4.17+)"
        )

    print(f"   Copying base documentation...")
    for item in mintlify_src.iterdir():
        if item.name.startswith('.'):
            continue
        dest = output_dir / item.name
        if item.is_dir():
            shutil.copytree(item, dest)
        else:
            shutil.copy2(item, dest)

    # Run mintlifier using venv's Python
    python_path = venv_dir / 'bin' / 'python'
    mintlifier_path = venv_dir / 'bin' / 'mintlifier'

    print(f"   Running mintlifier...")
    result = subprocess.run(
        [str(mintlifier_path), '--no-errors'],
        cwd=str(pixeltable_dir),
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        raise RuntimeError(f"Mintlifier failed: {result.stderr}")

    # Copy generated SDK docs to versioned output
    src_sdk = pixeltable_dir / 'docs' / 'target' / 'sdk' / 'latest'
    if src_sdk.exists():
        print(f"   Copying SDK docs to {major_version}...")
        shutil.copytree(src_sdk, sdk_output, dirs_exist_ok=True)

    print(f"   ✓ Documentation generated")


def deploy_to_stage(output_dir: Path, major_version: str):
    """
    Deploy generated docs to pixeltable-docs-www/stage branch.

    Args:
        output_dir: Directory containing generated docs
        major_version: Major version string (e.g., 'v0.4')
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

        # Detect existing major versions
        existing_versions = []
        sdk_dir = docs_repo_dir / 'sdk'
        if sdk_dir.exists():
            existing_versions = [d.name for d in sdk_dir.iterdir() if d.is_dir() and d.name.startswith('v')]

        print(f"   Existing versions: {existing_versions if existing_versions else 'none'}")

        # Copy all base docs from output
        print(f"   Copying documentation files...")
        for item in output_dir.iterdir():
            dest = docs_repo_dir / item.name
            if item.is_dir():
                if dest.exists():
                    shutil.rmtree(dest)
                shutil.copytree(item, dest)
            else:
                shutil.copy2(item, dest)

        # Update docs.json to include all versions
        import json
        docs_json_path = docs_repo_dir / 'docs.json'
        with open(docs_json_path) as f:
            docs_config = json.load(f)

        # Find all versions now present
        sdk_dir = docs_repo_dir / 'sdk'
        all_versions = sorted([d.name for d in sdk_dir.iterdir() if d.is_dir() and d.name.startswith('v')], reverse=True)

        # Update SDK tab with dropdowns for each major version
        for tab in docs_config['navigation']['tabs']:
            if tab.get('tab') == 'Pixeltable SDK':
                # Build dropdowns for each version
                tab['dropdowns'] = []
                for version in all_versions:
                    tab['dropdowns'].append({
                        'dropdown': version,
                        'icon': 'rocket' if version == all_versions[0] else 'archive',
                        'groups': [{
                            'group': 'SDK Reference',
                            'pages': [
                                # TODO: Generate proper page structure
                                # For now, this will need to be refined
                            ]
                        }]
                    })
                break

        # Save updated docs.json
        with open(docs_json_path, 'w') as f:
            json.dump(docs_config, f, indent=2)

        # Commit and push
        print(f"   Committing changes...")
        subprocess.run(['git', 'add', '-A'], cwd=str(docs_repo_dir), check=True)

        result = subprocess.run(
            ['git', 'diff', '--staged', '--quiet'],
            cwd=str(docs_repo_dir)
        )

        if result.returncode != 0:  # There are changes
            subprocess.run(
                ['git', 'commit', '-m', f'Deploy documentation for {major_version}'],
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
        full_version, major_version = parse_version(args.version)
        print(f"🚀 Deploying documentation for {full_version} (major: {major_version})")

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
            generate_docs(venv_dir, pixeltable_dir, output_dir, major_version)

            # Deploy to stage
            deploy_to_stage(output_dir, major_version)

        print(f"\n✅ Documentation deployed successfully!")
        print(f"   View at: https://pixeltable-stage.mintlify.app/")

    except Exception as e:
        print(f"\n❌ Deployment failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

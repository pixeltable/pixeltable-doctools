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


def find_current_pixeltable_repo() -> Path:
    """
    Find the current pixeltable repository (not the cloned version).

    This is used to get the latest docs structure from the working directory.
    """
    # Start from current working directory
    cwd = Path.cwd()

    # Check if we're in pixeltable repo
    if (cwd / 'docs' / 'mintlify-src').exists():
        return cwd

    # Walk up to find it
    current = cwd
    for _ in range(5):
        if (current / 'docs' / 'mintlify-src').exists():
            return current
        current = current.parent

    # Not found - user should run from pixeltable repo or we use main branch
    return None


def generate_docs(venv_dir: Path, pixeltable_dir: Path, output_dir: Path, major_version: str):
    """
    Generate SDK documentation for the specified version.

    Args:
        venv_dir: Path to virtual environment
        pixeltable_dir: Path to cloned pixeltable repository (versioned)
        output_dir: Where to output generated docs
        major_version: Major version string (e.g., 'v0.4')
    """
    print(f"\n📝 Generating documentation for {major_version}...")

    # Create output structure
    sdk_output = output_dir / 'sdk' / major_version
    sdk_output.mkdir(parents=True)

    # Get docs structure from current working directory (if available)
    # This allows us to use the latest doc structure for old code versions
    current_repo = find_current_pixeltable_repo()

    if current_repo:
        print(f"   Using documentation structure from: {current_repo}")
        mintlify_src = current_repo / 'docs' / 'mintlify-src'
        opml_path = current_repo / 'docs' / 'public_api.opml'
    else:
        print(f"   Using documentation structure from cloned repo")
        mintlify_src = pixeltable_dir / 'docs' / 'mintlify-src'
        opml_path = pixeltable_dir / 'docs' / 'public_api.opml'

    if not mintlify_src.exists():
        raise RuntimeError(
            f"mintlify-src not found at {mintlify_src}\n"
            f"Please run this command from the pixeltable repository, or ensure docs/mintlify-src/ exists."
        )

    # Copy OPML to cloned repo so mintlifier can find it
    if opml_path.exists():
        dest_opml = pixeltable_dir / 'docs' / 'public_api.opml'
        dest_opml.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(opml_path, dest_opml)
        print(f"   Using API structure from: {opml_path}")
    else:
        print(f"   Warning: OPML not found at {opml_path}, using version from cloned repo")

    # Copy mintlify-src to cloned repo
    dest_mintlify = pixeltable_dir / 'docs' / 'mintlify-src'
    if dest_mintlify.exists():
        shutil.rmtree(dest_mintlify)
    shutil.copytree(mintlify_src, dest_mintlify)

    # Create docs/target directory
    target_dir_in_clone = pixeltable_dir / 'docs' / 'target'
    target_dir_in_clone.mkdir(parents=True, exist_ok=True)

    # Fetch current deployed docs from pixeltable-docs-www/main
    print(f"   Fetching current deployed docs from pixeltable-docs-www...")
    with tempfile.TemporaryDirectory() as temp_dir:
        docs_repo_dir = Path(temp_dir) / 'pixeltable-docs-www'

        result = subprocess.run(
            ['git', 'clone', '--depth=1', 'https://github.com/pixeltable/pixeltable-docs-www.git', str(docs_repo_dir)],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            print(f"   Warning: Could not fetch deployed docs, using base docs.json")
            docs_json_src = mintlify_src / 'docs.json'
            if docs_json_src.exists():
                shutil.copy2(docs_json_src, target_dir_in_clone / 'docs.json')
        else:
            # Copy all files from deployed docs to target
            for item in docs_repo_dir.iterdir():
                if item.name == '.git':
                    continue
                dest = target_dir_in_clone / item.name
                if item.is_dir():
                    if dest.exists():
                        shutil.rmtree(dest)
                    shutil.copytree(item, dest)
                else:
                    shutil.copy2(item, dest)

            # Also preserve existing SDK docs to final output (before mintlifier overwrites target/sdk/)
            # This preserves sdk/latest/ and any other existing versions
            existing_sdk = docs_repo_dir / 'sdk'
            if existing_sdk.exists():
                print(f"   Copying existing SDK versions to output...")
                shutil.copytree(existing_sdk, output_dir / 'sdk', dirs_exist_ok=True)

            print(f"   ✓ Fetched deployed docs")

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

    # Run mintlifier using venv's Python
    python_path = venv_dir / 'bin' / 'python'
    mintlifier_path = venv_dir / 'bin' / 'mintlifier'

    print(f"   Running mintlifier for {major_version}...")
    result = subprocess.run(
        [str(mintlifier_path), '--no-errors', '--version', major_version],
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
        print(f"   Copying newly generated docs to sdk/{major_version}/...")
        shutil.copytree(src_sdk, sdk_output, dirs_exist_ok=True)

    # Copy updated docs.json to output
    docs_json_in_clone = pixeltable_dir / 'docs' / 'target' / 'docs.json'
    if docs_json_in_clone.exists():
        shutil.copy2(docs_json_in_clone, output_dir / 'docs.json')

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

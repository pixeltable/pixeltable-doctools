#!/usr/bin/env python3
"""
Build complete Mintlify documentation site.

This script:
1. Copies docs/mintlify/* to docs/target/
2. Runs mintlifier to generate SDK documentation into docs/target/
3. Results in a complete, deployable documentation site
"""

import shutil
import subprocess
import sys
from pathlib import Path

from doctools.changelog.fetch_releases import generate_changelog_to_dir
from doctools.convert_notebooks.convert_notebooks import convert_notebooks_to_dir


def validate_mintlify_docs(target_dir: Path) -> list[str]:
    """
    Validate Mintlify documentation for parsing errors.

    Runs mintlify validation and captures any parsing errors.

    Args:
        target_dir: Directory containing built documentation

    Returns:
        List of parsing error messages (empty if no errors)
    """
    # Validate the built documentation for parsing errors
    print(f"\nValidating documentation ...")

    try:
        # Run mintlify dev with a short timeout to capture parsing errors
        # The parsing errors appear in stderr immediately on startup
        result = subprocess.run(
            ['npx', 'mintlify', 'dev', '--port', '3001', '--no-open'],
            cwd=str(target_dir),
            capture_output=True,
            text=True,
            timeout=5  # Just need a few seconds to capture initial parsing
        )
    except subprocess.TimeoutExpired as e:
        # Timeout is expected - we just want to capture the initial output
        stderr_output = e.stderr.decode() if isinstance(e.stderr, bytes) else e.stderr
        stdout_output = e.stdout.decode() if isinstance(e.stdout, bytes) else e.stdout
    except Exception as e:
        # If validation command fails, return a warning but don't fail the build
        return [f"⚠️  Could not run validation: {str(e)}"]
    else:
        # If command completed, use its output
        stderr_output = result.stderr
        stdout_output = result.stdout

    # Parse output for error messages
    errors = []
    output = (stderr_output or '') + (stdout_output or '')

    for line in output.split('\n'):
        # Look for parsing error lines
        if 'parsing error' in line.lower():
            # Clean up the line for display
            clean_line = line.strip()
            if clean_line:
                errors.append(clean_line)

    if errors:
        print(f"   Found {len(errors)} error(s):")
        for error in errors:
            print(f"   {error}")
    else:
        print(f"   No errors.")

    return errors


def build_mintlify(pxt_repo_dir: Path, no_errors: bool = False) -> None:
    """
    Build Mintlify documentation site.
    """
    print(f"Building docs from repository: {pxt_repo_dir}")

    docs_dir = pxt_repo_dir / 'docs'
    source_dir = docs_dir / 'mintlify'
    target_dir = docs_dir / 'target'
    opml_file = docs_dir / 'public_api.opml'

    # Verify source exists
    if not source_dir.exists():
        raise FileNotFoundError(f"Source directory not found: {source_dir}")

    if not opml_file.exists():
        raise FileNotFoundError(f"OPML file not found: {opml_file}")

    # Step 1: Clean and prepare target directory
    print(f"\n📁 Preparing target directory: {target_dir}")
    if target_dir.exists():
        shutil.rmtree(target_dir)
    target_dir.mkdir(parents=True)

    # Step 2: Generate notebooks to docs/mintlify/notebooks/
    print(f"\n📓 Generating notebooks...")
    notebooks_output = target_dir / 'notebooks'
    convert_notebooks_to_dir(pxt_repo_dir, notebooks_output)
    print(f"   ✅ Notebooks generated to {notebooks_output}")

    # Step 3: Generate changelog to docs/mintlify/changelog/
    print(f"\n📰 Generating changelog from GitHub releases...")
    changelog_output = target_dir / 'changelog'
    generate_changelog_to_dir(changelog_output)
    print(f"   ✅ Changelog generated to {changelog_output}")

    # Step 4: Copy mintlify source to target
    print(f"\n📋 Copying source files from {source_dir} to {target_dir}")
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

    # Step 5: Run mintlifier to generate SDK docs
    # Mintlifier now writes directly to docs/target/sdk/latest and updates docs/target/docs.json
    print(f"\n🔨 Running mintlifier to generate SDK documentation...")
    print(f"   OPML: {opml_file}")
    print(f"   Output: {target_dir}")

    try:
        # Run mintlifier - it writes directly to target
        # For stage/prod targets, hide errors from generated docs
        mintlifier_cmd = ['mintlifier']
        if no_errors:
            mintlifier_cmd.append('--no-errors')

        result = subprocess.run(
            mintlifier_cmd,
            cwd=str(pxt_repo_dir),  # Run from repo root
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

    validation_errors = validate_mintlify_docs(target_dir)
    if validation_errors:
        print(f"\n   Tip: Check the source docstrings for formatting issues", file=sys.stderr)
        print(f"   Run: cd {target_dir} && npx mintlify dev", file=sys.stderr)
        print(f"   to see real-time parsing errors in context", file=sys.stderr)

    print(f"\n   To preview locally, run:")
    print(f"   cd {target_dir} && npx mintlify dev")


def main():
    """Main entry point."""
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

    build_mintlify(pxt_repo_dir)


if __name__ == '__main__':
    main()

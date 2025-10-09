#!/usr/bin/env python3
"""
Convert Jupyter notebooks to Mintlify MDX format using Quarto.

This script:
1. Finds all .ipynb files in docs/notebooks/
2. Creates a temporary _quarto.yml config file
3. Runs quarto render to convert to MDX
4. Outputs to docs/mintlify-src/notebooks/ preserving directory structure
"""

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


# Quarto configuration template
QUARTO_CONFIG = """project:
  type: default
  output-dir: {output_dir}

format:
  docusaurus-md:
    # Output MDX files directly
    output-ext: mdx
    # Test with both echo and output true
    echo: true
    output: true
    warning: false
    error: false
    # Preserve YAML frontmatter
    preserve-yaml: true
    # Structure settings
    standalone: false
    toc: false
    wrap: auto
    # ENHANCED media handling
    fig-format: png
    fig-dpi: 300
    fig-path: images/
    # Extract media from notebooks - needs to be a path string
    extract-media: images/
    # Resource paths for finding images
    resource-path: [".", "images/", "../images/"]
    default-image-extension: png
    # Markdown headings
    markdown-headings: atx
"""


def find_pixeltable_repo() -> Path:
    """Find the pixeltable repository root."""
    cwd = Path.cwd()

    # Check if we're already in pixeltable repo
    if (cwd / 'docs' / 'notebooks').exists():
        return cwd

    # Walk up to find it
    current = cwd
    for _ in range(5):  # Don't go up more than 5 levels
        if (current / 'docs' / 'notebooks').exists():
            return current
        current = current.parent

    raise FileNotFoundError(
        "Could not find pixeltable repository. "
        "Make sure you're running this from within the pixeltable repo."
    )


def convert_notebooks() -> None:
    """Convert all notebooks to MDX format."""
    print("🔄 Converting Jupyter notebooks to Mintlify MDX format...")

    # Find pixeltable repo
    repo_root = find_pixeltable_repo()
    print(f"Found pixeltable repository at: {repo_root}")

    notebooks_dir = repo_root / 'docs' / 'notebooks'
    output_dir = repo_root / 'docs' / 'mintlify-src' / 'notebooks'

    # Verify source exists
    if not notebooks_dir.exists():
        raise FileNotFoundError(f"Notebooks directory not found: {notebooks_dir}")

    # Check for quarto
    if not shutil.which('quarto'):
        raise RuntimeError(
            "Quarto is not installed. Please install it from: https://quarto.org/docs/get-started/"
        )

    # Count notebooks
    notebooks = list(notebooks_dir.rglob('*.ipynb'))
    if not notebooks:
        print(f"⚠️  No notebooks found in {notebooks_dir}")
        return

    print(f"📚 Found {len(notebooks)} notebook(s) to convert")

    # Clean output directory
    if output_dir.exists():
        print(f"🧹 Cleaning output directory: {output_dir}")
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)

    # Create _quarto.yml config in notebooks directory
    config_file = notebooks_dir / '_quarto.yml'

    # Use absolute path for output-dir
    config = QUARTO_CONFIG.format(output_dir=str(output_dir.absolute()))
    config_file.write_text(config)

    try:
        print(f"\n🔨 Running Quarto to convert notebooks...")
        print(f"   Source: {notebooks_dir}")
        print(f"   Output: {output_dir}")
        print(f"   Config: {config_file.name}")

        # Run quarto render
        result = subprocess.run(
            ['quarto', 'render', '--to', 'docusaurus-md'],
            cwd=str(notebooks_dir),
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )

        # Print output
        if result.stdout:
            print("\n--- Quarto Output ---")
            print(result.stdout)

        if result.stderr:
            print("\n--- Quarto Warnings/Errors ---")
            print(result.stderr)

        if result.returncode != 0:
            raise subprocess.CalledProcessError(
                result.returncode,
                'quarto render',
                result.stdout,
                result.stderr
            )

        # Count converted files
        mdx_files = list(output_dir.rglob('*.mdx'))
        print(f"\n✅ Successfully converted {len(mdx_files)} notebook(s) to MDX")

        # Show directory structure
        print(f"\n📁 Output directory structure:")
        for mdx_file in sorted(mdx_files):
            rel_path = mdx_file.relative_to(output_dir)
            print(f"   {rel_path}")

        print(f"\n💡 Next steps:")
        print(f"   1. Review converted files in: {output_dir}")
        print(f"   2. Add notebook pages to docs/mintlify-src/docs.json")
        print(f"   3. Preview with: cd {repo_root / 'docs' / 'mintlify-src'} && mintlify dev")

    except subprocess.TimeoutExpired:
        print("\n❌ Quarto conversion timed out after 5 minutes", file=sys.stderr)
        raise
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Error running quarto:", file=sys.stderr)
        print(e.stdout, file=sys.stderr)
        print(e.stderr, file=sys.stderr)
        raise
    finally:
        # Clean up temporary config file
        if config_file.exists():
            config_file.unlink()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Convert Jupyter notebooks to Mintlify MDX format using Quarto'
    )

    parser.parse_args()

    try:
        convert_notebooks()
    except Exception as e:
        print(f"\n❌ Conversion failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()

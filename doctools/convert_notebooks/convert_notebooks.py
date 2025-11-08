#!/usr/bin/env python3
"""
Convert Jupyter notebooks to Mintlify MDX format using Quarto.

This script:
1. Finds all .ipynb files in docs/notebooks/
2. Creates a temporary _quarto.yml config file
3. Runs quarto render to convert to MDX
4. Outputs to docs/mintlify/notebooks/ preserving directory structure
"""

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from doctools.config import get_mintlify_source_path


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


def convert_notebooks() -> None:
    """Convert all notebooks to MDX format (convenience function for CLI)."""
    repo_root = find_pixeltable_repo()
    output_dir = get_mintlify_source_path(repo_root) / 'notebooks'
    convert_notebooks_to_dir(repo_root, output_dir)


def add_frontmatter_to_mdx(mdx_file: Path, notebooks_dir: Path) -> None:
    """
    Post-process MDX file to enhance frontmatter with links.

    Quarto already converts H1 to frontmatter with title.
    This function adds icon and description with Kaggle/Colab/GitHub links.

    Args:
        mdx_file: Path to the .mdx file
        notebooks_dir: Original notebooks directory (for calculating relative path)
    """
    content = mdx_file.read_text()

    # Extract existing frontmatter
    frontmatter_match = re.match(r'^---\n(.*?)\n---\n', content, re.DOTALL)
    if not frontmatter_match:
        print(f"⚠️  No frontmatter found in {mdx_file.name}, skipping")
        return

    existing_frontmatter = frontmatter_match.group(1)
    content_after_frontmatter = content[frontmatter_match.end():]

    # Extract title from existing frontmatter
    title_match = re.search(r'^title:\s*(.+)$', existing_frontmatter, re.MULTILINE)
    if not title_match:
        print(f"⚠️  No title in frontmatter for {mdx_file.name}, skipping")
        return

    title = title_match.group(1).strip().strip('"')

    # Try to find matching notebook in notebooks_dir
    matching_notebooks = list(notebooks_dir.rglob(f'{mdx_file.stem}.ipynb'))
    if not matching_notebooks:
        print(f"⚠️  Could not find original notebook for {mdx_file.name}")
        return

    original_notebook = matching_notebooks[0]
    # Get path relative to repo root (not just docs/)
    repo_root = notebooks_dir.parent.parent  # notebooks_dir is repo/docs/notebooks, so parent.parent is repo
    notebook_rel_path = original_notebook.relative_to(repo_root)

    # Generate URLs
    github_base = "https://github.com/pixeltable/pixeltable/blob/release"
    kaggle_url = f"https://kaggle.com/kernels/welcome?src={github_base}/{notebook_rel_path}"
    colab_url = f"https://colab.research.google.com/{github_base.replace('https://','')}/{notebook_rel_path}"
    github_url = f"{github_base}/{notebook_rel_path}"

    # Create enhanced frontmatter
    enhanced_frontmatter = f'''---
title: "{title}"
icon: "notebook"
description: "[Open in Kaggle]({kaggle_url}) | [Open in Colab]({colab_url}) | [View on GitHub]({github_url})"
---
'''

    # Write back with enhanced frontmatter
    mdx_file.write_text(enhanced_frontmatter + content_after_frontmatter)


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


def convert_notebooks_to_dir(repo_root: Path, output_dir: Path) -> None:
    """
    Convert all notebooks in repo_root/docs/notebooks to MDX format.

    Args:
        repo_root: Path to pixeltable repository root
        output_dir: Where to output the converted .mdx files
    """
    print("   Converting Jupyter notebooks to Mintlify MDX format...")
    print(f"   Repository: {repo_root}")
    print(f"   Output: {output_dir}")

    notebooks_dir = repo_root / 'docs' / 'notebooks'

    # Verify source exists
    if not notebooks_dir.exists():
        raise FileNotFoundError(f"Notebooks directory not found: {notebooks_dir}")

    # Check for quarto
    if not shutil.which('quarto'):
        raise RuntimeError(
            "Quarto is not installed."
        )

    # Count notebooks
    notebooks = [file for file in notebooks_dir.rglob('*.ipynb') if '.ipynb_checkpoints' not in file.parts]
    if not notebooks:
        raise RuntimeError(f"   No notebooks found: {notebooks_dir}")

    print(f"   Found {len(notebooks)} notebook(s) to convert.")

    # Clean output directory
    if output_dir.exists():
        print(f"   Cleaning output directory: {output_dir}")
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)

    # Create _quarto.yml config in notebooks directory
    config_file = notebooks_dir / '_quarto.yml'

    # Use absolute path for output-dir
    config = QUARTO_CONFIG.format(output_dir=str(output_dir.absolute()))
    config_file.write_text(config)

    try:
        print(f"Running Quarto to convert notebooks...")
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
        print(f"\nSuccessfully converted {len(mdx_files)} notebook(s) to MDX")

        # Post-process: Add frontmatter to each MDX file
        print(f"\nAdding frontmatter to MDX files...")
        for mdx_file in mdx_files:
            add_frontmatter_to_mdx(mdx_file, notebooks_dir)
        print(f"   Added frontmatter to {len(mdx_files)} file(s)")

    except subprocess.TimeoutExpired:
        print("\nQuarto conversion timed out after 5 minutes", file=sys.stderr)
        raise
    except subprocess.CalledProcessError as e:
        print(f"\nError running quarto:", file=sys.stderr)
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

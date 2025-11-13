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
from pathlib import Path

from pixeltable_doctools.config import get_mintlify_source_path


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
    notebook_github_path = f"pixeltable/pixeltable/blob/release/{notebook_rel_path}"

    # Generate URLs
    github_url = f"https://github.com/{notebook_github_path}"
    kaggle_url = f"https://kaggle.com/kernels/welcome?src={github_url}"
    colab_url = f"https://colab.research.google.com/github/{notebook_github_path}"

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

    print(f"   {len(notebooks)} total notebook(s).")

    notebooks_to_convert: list[Path] = []
    for notebook in notebooks:
        relpath = notebook.relative_to(notebooks_dir)
        output_path = output_dir / relpath.with_suffix('.mdx')
        if not output_path.exists() or notebook.stat().st_mtime > output_path.stat().st_mtime:
            notebooks_to_convert.append(notebook)

    print(f"   {len(notebooks_to_convert)} notebook(s) need conversion.")

    if not notebooks_to_convert:
        return

    print(f"   Running Quarto to convert notebooks...")
    print(f"      Source: {notebooks_dir}")
    print(f"      Output: {output_dir}")

    try:
        # Run quarto render
        subprocess.run(
            ['quarto', 'render', *[str(f) for f in notebooks_to_convert], '--quiet', '--to', 'docusaurus-md', '--output-dir', str(output_dir)],
            cwd=str(notebooks_dir),
            check=True,
            timeout=300  # 5 minute timeout
        )

    except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as e:
        print(e.stdout, file=sys.stderr)
        print(e.stderr, file=sys.stderr)
        raise

    # Count converted files
    mdx_files = list(output_dir.rglob('*.mdx'))
    print(f"   Successfully converted {len(mdx_files)} notebook(s) to MDX")

    # Post-process: Add frontmatter to each MDX file
    print(f"   Updating frontmatter ...")
    for mdx_file in mdx_files:
        add_frontmatter_to_mdx(mdx_file, notebooks_dir)
    print(f"   Updated frontmatter for {len(mdx_files)} file(s)")


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

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
from glob import glob
import html
import re
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

from pixeltable_doctools.config import get_mintlify_source_path
from pixeltable_doctools.mintlifier.utils import img_link


def convert_notebooks() -> None:
    """Convert all notebooks to MDX format (convenience function for CLI)."""
    repo_root = find_pixeltable_repo()
    output_dir = get_mintlify_source_path(repo_root) / 'notebooks'
    convert_notebooks_to_dir(repo_root, output_dir)


def preprocess_notebook(input_path: Path, output_path: Path) -> None:
    content = input_path.read_text()

    # For unknown reasons, when Jupyter outputs the results of a Python `print()` statement, it is rendered as
    # MIME type "text/markdown" (unlike the console output of a statement, which is rendered as "text/html").
    # This confuses Quarto, so we revert to "text/html" in such cases. This does not appear to have any negative
    # side effects, at least on the existing documentation base.
    content = content.replace('"text/markdown"', '"text/html"')

    # We want to convert Jupyter alerts into Mintlify callouts, but Quarto erases the <div> tags during processing.
    # So we guard them with special identifiers that we can replace in postprocessing.
    content = re.sub(
        r'<div class=\\"alert alert-block alert-([a-z]+)\\">(.*?)</div>',
        r'(((BEGIN-alert-\1)))\2(((END-alert)))',
        content,
        flags=re.DOTALL,
    )

    # Similarly, Quarto messes with certain HTML tags that aren't a problem for Mintlify, so we escape them.
    content = re.sub(r'<(li|/li)>', r'(((HTML-\1)))', content)

    output_path.write_text(content, encoding='utf-8')


def postprocess_mdx(mdx_file: Path, notebooks_dir: Path) -> None:
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
    kaggle_url = f"https://kaggle.com/kernels/welcome?src=https://github.com/{notebook_github_path}"
    colab_url = f"https://colab.research.google.com/github/{notebook_github_path}"
    download_url = f"https://raw.githubusercontent.com/pixeltable/pixeltable/refs/tags/release/{notebook_rel_path}"

    links = [
        img_link("openKaggle", kaggle_url, "https://kaggle.com/static/images/open-in-kaggle.svg", "Open in Kaggle"),
        img_link("openColab", colab_url, "https://colab.research.google.com/assets/colab-badge.svg", "Open in Colab"),
        img_link("downloadNotebook", download_url, "https://img.shields.io/badge/%E2%AC%87-Download%20Notebook-blue", "Download Notebook"),
    ]

    # Create enhanced frontmatter
    enhanced_frontmatter = f'''
        ---
        title: "{title}"
        icon: "notebook"
        ---
        {"&nbsp;&nbsp;".join(links)}

        <Tip>This documentation page is also available as an interactive notebook. You can launch the notebook in
        Kaggle or Colab, or download it for use with an IDE or local Jupyter installation, by clicking one of the
        above links.</Tip>
        '''
    enhanced_frontmatter = textwrap.dedent(enhanced_frontmatter).strip() + '\n'

    # We need to prepend './' to links like `data-sharing_files/figure-markdown_strict/cell-7-output-1.png`
    content_after_frontmatter = re.sub(rf'\(({mdx_file.stem}_files/figure-markdown_strict/[^)]*)\)', r'(./\1)', content_after_frontmatter)

    def replace_code_block(match: re.Match) -> str:
        code_content = match.group(1)
        # HTML escapes
        code_content = html.escape(code_content)
        # Replace braces and brackets with markdown escapes
        code_content = re.sub(r'([{}\[\]])', r'\\\1', code_content)
        # Replace spaces with &nbsp;
        code_content = code_content.replace(' ', '&nbsp;')
        return f"<pre style={{{{ 'margin': '0px', 'padding': '0px', 'background-color': 'transparent', 'color': 'black' }}}}>{code_content}</pre>"

    # Replace ``` text blocks with transparent <pre>
    content_after_frontmatter = re.sub(
        r'``` text(.*?)```',
        replace_code_block,
        content_after_frontmatter,
        flags=re.DOTALL,
    )

    TAG_MAP = {
        'info': 'Note',
        'success': 'Check',
        'warning': 'Warning',
        'danger': 'Danger',
    }

    def replace_callout(match: re.Match) -> str:
        tag = TAG_MAP.get(match.group(1), 'Note')
        text = match.group(2)
        return f'<{tag}>\n{text}\n</{tag}>'

    # Replace alert guards with Mintlify callouts
    content_after_frontmatter = re.sub(
        r'\(\(\(BEGIN-alert-([a-z]+)\)\)\)(.*?)\(\(\(END-alert\)\)\)',
        replace_callout,
        content_after_frontmatter,
        flags=re.DOTALL,
    )

    # Replace escaped HTML tags back to normal
    content_after_frontmatter = re.sub(r'\(\(\(HTML-([a-z/]*)\)\)\)', r'<\1>', content_after_frontmatter)

    # Replace links to docs.pixeltable.com with internal links
    content_after_frontmatter = re.sub(r'\(https?://docs\.pixeltable\.com/([^)]*?)\)', r'(/\1)', content_after_frontmatter)

    # Align table cells
    content_after_frontmatter = content_after_frontmatter.replace('<td>', '<td style="vertical-align: middle;">')
    content_after_frontmatter = content_after_frontmatter.replace('<td data-quarto-table-cell-role="th">', '<td style="vertical-align: middle;">')

    # Write back with enhanced frontmatter
    mdx_file.write_text(enhanced_frontmatter + content_after_frontmatter, encoding='utf-8')


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


def convert_notebooks_to_dir(repo_root: Path, target_dir: Path) -> None:
    """
    Convert all notebooks in repo_root/docs/notebooks to MDX format.

    Args:
        repo_root: Path to pixeltable repository root
        output_dir: Where to output the converted .mdx files
    """
    from pixeltable_doctools.convert_notebooks import convert_notebooks

    print("   Converting Jupyter notebooks to Mintlify MDX format...")
    print(f"      Repository: {repo_root}")
    print(f"      Output: {target_dir}")

    notebooks_dir = repo_root / 'docs' / 'notebooks'
    preprocess_dir = target_dir / 'pre-docs' / 'notebooks'
    output_dir = target_dir / 'docs' / 'notebooks'

    # Check for quarto
    if not shutil.which('quarto'):
        raise RuntimeError("Quarto is not installed.")

    # Verify source exists
    if not notebooks_dir.exists():
        raise FileNotFoundError(f"Notebooks directory not found: {notebooks_dir}")

    # Find notebooks
    notebooks = [file for file in notebooks_dir.rglob('*.ipynb') if '.ipynb_checkpoints' not in file.parts]
    if not notebooks:
        raise RuntimeError(f"No notebooks found: {notebooks_dir}")

    print(f"   {len(notebooks)} total notebook(s).")

    notebooks_to_convert: list[Path] = []
    for notebook in notebooks:
        relpath = notebook.relative_to(notebooks_dir)
        output_path = output_dir / relpath.with_suffix('.mdx')
        if not output_path.exists() or notebook.stat().st_mtime > output_path.stat().st_mtime:
            pre_path = preprocess_dir / relpath
            pre_path.parent.mkdir(parents=True, exist_ok=True)
            preprocess_notebook(notebook, pre_path)
            notebooks_to_convert.append(pre_path)

    print(f"   {len(notebooks_to_convert)} notebook(s) need conversion.")

    if not notebooks_to_convert:
        return

    print(f"   Preparing Quarto configuration ...")
    quarto_cfg_path = Path(convert_notebooks.__file__).parent / '_quarto.yml'
    shutil.copy2(quarto_cfg_path, preprocess_dir / '_quarto.yml')

    print(f"   Running Quarto to convert notebooks ...")
    print(f"      Source: {preprocess_dir}")
    print(f"      Output: {output_dir}")

    try:
        # Run quarto render
        subprocess.run(
            ['quarto', 'render', *[str(f) for f in notebooks_to_convert], '--quiet', '--to', 'docusaurus-md', '--output-dir', str(output_dir)],
            cwd=str(preprocess_dir),
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
        postprocess_mdx(mdx_file, notebooks_dir)
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

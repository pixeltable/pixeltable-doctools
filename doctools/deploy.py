#!/usr/bin/env python3
"""
Deploy documentation.
"""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from time import sleep
from typing import Any

from doctools.build import validate_mintlify_docs
from doctools.mintlifier.docsjson_updater import DocsJsonUpdater


def find_sdk_tab(docs: dict[str, Any]) -> dict[str, Any]:
    if 'navigation' in docs and 'tabs' in docs['navigation']:
        for tab in docs['navigation']['tabs']:
            if tab.get('tab') == 'Pixeltable SDK':
                return tab
    return None


def merge_sdk_dropdowns(existing: dict, new: dict) -> None:
    """
    Merge dropdowns from the existing navigation structure into the new one; prefer the new
    one when there is a conflict.
    """
    # Find SDK tab in each version
    existing_sdk_tab = find_sdk_tab(existing)
    new_sdk_tab = find_sdk_tab(new)

    # Merge version dropdowns from production into generated
    existing_dropdowns: list[dict] = existing_sdk_tab.get('dropdowns', [])
    new_dropdowns: list[dict] = new_sdk_tab.get('dropdowns', [])

    for dropdown in existing_dropdowns:
        dropdown['icon'] = 'archive'

    merged_dropdowns = {dropdown['dropdown']: dropdown for dropdown in existing_dropdowns}
    merged_dropdowns.update({dropdown['dropdown']: dropdown for dropdown in new_dropdowns})

    new_sdk_tab['dropdowns'] = DocsJsonUpdater.sort_dropdowns(merged_dropdowns.values())


def deploy(pxt_version: str, pxt_repo_dir: Path, temp_dir: Path, branch: str) -> None:
    """
    Deploy generated docs.

    Args:
        output_dir: Directory containing generated docs
    """
    docs_target_dir = pxt_repo_dir / 'docs' / 'target'
    if not docs_target_dir.exists():
        print(f"Error: Docs target directory {docs_target_dir} does not exist. Please build the docs first.")
        sys.exit(1)

    display_version: str
    if branch == 'dev':
        display_version = pxt_version
    else:
        # For prod/staging deployments, truncate to major.minor.patch. We do this so that we can redeploy
        # minor changes to the docs post-release, without having to update the repo version tag.
        # If this isn't a production release version, we need to substract one from the patch number to
        # account for our numbering scheme (0.4.23.dev15 should actually publish as 0.4.22 docs).
        version_split = pxt_version.split('.')
        if len(version_split) == 3:
            display_version = pxt_version
        else:
            patch_num = int(version_split[2])
            assert patch_num > 0
            display_version = '.'.join([version_split[0], version_split[1], str(patch_num - 1)])

    # Retrieve current sha
    result = subprocess.run(
        ('git', 'rev-parse', 'HEAD'),
        cwd=str(pxt_repo_dir),
        capture_output=True,
        text=True,
        check=True
    )
    pxt_sha = result.stdout.strip()[:8]

    print(f"\nAssembling docs v{display_version} from {pxt_sha} into {branch!r} branch ...")

    if pxt_version != display_version:
        print(f"   NOTE: There have been changes since the official v{display_version} release.")

    docs_repo_dir = Path(temp_dir) / 'pixeltable-docs-www'

    # Clone the docs repository
    print(f"   Cloning into {docs_repo_dir} ...")
    subprocess.run(
        ('git', 'clone', '-b', branch, 'https://github.com/pixeltable/pixeltable-docs-www.git', str(docs_repo_dir)),
        capture_output=True,
        text=True,
        check=True
    )

    # Load docs JSON
    existing_docs_json: dict[str, Any] = {}
    new_docs_json: dict[str, Any] = {}

    with open(docs_repo_dir / 'docs.json', 'r', encoding='utf-8') as fp:
        existing_docs_json = json.load(fp)

    with open(docs_target_dir / 'docs.json', 'r', encoding='utf-8') as fp:
        new_docs_json = json.load(fp)

    # Clean existing repo dir
    for item in docs_repo_dir.iterdir():
        if item.name.startswith('.git'):
            continue  # Skip .git directory
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()

    # Copy all docs from output
    print(f"   Copying documentation files ...")
    for item in docs_target_dir.iterdir():
        dest = docs_repo_dir / item.name
        if item.is_dir():
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(item, dest)
        else:
            shutil.copy2(item, dest)

    sdk_tab = find_sdk_tab(new_docs_json)
    assert len(sdk_tab['dropdowns']) == 1 and sdk_tab['dropdowns'][0]['dropdown'] == "latest"
    dropdown_copy = sdk_tab['dropdowns'][0].copy()
    dropdown_copy['dropdown'] = f'v{display_version}'
    sdk_tab['dropdowns'].append(dropdown_copy)

    # Merge existing dropdowns if a prod/staging deployment
    if branch != 'dev':
        print(f"   Merging SDK dropdowns in docs.json ...")
        merge_sdk_dropdowns(existing_docs_json, new_docs_json)

    with open(docs_repo_dir / 'docs.json', 'w', encoding='utf-8') as fp:
        json.dump(new_docs_json, fp, indent=2)

    errors = validate_mintlify_docs(docs_repo_dir)
    if errors and branch != 'dev':
        print(f"\nERROR: Documentation has parsing errors. Fix before deploying to {branch!r}, or deploy to 'dev' instead.")
        sys.exit(1)

    # Add changes to local repo
    subprocess.run(('git', 'add', '-A'), cwd=str(docs_repo_dir), check=True)
    result = subprocess.run(
        ('git', 'diff', '--staged', '--quiet'),
        cwd=str(docs_repo_dir)
    )

    if result.returncode != 0:  # There are changes
        print(f"\nCommitting changes to {branch!r} branch ...")
        subprocess.run(
            ('git', 'commit', '-m', f'Deploy documentation {display_version} from {pxt_sha}'),
            cwd=str(docs_repo_dir),
            check=True
        )
        print(f"\nPushing to origin ...")
        subprocess.run(
            ('git', 'push', 'origin', branch),
            cwd=str(docs_repo_dir),
            check=True
        )
        print(f"   Deployed successfully")

    else:
        print(f"\nThere are no changes to deploy.")

    print(f"\nView at: https://pixeltable-{branch}.mintlify.app/sdk/latest")


def main():
    """Main entry point."""
    if len(sys.argv) != 2:
        print(f"Usage: deploy.py <dev|stage|prod>")
        sys.exit(1)

    target = sys.argv[1]
    if target not in ('dev', 'stage', 'prod'):
        print(f"Error: Invalid target {target!r}. Must be one of: dev, stage, prod.")
        sys.exit(1)

    print(f"Deploying documentation for target: {target}")

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

    with tempfile.TemporaryDirectory() as temp_dir:
        deploy(pxt.__version__, pxt_repo_dir, temp_dir, target)


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
Fetch and convert GitHub releases to Mintlify MDX format.

This script:
1. Fetches releases from GitHub API (pixeltable/pixeltable/releases)
2. Converts each release to MDX format
3. Outputs to docs/mintlify/changelog/ (gitignored, never committed)
4. Preserves contributor links and GitHub markdown formatting
"""

import json
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any


def fetch_releases_from_github(repo: str = "pixeltable/pixeltable", max_releases: int = 50) -> list[dict[str, Any]]:
    """
    Fetch releases from GitHub API.

    Args:
        repo: GitHub repository in format 'owner/repo'
        max_releases: Maximum number of releases to fetch

    Returns:
        List of release dictionaries from GitHub API
    """
    url = f"https://api.github.com/repos/{repo}/releases?per_page={max_releases}"

    try:
        with urllib.request.urlopen(url) as response:
            releases = json.loads(response.read().decode())
        return releases
    except Exception as e:
        raise RuntimeError(f"Failed to fetch releases from GitHub: {e}")


def convert_release_to_mdx(release: dict[str, Any]) -> str:
    """
    Convert a GitHub release to Mintlify MDX format.

    Args:
        release: Release dictionary from GitHub API

    Returns:
        MDX formatted string
    """
    tag_name = release.get('tag_name', 'Unknown')
    name = release.get('name', tag_name)
    published_at = release.get('published_at', '')
    author = release.get('author', {}).get('login', 'Unknown')
    html_url = release.get('html_url', '')
    body = release.get('body', '').strip()

    # Parse date
    if published_at:
        try:
            date_obj = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
            formatted_date = date_obj.strftime('%B %d, %Y')
        except Exception:
            formatted_date = published_at
    else:
        formatted_date = 'Unknown date'

    # Build MDX content
    mdx_content = f"""---
title: "{name}"
description: "Released {formatted_date}"
---

# {name}

**Released:** {formatted_date}
**Author:** [@{author}](https://github.com/{author})
**View on GitHub:** [{tag_name}]({html_url})

---

{body}
"""

    return mdx_content


def generate_changelog_to_dir(output_dir: Path, repo: str = "pixeltable/pixeltable") -> None:
    """
    Generate changelog MDX files from GitHub releases.

    Args:
        output_dir: Where to output the .mdx files
        repo: GitHub repository in format 'owner/repo'
    """
    print("📰 Fetching releases from GitHub...")
    print(f"   Repository: {repo}")
    print(f"   Output: {output_dir}")

    # Fetch releases
    try:
        releases = fetch_releases_from_github(repo)
    except Exception as e:
        raise RuntimeError(f"Failed to fetch releases: {e}")

    if not releases:
        print(f"⚠️  No releases found")
        return

    print(f"📚 Found {len(releases)} release(s)")

    # Clean output directory
    if output_dir.exists():
        print(f"🧹 Cleaning output directory: {output_dir}")
        import shutil
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)

    # Convert each release to MDX
    print(f"\n🔨 Converting releases to MDX...")

    for release in releases:
        tag_name = release.get('tag_name', 'unknown')

        # Sanitize filename (remove 'v' prefix if present)
        filename = tag_name.lstrip('v').replace('/', '-') + '.mdx'
        output_path = output_dir / filename

        try:
            mdx_content = convert_release_to_mdx(release)
            output_path.write_text(mdx_content)
            print(f"   ✅ {filename}")
        except Exception as e:
            print(f"   ⚠️  Failed to convert {tag_name}: {e}")
            continue

    print(f"\n💪 Changelog generated successfully!")
    print(f"   Output: {output_dir}")
    print(f"   Files: {len(list(output_dir.glob('*.mdx')))}")


def main():
    """Main entry point for CLI."""
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description='Fetch GitHub releases and convert to Mintlify MDX format'
    )
    parser.add_argument(
        '--output',
        type=Path,
        required=True,
        help='Output directory for MDX files'
    )
    parser.add_argument(
        '--repo',
        default='pixeltable/pixeltable',
        help='GitHub repository (default: pixeltable/pixeltable)'
    )

    args = parser.parse_args()

    try:
        generate_changelog_to_dir(args.output, args.repo)
    except Exception as e:
        print(f"\n❌ Failed to generate changelog: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()

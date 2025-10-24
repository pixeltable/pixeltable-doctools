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
import re
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


def shorten_pr_links(text: str) -> str:
    """
    Shorten GitHub PR links to just show PR number as clickable link.

    Converts:
        in https://github.com/pixeltable/pixeltable/pull/289
    To:
        in [#289](https://github.com/pixeltable/pixeltable/pull/289)

    Matches GitHub's native display format (shows #289 but links to full URL).

    Args:
        text: Markdown text with PR links

    Returns:
        Text with shortened PR links
    """
    # Match full PR URLs and replace with [#number](url) markdown link
    pattern = r'https://github\.com/pixeltable/pixeltable/pull/(\d+)'
    replacement = r'[#\1](https://github.com/pixeltable/pixeltable/pull/\1)'
    return re.sub(pattern, replacement, text)


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
    Generate consolidated changelog MDX file from GitHub releases.

    Args:
        output_dir: Where to output the .mdx file
        repo: GitHub repository in format 'owner/repo'
    """
    print("⚡ Fetching releases from GitHub...")
    print(f"   Repository: {repo}")
    print(f"   Output: {output_dir}")

    # Fetch releases
    try:
        releases = fetch_releases_from_github(repo)
    except Exception as e:
        raise RuntimeError(f"Failed to fetch releases: {e}")

    if not releases:
        print(f"☠️  No releases found")
        return

    print(f"🔥 Found {len(releases)} release(s)")

    # Clean output directory
    if output_dir.exists():
        print(f"💀 Cleaning output directory: {output_dir}")
        import shutil
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)

    # Create consolidated changelog
    print(f"⚠️  Creating consolidated changelog...")
    changelog_content = """---
title: "Changelog"
description: "Release history and updates for Pixeltable"
---

## Contributors

Pixeltable is built by a vibrant community of contributors. We're grateful for everyone who has helped make Pixeltable better!

**Want to contribute?** Check out our [Contributing Guide](https://github.com/pixeltable/pixeltable/blob/main/CONTRIBUTING.md) to get started.

**Top Contributors:** View our amazing contributors on [GitHub](https://github.com/pixeltable/pixeltable/graphs/contributors).

---

## Release History

View the complete release history for Pixeltable below. Each release includes detailed information about new features, bug fixes, and improvements.

For the latest release information, visit our [GitHub Releases page](https://github.com/pixeltable/pixeltable/releases).

---

"""

    # Add all releases inline
    for release in releases:
        tag_name = release.get('tag_name', 'unknown')
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

        # Add release section (using ### to nest under "Release History")
        changelog_content += f"### {name}\n\n"
        changelog_content += f"**Released:** {formatted_date}  \n"
        changelog_content += f"**Author:** [@{author}](https://github.com/{author})  \n"
        changelog_content += f"**View on GitHub:** [{tag_name}]({html_url})\n\n"

        # Convert H2 sections to H4 in the body for proper sidebar hierarchy
        # GitHub release notes use ## for "What's Changed" and "New Contributors"
        # Handle both mid-body (after newline) and start-of-body cases
        body_formatted = body.replace('\n## ', '\n#### ')
        if body_formatted.startswith('## '):
            body_formatted = '#### ' + body_formatted[3:]

        # Shorten PR links to just show (#number) instead of full URLs
        body_formatted = shorten_pr_links(body_formatted)

        changelog_content += f"{body_formatted}\n\n"
        changelog_content += "---\n\n"

    # Write consolidated changelog
    changelog_path = output_dir / 'changelog.mdx'
    changelog_path.write_text(changelog_content)
    print(f"   ✅ changelog.mdx (consolidated)")

    print(f"💥 Changelog generated successfully!")
    print(f"   Output: {output_dir}")
    print(f"   File: changelog.mdx with {len(releases)} releases")


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

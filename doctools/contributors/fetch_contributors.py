#!/usr/bin/env python3
"""
Fetch and display GitHub contributors for Pixeltable.

This script:
1. Fetches all contributors from GitHub API (pixeltable/pixeltable)
2. Gets detailed information including avatar, contributions count, and profile
3. Generates an MDX page showcasing all contributors
4. Outputs to docs/mintlify/community/contributors.mdx
"""

import json
import urllib.request
from pathlib import Path
from typing import Any


def fetch_contributors_from_github(repo: str = "pixeltable/pixeltable") -> list[dict[str, Any]]:
    """
    Fetch all contributors from GitHub API.

    Args:
        repo: GitHub repository in format 'owner/repo'

    Returns:
        List of contributor dictionaries from GitHub API
    """
    url = f"https://api.github.com/repos/{repo}/contributors?per_page=100"

    contributors = []

    try:
        while url:
            with urllib.request.urlopen(url) as response:
                page_contributors = json.loads(response.read().decode())
                contributors.extend(page_contributors)

                # Check for pagination link in headers
                link_header = response.headers.get('Link', '')
                url = None
                for link in link_header.split(','):
                    if 'rel="next"' in link:
                        url = link[link.index('<') + 1:link.index('>')]
                        break

        return contributors
    except Exception as e:
        raise RuntimeError(f"Failed to fetch contributors from GitHub: {e}")


def generate_contributors_page(output_dir: Path, repo: str = "pixeltable/pixeltable") -> None:
    """
    Generate contributors page MDX file from GitHub contributors.

    Args:
        output_dir: Where to output the .mdx file
        repo: GitHub repository in format 'owner/repo'
    """
    print("👥 Fetching contributors from GitHub...")
    print(f"   Repository: {repo}")
    print(f"   Output: {output_dir}")

    # Fetch contributors
    try:
        contributors = fetch_contributors_from_github(repo)
    except Exception as e:
        raise RuntimeError(f"Failed to fetch contributors: {e}")

    if not contributors:
        print(f"⚠️  No contributors found")
        return

    print(f"🎉 Found {len(contributors)} contributor(s)")

    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    # Build contributors page content
    content = """---
title: "Our Contributors"
description: "Meet the amazing people who make Pixeltable possible"
---

Pixeltable is built by a vibrant community of developers, researchers, and enthusiasts. We're grateful for every contribution, from code to documentation to bug reports.

## Core Team & Community Contributors

The following amazing people have contributed to Pixeltable:

"""

    # Sort contributors by number of contributions (descending)
    contributors.sort(key=lambda x: x.get('contributions', 0), reverse=True)

    # Create a grid of contributor cards
    for contributor in contributors:
        login = contributor.get('login', 'Unknown')
        avatar_url = contributor.get('avatar_url', '')
        html_url = contributor.get('html_url', '')
        contributions = contributor.get('contributions', 0)

        # Skip bots
        if contributor.get('type') == 'Bot':
            continue

        content += f"""
<div style="display: inline-block; margin: 10px; text-align: center; width: 150px;">
  <a href="{html_url}" target="_blank" style="text-decoration: none;">
    <img src="{avatar_url}" alt="{login}" style="border-radius: 50%; width: 100px; height: 100px; border: 2px solid #e5e7eb;" />
    <div style="margin-top: 8px; font-weight: 600; color: #1f2937;">@{login}</div>
    <div style="font-size: 0.875rem; color: #6b7280;">{contributions} contribution{'s' if contributions != 1 else ''}</div>
  </a>
</div>
"""

    content += """

---

## Join Our Community

Want to see your name here? We'd love your contributions! Check out our [GitHub repository](https://github.com/pixeltable/pixeltable) to get started.

- 🐛 Report bugs
- 💡 Suggest features
- 📝 Improve documentation
- 🔧 Submit pull requests

Every contribution, no matter how small, makes a difference. Thank you for being part of the Pixeltable community! 🙏
"""

    # Write the file
    contributors_path = output_dir / 'contributors.mdx'
    contributors_path.write_text(content)
    print(f"   ✅ contributors.mdx")

    print(f"\n💪 Contributors page generated successfully!")
    print(f"   Output: {contributors_path}")
    print(f"   Total contributors: {len([c for c in contributors if c.get('type') != 'Bot'])}")


def main():
    """Main entry point for CLI."""
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description='Fetch GitHub contributors and generate contributors page'
    )
    parser.add_argument(
        '--output',
        type=Path,
        required=True,
        help='Output directory for MDX file'
    )
    parser.add_argument(
        '--repo',
        default='pixeltable/pixeltable',
        help='GitHub repository (default: pixeltable/pixeltable)'
    )

    args = parser.parse_args()

    try:
        generate_contributors_page(args.output, args.repo)
    except Exception as e:
        print(f"\n❌ Failed to generate contributors page: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()

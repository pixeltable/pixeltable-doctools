"""
Docs.json updater for Mintlifier documentation.

Updates the Mintlify navigation structure with generated SDK documentation.
"""

import json
from pathlib import Path
from typing import Dict, List
from datetime import datetime
import shutil


class DocsJsonUpdater:
    """Updates docs.json with SDK navigation structure."""

    def __init__(self, docs_json_path: Path, sdk_tab_name: str):
        """Initialize with path to docs.json and SDK tab name."""
        self.docs_json_path = docs_json_path
        self.sdk_tab_name = sdk_tab_name
        self.docs_config = None

    def load(self):
        """Load docs.json."""
        # Load docs.json
        with open(self.docs_json_path) as f:
            self.docs_config = json.load(f)

        print(f"📋 Loaded docs.json with {len(self.docs_config.get('navigation', {}).get('tabs', []))} tabs")

    def update_navigation(self, navigation_structure: Dict):
        """Update navigation with SDK documentation structure."""
        if not self.docs_config:
            raise ValueError("docs.json not loaded. Call load() first.")

        # Ensure navigation structure exists
        if "navigation" not in self.docs_config:
            self.docs_config["navigation"] = {"tabs": []}
        if "tabs" not in self.docs_config["navigation"]:
            self.docs_config["navigation"]["tabs"] = []

        tabs = self.docs_config["navigation"]["tabs"]

        # Find existing SDK or API Reference tab
        sdk_tab_index = None
        for i, tab in enumerate(tabs):
            if tab.get("tab") == self.sdk_tab_name:
                sdk_tab_index = i
                break
            elif tab.get("tab") == "API Reference" and tab.get("href"):
                # Found the old external link tab
                sdk_tab_index = i
                break

        # Update or add SDK tab
        if sdk_tab_index is not None:
            existing_tab = tabs[sdk_tab_index]

            # If existing tab has dropdowns, merge them
            if "dropdowns" in existing_tab and "dropdowns" in navigation_structure:
                new_dropdown = navigation_structure["dropdowns"][0]  # The new version dropdown
                new_version = new_dropdown["dropdown"]

                # Extract major.minor prefix from new version (e.g., v0.4.17 -> v0.4)
                import re
                match = re.match(r'(v\d+\.\d+)', new_version)
                major_minor_prefix = match.group(1) if match else None

                # Remove any existing dropdowns with the same major.minor prefix
                if major_minor_prefix:
                    original_count = len(existing_tab["dropdowns"])
                    existing_tab["dropdowns"] = [
                        d for d in existing_tab["dropdowns"]
                        if not d.get("dropdown", "").startswith(major_minor_prefix)
                    ]
                    removed_count = original_count - len(existing_tab["dropdowns"])
                    if removed_count > 0:
                        print(f"📝 Removed {removed_count} old version(s) with prefix {major_minor_prefix}")

                # Add the new version dropdown
                existing_tab["dropdowns"].append(new_dropdown)
                print(f"📝 Added new dropdown: {new_version}")

                # Sort dropdowns by version (newest first)
                existing_tab["dropdowns"] = self._sort_dropdowns(existing_tab["dropdowns"])

                # Preserve other fields from new structure (like tab name)
                existing_tab["tab"] = navigation_structure["tab"]
            else:
                # No dropdowns, replace entire tab
                print(f"📝 Replacing tab at index {sdk_tab_index}: {tabs[sdk_tab_index].get('tab', 'Unknown')}")
                tabs[sdk_tab_index] = navigation_structure
        else:
            print(f"📝 Adding new tab: {self.sdk_tab_name}")
            tabs.append(navigation_structure)

    def save(self):
        """Save updated docs.json."""
        if not self.docs_config:
            raise ValueError("No configuration to save")

        # Write with proper formatting
        with open(self.docs_json_path, "w") as f:
            json.dump(self.docs_config, f, indent=2)

        print(f"✅ Updated {self.docs_json_path}")

    def _sort_dropdowns(self, dropdowns: List[Dict]) -> List[Dict]:
        """Sort dropdowns by version number in descending order (newest first).

        Args:
            dropdowns: List of dropdown dictionaries

        Returns:
            Sorted list with newest versions first
        """
        def parse_version(dropdown: Dict) -> tuple:
            """Parse version string to tuple for sorting."""
            version_str = dropdown.get("dropdown", "")

            # Handle "latest" specially - always put it first
            if version_str == "latest":
                return (float('inf'),)

            # Parse version like "v0.4" -> (0, 4)
            # Strip 'v' prefix and split by '.'
            if version_str.startswith("v"):
                version_str = version_str[1:]

            try:
                parts = [int(x) for x in version_str.split('.')]
                return tuple(parts)
            except (ValueError, AttributeError):
                # If parsing fails, return (0,) so it sorts last
                return (0,)

        # Sort by version in descending order (reverse=True for newest first)
        return sorted(dropdowns, key=parse_version, reverse=True)

    def validate_structure(self, navigation_structure: Dict) -> List[str]:
        """Validate navigation structure and return any warnings."""
        warnings = []

        # Check for required fields
        if "tab" not in navigation_structure:
            warnings.append("Missing 'tab' field in navigation structure")

        # Check if it has either groups or dropdowns
        if "groups" not in navigation_structure and "dropdowns" not in navigation_structure:
            warnings.append("Missing 'groups' or 'dropdowns' field in navigation structure")

        # Check for empty groups
        if navigation_structure.get("groups"):
            for group in navigation_structure["groups"]:
                if not group.get("pages") and not group.get("groups"):
                    warnings.append(f"Empty group: {group.get('group', 'Unknown')}")

        # Check for duplicate page paths
        all_pages = []

        def collect_pages(items):
            for item in items:
                if "pages" in item:
                    for page in item["pages"]:
                        # Skip nested groups (they're dicts, not strings)
                        if isinstance(page, str):
                            all_pages.append(page)
                        elif isinstance(page, dict) and "pages" in page:
                            # Recursively collect from nested group
                            collect_pages([page])
                if "groups" in item:
                    collect_pages(item["groups"])

        # Collect from groups or dropdowns
        if navigation_structure.get("groups"):
            collect_pages(navigation_structure["groups"])
        elif navigation_structure.get("dropdowns"):
            # Process dropdowns
            for dropdown in navigation_structure["dropdowns"]:
                if dropdown.get("pages"):
                    for page in dropdown["pages"]:
                        if isinstance(page, str):
                            all_pages.append(page)
                if dropdown.get("groups"):
                    collect_pages(dropdown["groups"])

        seen = set()
        for page in all_pages:
            if page in seen:
                warnings.append(f"Duplicate page path: {page}")
            seen.add(page)

        return warnings

"""
Shared configuration for doctools.

This module provides centralized path configuration for all doctools scripts.
"""

from pathlib import Path

# Source directory for Mintlify documentation
# All doctools scripts should reference this instead of hardcoding paths
MINTLIFY_SOURCE_DIR = 'mintlify'  # Changed from 'mintlify-src' (2025-10-19)

# Target directory for built documentation
MINTLIFY_TARGET_DIR = 'target'


def get_mintlify_source_path(repo_root: Path) -> Path:
    """Get the path to the Mintlify source directory.

    Args:
        repo_root: Path to the pixeltable repository root

    Returns:
        Path to docs/mintlify/ directory
    """
    return repo_root / 'docs' / MINTLIFY_SOURCE_DIR


def get_mintlify_target_path(repo_root: Path) -> Path:
    """Get the path to the Mintlify build target directory.

    Args:
        repo_root: Path to the pixeltable repository root

    Returns:
        Path to docs/target/ directory
    """
    return repo_root / 'docs' / MINTLIFY_TARGET_DIR

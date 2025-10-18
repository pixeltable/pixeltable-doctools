#!/usr/bin/env python3
"""
Validate that OPML documentation matches the actual public API.

This tool scans the Pixeltable codebase using Python inspect to find all
public API items, then compares against what's documented in the OPML file.

Reports:
- Items in code but missing from OPML
- Items in OPML but not found in code
- Empty modules in OPML that have content in code
"""

import argparse
import importlib
import inspect
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Set, Tuple


class APIScanner:
    """Scans Python code to find public API items."""

    def __init__(self, package_name: str = "pixeltable"):
        self.package_name = package_name
        self.api_items = {}

    def scan(self) -> Dict[str, List[str]]:
        """
        Scan the package and return all public API items.

        Returns:
            Dict mapping module paths to lists of public items
        """
        print("📋 Scan Criteria:")
        print("   • Using __all__ if defined, otherwise all non-private symbols")
        print("   • Main module: Include all items in __all__")
        print("   • Submodules: Include items defined in that module or UDFs")
        print("   • UDFs detected by: isinstance of CallableFunction (created by @pxt.udf)")
        print("   • Classes: Scan for methods, properties, and descriptors")
        print()

        try:
            # Import the main package
            package = importlib.import_module(self.package_name)

            # Scan the main module
            self._scan_module(self.package_name, package)

            # Scan known submodules
            submodules = [
                'functions.audio',
                'functions.date',
                'functions.image',
                'functions.json',
                'functions.math',
                'functions.string',
                'functions.timestamp',
                'functions.video',
                'functions.yolox',
                'functions.whisperx',
                'functions.openai',
                'functions.anthropic',
                'functions.gemini',
                'functions.bedrock',
                'functions.groq',
                'functions.replicate',
                'functions.together',
                'functions.fireworks',
                'functions.mistralai',
                'functions.deepseek',
                'functions.ollama',
                'functions.llama_cpp',
                'functions.whisper',
                'functions.vision',
                'functions.huggingface',
                'iterators',
                'io',
            ]

            for submodule in submodules:
                try:
                    full_name = f"{self.package_name}.{submodule}"
                    module = importlib.import_module(full_name)
                    self._scan_module(full_name, module)
                except (ImportError, AttributeError) as e:
                    print(f"⚠️  Could not import {full_name}: {e}", file=sys.stderr)

            return self.api_items

        except ImportError as e:
            print(f"❌ Could not import {self.package_name}: {e}", file=sys.stderr)
            print("   Make sure pixeltable is installed in the current environment", file=sys.stderr)
            sys.exit(1)

    def _scan_module(self, module_path: str, module):
        """Scan a single module for public items."""
        items = []

        # Use __all__ if it exists, otherwise use dir()
        if hasattr(module, '__all__'):
            public_names = module.__all__
        else:
            public_names = [name for name in dir(module) if not name.startswith('_')]

        # Get all public attributes
        for name in public_names:
            try:
                obj = getattr(module, name)

                # Check if it's a UDF by checking the type name
                # UDFs are wrapped and may have different __module__, so we check this first
                # All UDFs created with @pxt.udf decorator are instances of CallableFunction
                is_udf = type(obj).__name__ == 'CallableFunction'

                # For submodules (not main package), only include items defined in that module
                # Exception: Always include UDFs since they're wrapped and have different __module__
                if module_path != self.package_name and not is_udf:
                    # Check if it's defined in this module (not imported)
                    if hasattr(obj, '__module__') and not obj.__module__.startswith(module_path):
                        continue

                # Categorize the item
                if inspect.isclass(obj):
                    items.append(('class', name))
                    # Also scan class methods
                    self._scan_class(f"{module_path}.{name}", obj)
                elif inspect.isfunction(obj) or callable(obj):
                    if is_udf:
                        items.append(('udf', name))
                    else:
                        items.append(('func', name))

            except (AttributeError, TypeError):
                # Skip items that can't be inspected
                continue

        if items:
            self.api_items[module_path] = items

    def _scan_class(self, class_path: str, cls):
        """Scan a class for public methods, properties, and attributes."""
        items = []

        for name in dir(cls):
            # Skip private and special methods
            if name.startswith('_'):
                continue

            try:
                obj = getattr(cls, name)

                # Check for property
                if isinstance(inspect.getattr_static(cls, name), property):
                    items.append(('property', name))
                # Check for method/function
                elif inspect.ismethod(obj) or inspect.isfunction(obj):
                    items.append(('method', name))
                # Check for other descriptors (e.g., cached_property)
                elif hasattr(inspect.getattr_static(cls, name), '__get__'):
                    items.append(('property', name))

            except (AttributeError, TypeError):
                continue

        if items:
            self.api_items[class_path] = items


class OPMLParser:
    """Parses OPML file to extract documented items."""

    def __init__(self, opml_path: Path):
        self.opml_path = opml_path
        self.opml_items = {}

    def parse(self) -> Dict[str, List[str]]:
        """
        Parse the OPML file and return all documented items.

        Returns:
            Dict mapping module paths to lists of documented items
        """
        tree = ET.parse(self.opml_path)
        root = tree.getroot()

        # Find all outline elements
        for outline in root.iter('outline'):
            text = outline.get('text', '')

            if '|' in text:
                item_type, path = text.split('|', 1)

                if item_type == 'module':
                    # Get children of this module
                    children = []
                    for child in outline:
                        child_text = child.get('text', '')
                        if '|' in child_text:
                            child_type, child_path = child_text.split('|', 1)
                            child_name = child_path.split('.')[-1]
                            children.append((child_type, child_name))

                    self.opml_items[path] = children

                elif item_type == 'class':
                    # Get methods of this class
                    methods = []
                    for child in outline:
                        child_text = child.get('text', '')
                        if '|' in child_text:
                            child_type, child_path = child_text.split('|', 1)
                            child_name = child_path.split('.')[-1]
                            methods.append((child_type, child_name))

                    self.opml_items[path] = methods

        return self.opml_items


class APIValidator:
    """Compares scanned API against OPML documentation."""

    def __init__(self, api_items: Dict, opml_items: Dict):
        self.api_items = api_items
        self.opml_items = opml_items

    def validate(self) -> Tuple[List[str], List[str], List[str]]:
        """
        Compare API items against OPML.

        Returns:
            Tuple of (missing_from_opml, not_in_code, empty_modules)
        """
        missing_from_opml = []
        not_in_code = []
        empty_modules = []

        # Check for items in code but not in OPML
        for module_path, items in self.api_items.items():
            if module_path not in self.opml_items:
                # Entire module missing from OPML
                for item_type, item_name in items:
                    missing_from_opml.append(f"{module_path}.{item_name} ({item_type})")
            else:
                # Check individual items
                opml_item_names = {name for _, name in self.opml_items[module_path]}
                for item_type, item_name in items:
                    if item_name not in opml_item_names:
                        missing_from_opml.append(f"{module_path}.{item_name} ({item_type})")

        # Check for items in OPML but not in code
        for module_path, items in self.opml_items.items():
            if not items:
                # Empty module in OPML
                if module_path in self.api_items and self.api_items[module_path]:
                    empty_modules.append(f"{module_path} (has {len(self.api_items[module_path])} items in code)")
            elif module_path in self.api_items:
                # Check individual items
                api_item_names = {name for _, name in self.api_items[module_path]}
                for item_type, item_name in items:
                    if item_name not in api_item_names:
                        not_in_code.append(f"{module_path}.{item_name} ({item_type})")
            else:
                # Module in OPML but not found in code
                for item_type, item_name in items:
                    not_in_code.append(f"{module_path}.{item_name} ({item_type}) - module not found")

        return missing_from_opml, not_in_code, empty_modules


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Validate OPML documentation against actual Python API'
    )
    parser.add_argument(
        '--opml',
        type=Path,
        help='Path to OPML file (default: auto-detect from pixeltable repo)'
    )
    parser.add_argument(
        '--package',
        default='pixeltable',
        help='Package to scan (default: pixeltable)'
    )

    args = parser.parse_args()

    # Auto-detect OPML path if not provided
    if not args.opml:
        # Try to find pixeltable repo
        cwd = Path.cwd()
        candidates = [
            cwd / 'docs' / 'public_api.opml',
            cwd.parent / 'docs' / 'public_api.opml',
            cwd.parent.parent / 'docs' / 'public_api.opml',
        ]

        for candidate in candidates:
            if candidate.exists():
                args.opml = candidate
                break

        if not args.opml:
            print("❌ Could not find public_api.opml", file=sys.stderr)
            print("   Please specify --opml path or run from pixeltable repository", file=sys.stderr)
            sys.exit(1)

    print(f"📊 Validating API documentation")
    print(f"   OPML: {args.opml}")
    print(f"   Package: {args.package}")
    print()

    # Scan the API
    print("🔍 Scanning Python API...")
    scanner = APIScanner(args.package)
    api_items = scanner.scan()
    print(f"   Found {len(api_items)} modules with {sum(len(items) for items in api_items.values())} items")

    # Parse OPML
    print("📖 Parsing OPML...")
    parser = OPMLParser(args.opml)
    opml_items = parser.parse()
    print(f"   Found {len(opml_items)} modules with {sum(len(items) for items in opml_items.values())} items")
    print()

    # Validate
    print("⚖️  Comparing...")
    validator = APIValidator(api_items, opml_items)
    missing_from_opml, not_in_code, empty_modules = validator.validate()

    # Report results
    print("=" * 70)
    print("VALIDATION REPORT")
    print("=" * 70)
    print()

    if empty_modules:
        print("⚠️  EMPTY MODULES IN OPML (have content in code):")
        for item in sorted(empty_modules):
            print(f"   - {item}")
        print()

    if missing_from_opml:
        print(f"❌ MISSING FROM OPML ({len(missing_from_opml)} items):")
        for item in sorted(missing_from_opml)[:20]:  # Show first 20
            print(f"   - {item}")
        if len(missing_from_opml) > 20:
            print(f"   ... and {len(missing_from_opml) - 20} more")
        print()

    if not_in_code:
        print(f"⚠️  IN OPML BUT NOT IN CODE ({len(not_in_code)} items):")
        for item in sorted(not_in_code)[:20]:  # Show first 20
            print(f"   - {item}")
        if len(not_in_code) > 20:
            print(f"   ... and {len(not_in_code) - 20} more")
        print()

    if not missing_from_opml and not not_in_code and not empty_modules:
        print("✅ All API items are properly documented!")
        print()

    # Summary
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"  Empty modules: {len(empty_modules)}")
    print(f"  Missing from OPML: {len(missing_from_opml)}")
    print(f"  In OPML but not in code: {len(not_in_code)}")
    print()

    # Exit code
    if missing_from_opml or empty_modules:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == '__main__':
    main()

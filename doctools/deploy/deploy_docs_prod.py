#!/usr/bin/env python3
"""
Deploy documentation from stage to production.

This script:
1. Fetches the stage branch
2. Completely replaces main branch content with stage
3. Creates a commit checkpoint for rollback
4. Pushes to main branch
"""

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from datetime import datetime


def deploy_to_prod():
    """
    Deploy stage branch to main branch (production).

    This completely replaces main with stage content, creating a commit checkpoint.
    """
    print(f"\n🚀 Deploying documentation from stage to production...")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Clone main branch
        print(f"\n📥 Cloning main branch...")
        main_repo_dir = temp_path / 'pixeltable-docs-www-main'
        result = subprocess.run(
            ['git', 'clone', '-b', 'main', 'https://github.com/pixeltable/pixeltable-docs-www.git', str(main_repo_dir)],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            print(f"❌ Failed to clone main branch: {result.stderr}")
            sys.exit(1)

        print(f"   ✓ Cloned main branch")

        # Clone stage branch
        print(f"\n📥 Cloning stage branch...")
        stage_repo_dir = temp_path / 'pixeltable-docs-www-stage'
        result = subprocess.run(
            ['git', 'clone', '-b', 'stage', 'https://github.com/pixeltable/pixeltable-docs-www.git', str(stage_repo_dir)],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            print(f"❌ Failed to clone stage branch: {result.stderr}")
            sys.exit(1)

        print(f"   ✓ Cloned stage branch")

        # Delete all files in main (except .git)
        print(f"\n🗑️  Clearing main branch content...")
        for item in main_repo_dir.iterdir():
            if item.name == '.git':
                continue
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()

        print(f"   ✓ Cleared main branch")

        # Copy all files from stage to main (except .git)
        print(f"\n📋 Copying stage content to main...")
        copied_count = 0
        for item in stage_repo_dir.iterdir():
            if item.name == '.git':
                continue
            dest = main_repo_dir / item.name
            if item.is_dir():
                shutil.copytree(item, dest)
            else:
                shutil.copy2(item, dest)
            copied_count += 1

        print(f"   ✓ Copied {copied_count} items")

        # Commit changes
        print(f"\n💾 Creating commit checkpoint...")
        subprocess.run(['git', 'add', '-A'], cwd=str(main_repo_dir), check=True)

        # Check if there are changes
        result = subprocess.run(
            ['git', 'diff', '--staged', '--quiet'],
            cwd=str(main_repo_dir)
        )

        if result.returncode != 0:  # There are changes
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            commit_message = f"Deploy from stage to production ({timestamp})"

            subprocess.run(
                ['git', 'commit', '-m', commit_message],
                cwd=str(main_repo_dir),
                check=True
            )

            print(f"   ✓ Created commit: {commit_message}")

            # Push to main
            print(f"\n📤 Pushing to main branch...")
            subprocess.run(
                ['git', 'push', 'origin', 'main'],
                cwd=str(main_repo_dir),
                check=True
            )

            print(f"   ✓ Pushed to main")

            # Show recent commits for rollback reference
            print(f"\n📜 Recent commits (for rollback reference):")
            result = subprocess.run(
                ['git', 'log', '--oneline', '-5'],
                cwd=str(main_repo_dir),
                capture_output=True,
                text=True
            )
            for line in result.stdout.strip().split('\n'):
                print(f"   {line}")

        else:
            print(f"   ℹ️  No changes detected (stage and main are identical)")

    print("\n" + "=" * 60)
    print("✅ Production deployment complete!")
    print(f"   View at: https://docs.pixeltable.com/")
    print(f"\n💡 To rollback, use: git revert HEAD")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Deploy documentation from stage to production (main branch)'
    )

    args = parser.parse_args()

    try:
        deploy_to_prod()
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Deployment failed: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Deployment failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

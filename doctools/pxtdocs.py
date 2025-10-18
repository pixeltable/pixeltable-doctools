#!/usr/bin/env python3
"""
pxtdocs - Pixeltable documentation tools CLI

Usage:
    pxtdocs build              Build docs for local preview
    pxtdocs deploy-stage       Deploy versioned docs to staging
    pxtdocs deploy-prod        Deploy docs from staging to production
"""

import sys
import argparse


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog='pxtdocs',
        description='Pixeltable documentation tools'
    )

    subparsers = parser.add_subparsers(dest='command', help='Command to run')

    # build command
    build_parser = subparsers.add_parser('build', help='Build documentation for local preview')

    # deploy-stage command
    stage_parser = subparsers.add_parser('deploy-stage', help='Deploy versioned documentation to staging')
    stage_parser.add_argument('--version', required=True, help='Version to deploy (e.g., 0.4.17)')

    # deploy-prod command
    prod_parser = subparsers.add_parser('deploy-prod', help='Deploy documentation from staging to production')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Route to appropriate module
    if args.command == 'build':
        from doctools.build_mintlify.build_mintlify import main as build_main
        build_main()
    elif args.command == 'deploy-stage':
        from doctools.deploy.deploy_docs_stage import main as stage_main
        # Override sys.argv to pass --version to the subcommand
        sys.argv = ['deploy-docs-stage', '--version', args.version]
        stage_main()
    elif args.command == 'deploy-prod':
        from doctools.deploy.deploy_docs_prod import main as prod_main
        prod_main()


if __name__ == '__main__':
    main()

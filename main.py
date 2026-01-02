#!/usr/bin/env python3
"""
ZenFeed - Main Entry Point

This script initializes the ZenFeed application. It sets up the path to include
the 'src' directory, parses command-line arguments, and either launches the
TUI application or runs the OPML import utility.
"""

import sys
import os
import argparse

# Add the src directory to sys.path to resolve imports
current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.join(current_dir, "src")
sys.path.append(src_path)

from tui.app import ZenFeedApp
from core.opml_import import import_opml

def main():
    """
    Main function to parse arguments and start the application.
    """
    parser = argparse.ArgumentParser(description="ZenFeed - A minimalist RSS reader.")
    parser.add_argument("--import-opml", dest="opml_file", help="Import feeds from an OPML file", metavar="FILE")
    
    args = parser.parse_args()

    if args.opml_file:
        import_opml(args.opml_file)
    else:
        app = ZenFeedApp()
        app.run()

if __name__ == "__main__":
    main()
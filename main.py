#!/usr/bin/env python3
import sys
import os
import shutil

# Add the src directory to sys.path to resolve imports
current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.join(current_dir, "src")
sys.path.append(src_path)

from tui.app import ZenFeedApp
from core.database import DatabaseManager

def apply_theme():
    """Applies the selected theme by copying it to layout.tcss."""
    try:
        db = DatabaseManager()
        theme_name = db.get_setting("theme", "theme_1_brutalist")
        
        # Paths
        theme_src = os.path.join(src_path, "tui", "themes", f"{theme_name}.tcss")
        theme_dest = os.path.join(src_path, "tui", "layout.tcss")
        
        if os.path.exists(theme_src):
            shutil.copy(theme_src, theme_dest)
        else:
            # Fallback if theme file is missing
            print(f"Warning: Theme file {theme_src} not found. Using default.")
            
    except Exception as e:
        print(f"Failed to apply theme: {e}")

def main():
    apply_theme()
    app = ZenFeedApp()
    app.run()

if __name__ == "__main__":
    main()
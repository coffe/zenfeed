import xml.etree.ElementTree as ET
import os
from .database import DatabaseManager

def import_opml(file_path: str):
    """
    Imports RSS feeds from an OPML file into the ZenFeed database.
    """
    if not os.path.exists(file_path):
        print(f"Error: File '{file_path}' not found.")
        return

    print(f"Importing feeds from {file_path}...")
    
    try:
        tree = ET.parse(file_path)
        root = tree.getroot()
        
        db = DatabaseManager()
        count = 0
        
        # Find all 'outline' elements that have an xmlUrl
        # OPML structure can vary, but usually feeds are in <body>
        # Sometimes nested in categories
        
        # Recursive function to handle nested folders (categories)
        def process_node(node, current_category="Uncategorized"):
            nonlocal count
            
            # Check if this node is a feed (has xmlUrl)
            xml_url = node.get('xmlUrl')
            if xml_url:
                title = node.get('text') or node.get('title') or xml_url
                # In OPML, parent outlines are often categories.
                # We use the passed 'current_category'.
                
                db.add_feed(xml_url, title, current_category)
                print(f"  [+] Added: {title}")
                count += 1
            else:
                # It might be a folder/category container
                # If it has text/title but no xmlUrl, treat as a category for its children
                new_category = node.get('text') or node.get('title')
                if new_category:
                    # Iterate over children using this node's title as the new category
                    for child in node:
                        process_node(child, new_category)
                else:
                    # If no title, just recurse without changing the category
                    for child in node:
                        process_node(child, current_category)

        # Start processing from body
        body = root.find('body')
        if body is not None:
            for child in body:
                process_node(child)
        else:
            # Fallback if no body tag (rare but possible in fragments)
            for child in root:
                process_node(child)

        print(f"\nImport complete! Added {count} feeds.")

    except ET.ParseError as e:
        print(f"Error parsing OPML file: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

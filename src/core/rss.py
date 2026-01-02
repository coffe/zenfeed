import feedparser
from bs4 import BeautifulSoup
from time import mktime
from datetime import datetime
from typing import List, Dict, Any, Optional

class RSSFetcher:
    """
    Handles fetching and parsing of RSS/Atom feeds.
    """

    def parse_feed(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Fetches and parses an RSS feed from the given URL.
        
        Returns:
            A dictionary containing 'title' (feed metadata) and 'entries' (list of articles),
            or None if fetching/parsing fails.
        """
        try:
            # feedparser handles network request and parsing
            feed_data = feedparser.parse(url)

            if feed_data.bozo:
                # 'bozo' is set to 1 if there is a malformed XML structure,
                # but often the content is still readable. We just ignore it for now.
                pass
            
            # Check that we actually got some data
            if not feed_data.feed.get('title') and not feed_data.entries:
                return None

            cleaned_entries = []
            for entry in feed_data.entries:
                cleaned_entries.append(self._process_entry(entry))

            return {
                "title": feed_data.feed.get("title", "Unknown Feed"),
                "entries": cleaned_entries
            }

        except Exception as e:
            # In a production app, we should log this properly
            print(f"Error fetching {url}: {e}")
            return None

    def get_feed_title(self, url: str) -> Optional[str]:
        """Fetches only the title of the feed."""
        try:
            feed_data = feedparser.parse(url)
            if feed_data.bozo and not feed_data.feed:
                 return None
            return feed_data.feed.get("title")
        except Exception:
            return None

    def _process_entry(self, entry: Any) -> Dict[str, Any]:
        """Extracts and cleans relevant data from a feed entry."""
        
        # Handle dates
        published_at = datetime.now() # Fallback
        if hasattr(entry, 'published_parsed') and entry.published_parsed:
            published_at = datetime.fromtimestamp(mktime(entry.published_parsed))
        elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
            published_at = datetime.fromtimestamp(mktime(entry.updated_parsed))

        # Find content (summary or full content)
        content_html = ""
        if hasattr(entry, 'content'):
            # Atom feeds often have a list of content objects; we take the first one
            content_html = entry.content[0].value
        elif hasattr(entry, 'summary'):
            content_html = entry.summary
        else:
            content_html = "No content available."

        # Clean the content (HTML -> Text)
        # For the MVP we convert it to plain text.
        # In the future, we could use 'markdownify' to preserve links/bold text.
        clean_content = self._html_to_text(content_html)

        return {
            "title": entry.get("title", "No Title"),
            "url": entry.get("link", ""),
            "content": clean_content,
            "published_at": published_at.strftime("%Y-%m-%d %H:%M:%S")
        }

    def _html_to_text(self, html: str) -> str:
        """Uses BeautifulSoup to strip tags and extract plain text."""
        if not html:
            return ""
        soup = BeautifulSoup(html, "html.parser")
        return soup.get_text(separator="\n\n").strip()
import feedparser
from bs4 import BeautifulSoup
from time import mktime
from datetime import datetime
from typing import List, Dict, Any, Optional

class RSSFetcher:
    def parse_feed(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Hämtar och parsar en RSS-feed.
        Returnerar en dict med 'feed' (metadata) och 'entries' (artiklar).
        """
        try:
            # Feedparser hanterar nätverk och parsing
            feed_data = feedparser.parse(url)

            if feed_data.bozo:
                # 'bozo' sätts till 1 om det är problem med XML-strukturen, 
                # men ofta går det att läsa ändå. Vi loggar bara varningen mentalt.
                pass
            
            # Kontrollera att vi faktiskt fick data
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
            # I en riktig app vill vi logga detta ordentligt
            print(f"Error fetching {url}: {e}")
            return None

    def _process_entry(self, entry: Any) -> Dict[str, Any]:
        """Extraherar och städar relevant data från en post."""
        
        # Hantera datum
        published_at = datetime.now() # Fallback
        if hasattr(entry, 'published_parsed') and entry.published_parsed:
            published_at = datetime.fromtimestamp(mktime(entry.published_parsed))
        elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
            published_at = datetime.fromtimestamp(mktime(entry.updated_parsed))

        # Hitta innehåll (summary eller content)
        content_html = ""
        if hasattr(entry, 'content'):
            # Atom feeds har ofta en lista av content, vi tar den första
            content_html = entry.content[0].value
        elif hasattr(entry, 'summary'):
            content_html = entry.summary
        else:
            content_html = "No content available."

        # Tvätta innehållet (HTML -> Text)
        # För MVP gör vi om det till ren text. 
        # I framtiden kan vi använda 'markdownify' för att behålla länkar/fetstil.
        clean_content = self._html_to_text(content_html)

        return {
            "title": entry.get("title", "No Title"),
            "url": entry.get("link", ""),
            "content": clean_content,
            "published_at": published_at.strftime("%Y-%m-%d %H:%M:%S")
        }

    def _html_to_text(self, html: str) -> str:
        """Använder BeautifulSoup för att strippa tags och få ren text."""
        if not html:
            return ""
        soup = BeautifulSoup(html, "html.parser")
        return soup.get_text(separator="\n\n").strip()

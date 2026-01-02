from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Tree, DataTable, Static, Markdown, Switch, Label, Button, Input, Select, ListView, ListItem
from textual.containers import Container, VerticalScroll, Horizontal
from textual.screen import Screen
from textual.worker import Worker, get_current_worker
from textual.message import Message
from textual import work

import sys
import os
import webbrowser
import trafilatura
import shutil
import subprocess

# Hack to ensure imports work when running from src/tui
sys.path.append(os.path.join(os.path.dirname(__file__), "../.."))

from src.core.database import DatabaseManager
from src.core.rss import RSSFetcher

class SearchInput(Input):
    """An input that removes itself from the focus chain when it loses focus."""
    
    def on_blur(self, event) -> None:
        self.can_focus = False

class AddFeedScreen(Screen):
    """Screen for adding a new RSS feed."""
    
    BINDINGS = [
        ("escape", "app.pop_screen", "Cancel"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="add-feed-container"):
            yield Label("Add New RSS Feed", classes="section-header")
            
            yield Label("Feed URL:")
            yield Input(placeholder="https://example.com/rss.xml", id="feed_url")
            
            yield Label("Title (Optional):")
            yield Input(placeholder="My Tech News", id="feed_title")
            
            yield Label("Category:")
            yield Input(placeholder="Tech", value="Uncategorized", id="feed_category")
            
            with Horizontal(id="dialog-buttons"):
                yield Button("Add Feed", variant="primary", id="add_btn")
                yield Button("Cancel", id="cancel_btn")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel_btn":
            self.app.pop_screen()
        elif event.button.id == "add_btn":
            self._submit_feed()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        # If enter is pressed in the last input, submit
        if event.input.id == "feed_category":
            self._submit_feed()
        else:
            # Move focus to next input
            if event.input.id == "feed_url":
                self.query_one("#feed_title").focus()
            elif event.input.id == "feed_title":
                self.query_one("#feed_category").focus()

    def _submit_feed(self):
        url = self.query_one("#feed_url").value.strip()
        title = self.query_one("#feed_title").value.strip()
        category = self.query_one("#feed_category").value.strip() or "Uncategorized"

        if not url:
            self.notify("URL is required.", severity="error")
            return

        # If title is empty, use the URL or a placeholder initially
        if not title:
            title = url

        try:
            feed_id = self.app.db.add_feed(url, title, category)
            if feed_id != -1:
                self.notify(f"Added feed: {title}")
                self.app.pop_screen()
                self.app.action_refresh_feeds() # Will fetch real title and articles
            else:
                self.notify("Feed already exists or invalid.", severity="warning")
        except Exception as e:
            self.notify(f"Error adding feed: {e}", severity="error")

class SettingsScreen(Screen):
    """Screen for configuring ZenFeed preferences."""
    
    BINDINGS = [
        ("escape", "app.pop_screen", "Back"),
        ("q", "app.pop_screen", "Back"),
    ]

    def __init__(self, db_manager: DatabaseManager):
        super().__init__()
        self.db = db_manager

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="settings-container"):
            # UI Section
            yield Label("## UI:", classes="section-header")
            
            with ListView(id="settings-list"):
                yield ListItem(Label(self._get_theme_label()), id="setting-theme")
                yield ListItem(Label(self._get_width_label()), id="setting-width")
                
            yield Static("\n")
            
            yield Label("## FEATURES:", classes="section-header")
            with ListView(id="features-list"):
                yield ListItem(Label(self._get_ai_label()), id="setting-ai")

            yield Static("\n")
            yield Button("Close", variant="primary", id="close_btn")
        yield Footer()

    def _get_theme_label(self):
        val = self.db.get_setting("theme", "theme_1_brutalist")
        clean_val = val.replace("theme_", "").replace("_", " ").title()
        # Remove number prefix if present
        parts = clean_val.split(" ")
        if parts[0].isdigit():
            clean_val = " ".join(parts[1:])
        return f"Theme ................ {clean_val}"

    def _get_width_label(self):
        val = self.db.get_setting("reader_width", "Medium")
        return f"Reader Width ......... {val}"

    def _get_ai_label(self):
        val = self.db.get_bool_setting("enable_ai_briefing", False)
        status = "ON" if val else "OFF"
        return f"AI Briefing .......... {status}"

    def on_list_view_selected(self, event: ListView.Selected):
        item_id = event.item.id
        
        if item_id == "setting-theme":
            self._cycle_theme()
            event.item.query_one(Label).update(self._get_theme_label())
            
        elif item_id == "setting-width":
            self._cycle_width()
            event.item.query_one(Label).update(self._get_width_label())
            
        elif item_id == "setting-ai":
            self._toggle_ai()
            event.item.query_one(Label).update(self._get_ai_label())

    def _cycle_theme(self):
        themes = ["theme_1_brutalist", "theme_2_bold", "theme_3_dashed", "theme_4_double"]
        current = self.db.get_setting("theme", "theme_1_brutalist")
        try:
            idx = themes.index(current)
            new_theme = themes[(idx + 1) % len(themes)]
        except ValueError:
            new_theme = themes[0]
        
        self.db.set_setting("theme", new_theme)

    def _cycle_width(self):
        opts = ["Narrow", "Medium", "Wide"]
        current = self.db.get_setting("reader_width", "Medium")
        try:
            idx = opts.index(current)
            new_val = opts[(idx + 1) % len(opts)]
        except ValueError:
            new_val = opts[0]
        self.db.set_setting("reader_width", new_val)
        
    def _toggle_ai(self):
        curr = self.db.get_bool_setting("enable_ai_briefing", False)
        new_val = not curr
        self.db.set_setting("enable_ai_briefing", str(new_val))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "close_btn":
            self.app.pop_screen()

class ReaderScreen(Screen):
    """Screen for reading an article in 'Zen Mode'."""
    
    BINDINGS = [
        ("escape", "app.pop_screen", "Back"),
        ("q", "app.pop_screen", "Back"),
        ("o", "open_browser", "Open in Browser"),
        ("s", "toggle_save", "Save/Unsave"),
    ]

    def __init__(self, article: dict, db_manager: DatabaseManager):
        super().__init__()
        self.article = article
        self.db = db_manager

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(id="reader-container"):
            md_content = self._format_markdown(loading=True)
            yield Markdown(md_content, id="reader-content")
        yield Footer()

    def on_mount(self):
        # Apply Width Setting
        width_setting = self.db.get_setting("reader_width", "Medium").lower()
        container = self.query_one("#reader-container")
        container.remove_class("reader-narrow", "reader-medium", "reader-wide")
        
        # Default to medium if invalid
        if width_setting not in ["narrow", "medium", "wide"]:
            width_setting = "medium"
            
        container.add_class(f"reader-{width_setting}")

        if self.article.get('full_content'):
            self._update_view(self.article['full_content'])
        else:
            self.fetch_full_text()

    def _format_markdown(self, content: str = None, loading: bool = False):
        saved_icon = "⭐ " if self.article['is_saved'] else ""
        md = f"# {saved_icon}{self.article['title']}\n"
        md += f"**Source:** {self.article['feed_title']} | **Date:** {self.article['published_at']}\n\n"
        md += "---\n\n"
        
        if content:
            md += content
        elif loading:
            md += "⏳ *Fetching full article content...*\n\n"
            md += f"> {self.article['content'] or ''}"
        else:
            md += self.article['content'] or "*No content available.*"
        return md

    def _update_view(self, content: str):
        md_widget = self.query_one(Markdown)
        md_widget.update(self._format_markdown(content=content))

    def action_toggle_save(self):
        new_status = self.db.toggle_saved(self.article['id'])
        self.article['is_saved'] = new_status
        # Refresh view to show/hide star
        if self.article.get('full_content'):
            self._update_view(self.article['full_content'])
        else:
             # Just update header if content is still loading/missing
             self._update_view(None)
             
        status_msg = "Saved for later" if new_status else "Removed from saved"
        self.notify(status_msg)
        # Notify parent app to refresh list when we return
        self.app.post_message(self.app.SavedStatusChanged())

    @work(exclusive=True, thread=True)
    def fetch_full_text(self):
        url = self.article['url']
        downloaded = trafilatura.fetch_url(url)
        
        full_text = None
        if downloaded:
            full_text = trafilatura.extract(
                downloaded, 
                include_comments=False, 
                include_tables=True,
                with_metadata=False,
                output_format="markdown"
            )
        
        if full_text:
            self.db.update_article_content(self.article['id'], full_text)
            self.app.call_from_thread(self._update_view, full_text)
        else:
            self.app.call_from_thread(self.notify, "Could not extract full text.", severity="warning")
            self.app.call_from_thread(self._update_view, None)

    def action_open_browser(self):
        if self.article['url']:
            webbrowser.open(self.article['url'])
            self.notify("Opening in browser...")

class BriefingScreen(Screen):
    """Screen for displaying AI Daily Briefing."""
    
    BINDINGS = [
        ("escape", "app.pop_screen", "Back"),
        ("q", "app.pop_screen", "Back"),
    ]

    def __init__(self, content: str):
        super().__init__()
        self.content = content

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(id="reader-container"):
            yield Markdown(self.content, id="reader-content")
        yield Footer()

class ConfirmationScreen(Screen):
    """A generic confirmation dialog."""
    
    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, message: str, on_confirm: callable):
        super().__init__()
        self.message = message
        self.on_confirm = on_confirm

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="add-feed-container"): # Reuse styling
            yield Label(self.message, classes="section-header")
            with Horizontal(id="dialog-buttons"):
                yield Button("Yes", variant="error", id="yes_btn")
                yield Button("No", variant="primary", id="no_btn")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "yes_btn":
            self.on_confirm()
            self.app.pop_screen()
        else:
            self.app.pop_screen()
            
    def action_cancel(self):
        self.app.pop_screen()

class ZenFeedApp(App):
    """ZenFeed - A minimalist RSS reader."""

    CSS_PATH = "layout.tcss"
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("d", "toggle_dark", "Toggle dark mode"),
        ("r", "refresh_feeds", "Refresh Feeds"),
        ("a", "add_feed", "Add Feed"),
        ("x", "delete_feed", "Unsubscribe"),
        ("s", "toggle_save_list", "Save/Unsave"),
        ("m", "mark_read", "Mark All Read"),
        ("p", "open_settings", "Settings"),
        ("b", "daily_briefing", "AI Briefing"),
        ("/", "focus_search", "Search"),
    ]

    # Custom message to trigger updates from other screens
    class SavedStatusChanged(Message):
        pass

    def __init__(self):
        super().__init__()
        self.db = DatabaseManager()
        self.fetcher = RSSFetcher()
        self.current_feed_id = None 
        self.current_category = None
        self.current_filter_mode = "all" # 'all', 'saved', 'feed', 'category'
        self.current_search_query = None

    def _load_theme_css(self) -> str:
        """Load CSS content based on selected theme."""
        theme_name = self.db.get_setting("theme", "theme_1_brutalist")
        theme_path = os.path.join(os.path.dirname(__file__), "themes", f"{theme_name}.tcss")
        
        css_content = ""
        try:
            if os.path.exists(theme_path):
                with open(theme_path, "r") as f:
                    css_content = f.read()
            else:
                # Fallback to layout.tcss
                fallback_path = os.path.join(os.path.dirname(__file__), "layout.tcss")
                if os.path.exists(fallback_path):
                    with open(fallback_path, "r") as f:
                        css_content = f.read()
        except Exception as e:
            print(f"Error loading theme: {e}")
            
        return css_content

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Container(id="main-layout"):
            # Sidebar with Tree
            with Container(id="sidebar"):
                tree = Tree("Feeds", id="feed_tree")
                tree.root.expand()
                yield tree

            # A: Vertical Separator Wrapper
            with Container(id="vertical-sep-wrapper"):
                yield Static("", classes="vertical-separator")

            table = DataTable(cursor_type="row")
            table.add_columns("Date", "Title", "Source")
            
            with Container(id="article-list"):
                # B: Search Input Wrapper
                with Container(id="search-wrapper"):
                    yield SearchInput(placeholder="Search articles... (Press '/' to focus)", id="search_input")
                yield table
        yield Footer()

    def on_mount(self) -> None:
        # Inject CSS
        css = self._load_theme_css()
        if css:
            self.stylesheet.add_source(css)

        self._init_data()
        self.refresh_ui_tree()
        self.action_refresh_feeds()
        # Disable search focus by default so Tab skips it
        search_input = self.query_one(SearchInput)
        search_input.can_focus = False

    def action_focus_search(self):
        inp = self.query_one(SearchInput)
        inp.can_focus = True
        inp.focus()
        
    def on_input_changed(self, event: Input.Changed):
        if event.input.id == "search_input":
            self.current_search_query = event.value
            self.refresh_article_list_wrapper()

    def on_input_submitted(self, event: Input.Submitted):
        """When Enter is pressed in search, move focus to table."""
        if event.input.id == "search_input":
            self.query_one(DataTable).focus()

    def _init_data(self):
        feeds = self.db.get_feeds()
        if not feeds:
            defaults = [
                ("https://www.svt.se/nyheter/rss.xml", "SVT Nyheter", "News"),
                ("https://feeds.feedburner.com/TheHackersNews", "The Hacker News", "Tech"),
                ("https://9to5linux.com/feed", "9to5Linux", "Linux"),
            ]
            for url, title, cat in defaults:
                self.db.add_feed(url, title, cat)

    def action_open_settings(self):
        self.push_screen(SettingsScreen(self.db))

    def action_add_feed(self):
        self.push_screen(AddFeedScreen())

    def action_delete_feed(self):
        tree = self.query_one(Tree)
        node = tree.cursor_node
        
        if not node or not node.data:
            self.notify("Select a feed to unsubscribe.", severity="warning")
            return

        if node.data.get("type") == "feed":
            feed_id = node.data["feed_id"]
            feed_title = str(node.label).replace("📰 ", "")
            
            def do_delete():
                if self.db.delete_feed(feed_id):
                    self.notify(f"Unsubscribed from '{feed_title}'")
                    # Clear selection if we deleted the current feed
                    if self.current_feed_id == feed_id:
                        self.current_feed_id = None
                        self.refresh_article_list(filter_mode="all")
                    self.refresh_ui_tree()
                else:
                    self.notify("Failed to delete feed.", severity="error")

            self.push_screen(ConfirmationScreen(f"Unsubscribe from '{feed_title}'?", do_delete))
        else:
             self.notify("You can only unsubscribe from specific feeds.", severity="warning")

    def action_daily_briefing(self):
        is_enabled = self.db.get_bool_setting("enable_ai_briefing", False)
        
        if not is_enabled:
            self.notify("AI Briefing is disabled in Settings.", severity="warning")
            return

        self.notify("Generating Daily Briefing... This may take a moment.", title="AI Assistant")
        self.generate_briefing_worker()

    @work(exclusive=True, thread=True)
    def generate_briefing_worker(self):
        # Fetch articles
        articles = self.db.get_articles(limit=15)
        
        if not articles:
            self.app.call_from_thread(self.notify, "No articles found.", severity="warning")
            return

        # Prepare context data
        context_data = ""
        for art in articles:
            # Limit content length per article to avoid token explosion
            content_snippet = (art['content'] or "")[:500].replace("\n", " ")
            context_data += f"Title: {art['title']}\nSource: {art['feed_title']}\nContent: {content_snippet}\n---\n"

        system_prompt = (
            "You are a helpful news assistant. "
            "Summarize the provided news articles into a structured 'Daily Briefing'. "
            "Group them by topic if possible. Use Markdown formatting with bold headers and bullet points. "
            "Start with a 'Key Takeaways' section."
        )

        try:
            # We pipe context_data into stdin and provide the system prompt as argument
            process = subprocess.Popen(
                ["gemini", system_prompt],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            stdout, stderr = process.communicate(input=context_data)
            
            if process.returncode == 0 and stdout:
                self.app.call_from_thread(self.push_screen, BriefingScreen(stdout))
            else:
                error_msg = stderr if stderr else "Unknown error from Gemini CLI"
                self.app.call_from_thread(self.notify, f"Error: {error_msg}", severity="error")
                
        except Exception as e:
            self.app.call_from_thread(self.notify, f"Failed to run Gemini: {e}", severity="error")

    @work(exclusive=True, thread=True)
    def action_refresh_feeds(self) -> None:
        worker = get_current_worker()
        self.title = "ZenFeed - Refreshing..."
        
        feeds = self.db.get_feeds()
        for feed in feeds:
            if worker.is_cancelled: return
            data = self.fetcher.parse_feed(feed['url'])
            if data and data['entries']:
                for entry in data['entries']:
                    self.db.add_article(
                        feed['id'], entry['title'], entry['url'], 
                        entry['content'], entry['published_at']
                    )
        
        # Refresh current view
        self.call_from_thread(self.refresh_article_list_wrapper)
        self.call_from_thread(self.refresh_ui_tree)
        self.call_from_thread(self.update_title, "ZenFeed")

    def refresh_article_list_wrapper(self):
        """Wrapper to call refresh_article_list with current state from thread."""
        self.refresh_article_list(
            feed_id=self.current_feed_id, 
            category=self.current_category,
            filter_mode=self.current_filter_mode,
            search_query=self.current_search_query
        )

    def update_title(self, text: str):
        self.title = text

    def refresh_ui_tree(self):
        tree = self.query_one("#feed_tree")
        tree.clear()
        tree.root.expand()
        
        # Add "Saved" Node at the top
        tree.root.add_leaf("⭐ Saved for Later", data={"type": "saved"})
        
        feeds = self.db.get_feeds()
        unread_counts = self.db.get_unread_counts()
        categories = {}

        for feed in feeds:
            cat = feed['category']
            if cat not in categories: categories[cat] = []
            categories[cat].append(feed)

        for cat, feed_list in categories.items():
            # Calculate total unread for category
            cat_unread = 0
            for feed in feed_list:
                cat_unread += unread_counts.get(feed['id'], 0)
            
            cat_count_str = f" ({cat_unread})" if cat_unread > 0 else ""
            cat_node = tree.root.add(f"📁 {cat}{cat_count_str}", expand=True, data={"type": "category", "name": cat})
            
            for feed in feed_list:
                count = unread_counts.get(feed['id'], 0)
                count_str = f" ({count})" if count > 0 else ""
                label = f"📰 {feed['title']}{count_str}"
                cat_node.add_leaf(label, data={"type": "feed", "feed_id": feed['id']})

    def refresh_article_list(self, feed_id: int = None, category: str = None, filter_mode: str = "all", search_query: str = None):
        """Reloads the DataTable based on filters."""
        table = self.query_one(DataTable)
        table.clear()
        
        self.current_feed_id = feed_id
        self.current_category = category
        self.current_filter_mode = filter_mode

        # Common args
        kwargs = {"limit": 100, "search_query": search_query}

        if filter_mode == "saved":
            articles = self.db.get_articles(saved_only=True, **kwargs)
        elif filter_mode == "feed" and feed_id:
            articles = self.db.get_articles(feed_id=feed_id, **kwargs)
        elif filter_mode == "category" and category:
            articles = self.db.get_articles(category=category, **kwargs)
        else: # All
            articles = self.db.get_articles(**kwargs)
        
        for art in articles:
            date_str = str(art['published_at'])[:10]
            
            # Formatting
            title = art['title']
            if art['is_saved']: title = f"⭐ {title}"
            elif not art['is_read']: title = f"● {title}" # Unread indicator
            
            table.add_row(
                date_str, 
                title, 
                art['feed_title'], 
                key=str(art['id'])
            )

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        node_data = event.node.data
        if not node_data:
            self.refresh_article_list(filter_mode="all")
            return

        if node_data.get("type") == "saved":
            self.refresh_article_list(filter_mode="saved")
        elif node_data.get("type") == "category":
            self.refresh_article_list(category=node_data["name"], filter_mode="category")
        elif node_data.get("type") == "feed":
            self.refresh_article_list(feed_id=node_data["feed_id"], filter_mode="feed")

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        article_id = int(event.row_key.value)
        article = self.db.get_article_by_id(article_id)
        if article:
            self.push_screen(ReaderScreen(article, self.db))
            self.db.mark_as_read(article_id)
            self.refresh_ui_tree() # Update counts
            self.refresh_article_list_wrapper() # Remove unread dot

    def action_toggle_save_list(self):
        """Toggle save for selected row in list."""
        table = self.query_one(DataTable)
        try:
            row_key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key
            article_id = int(row_key.value)
            
            new_status = self.db.toggle_saved(article_id)
            status_msg = "Saved" if new_status else "Unsaved"
            self.notify(status_msg)
            
            # Refresh list to show/hide star
            self.refresh_article_list_wrapper()
            
        except Exception:
            self.notify("No article selected", severity="warning")

    def action_mark_read(self):
        """Mark all visible articles as read."""
        if self.current_filter_mode == "feed" and self.current_feed_id:
            self.db.mark_feed_as_read(self.current_feed_id)
            self.notify("Feed marked as read")
        elif self.current_filter_mode == "category" and self.current_category:
            self.db.mark_category_as_read(self.current_category)
            self.notify(f"Category '{self.current_category}' marked as read")
        elif self.current_filter_mode == "all":
            self.db.mark_all_as_read()
            self.notify("All articles marked as read")
        
        self.refresh_ui_tree()
        self.refresh_article_list_wrapper()

    def on_saved_status_changed(self, message: SavedStatusChanged):
        """Handle save toggle from ReaderScreen."""
        self.refresh_article_list_wrapper()
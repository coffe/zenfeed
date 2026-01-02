import sqlite3
import os
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Dict, Any

class DatabaseManager:
    """
    Manages the SQLite database for ZenFeed, handling storage of feeds, articles, and settings.
    """
    def __init__(self, db_path: str = None):
        """
        Initialize the DatabaseManager.
        
        Args:
            db_path: Optional custom path for the database file. 
                     If None, defaults to ~/.config/zenfeed/zenfeed.db
        """
        if db_path is None:
            # Determine config directory
            config_dir = Path.home() / ".config" / "zenfeed"
            config_dir.mkdir(parents=True, exist_ok=True)
            self.db_path = str(config_dir / "zenfeed.db")
        else:
            self.db_path = db_path
            
        self._create_tables()
        self._migrate_schema()
        self._create_indexes()

    def _get_connection(self):
        """Creates and returns a new database connection with Row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _create_tables(self):
        """Initializes the database schema (tables) if they do not exist."""
        schema = """
        CREATE TABLE IF NOT EXISTS feeds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT UNIQUE NOT NULL,
            title TEXT,
            category TEXT DEFAULT 'Uncategorized',
            icon_url TEXT,
            last_fetched TIMESTAMP,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            feed_id INTEGER,
            title TEXT NOT NULL,
            url TEXT UNIQUE NOT NULL,
            content TEXT,
            full_content TEXT,
            published_at TIMESTAMP,
            is_read BOOLEAN DEFAULT 0,
            is_saved BOOLEAN DEFAULT 0,
            fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(feed_id) REFERENCES feeds(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        """
        with self._get_connection() as conn:
            conn.executescript(schema)

    def _create_indexes(self):
        """Creates indexes after tables and columns are in place."""
        indexes = """
        CREATE INDEX IF NOT EXISTS idx_articles_feed_id ON articles(feed_id);
        CREATE INDEX IF NOT EXISTS idx_articles_is_read ON articles(is_read);
        CREATE INDEX IF NOT EXISTS idx_articles_is_saved ON articles(is_saved);
        """
        with self._get_connection() as conn:
            conn.executescript(indexes)

    def _migrate_schema(self):
        """Performs schema migrations to add new columns if they are missing."""
        with self._get_connection() as conn:
            # Migration for articles (is_saved)
            try:
                conn.execute("SELECT is_saved FROM articles LIMIT 1")
            except sqlite3.OperationalError:
                conn.execute("ALTER TABLE articles ADD COLUMN is_saved BOOLEAN DEFAULT 0")

            # Migration for feeds (icon_url, last_fetched)
            try:
                conn.execute("SELECT icon_url FROM feeds LIMIT 1")
            except sqlite3.OperationalError:
                conn.execute("ALTER TABLE feeds ADD COLUMN icon_url TEXT")
            
            try:
                conn.execute("SELECT last_fetched FROM feeds LIMIT 1")
            except sqlite3.OperationalError:
                conn.execute("ALTER TABLE feeds ADD COLUMN last_fetched TIMESTAMP")

    # --- Settings Management ---

    def set_setting(self, key: str, value: str):
        """Save a setting. Value is always stored as a string."""
        with self._get_connection() as conn:
            conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))

    def get_setting(self, key: str, default: str = None) -> Optional[str]:
        """Retrieve a setting as a string."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT value FROM settings WHERE key = ?", (key,))
            row = cursor.fetchone()
            return row['value'] if row else default

    def get_bool_setting(self, key: str, default: bool = False) -> bool:
        """Helper method to retrieve boolean settings."""
        val = self.get_setting(key)
        if val is None:
            return default
        return val.lower() in ('true', '1', 'yes', 'on')

    def add_feed(self, url: str, title: str, category: str = "Uncategorized", icon_url: str = None) -> int:
        """
        Add a new feed to the database.
        Returns the ID of the new (or existing) feed.
        """
        with self._get_connection() as conn:
            try:
                cursor = conn.execute(
                    "INSERT INTO feeds (url, title, category, icon_url) VALUES (?, ?, ?, ?)",
                    (url, title, category, icon_url)
                )
                return cursor.lastrowid
            except sqlite3.IntegrityError:
                cursor = conn.execute("SELECT id FROM feeds WHERE url = ?", (url,))
                row = cursor.fetchone()
                return row['id'] if row else -1

    def delete_feed(self, feed_id: int) -> bool:
        """Removes a feed and its articles."""
        with self._get_connection() as conn:
            cursor = conn.execute("DELETE FROM feeds WHERE id = ?", (feed_id,))
            return cursor.rowcount > 0

    def get_feeds(self) -> List[Dict[str, Any]]:
        """Retrieve all feeds, ordered by category and title."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM feeds ORDER BY category, title")
            return [dict(row) for row in cursor.fetchall()]

    def get_categories(self) -> List[str]:
        """Retrieves a list of unique categories."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT DISTINCT category FROM feeds ORDER BY category")
            return [row['category'] for row in cursor.fetchall() if row['category']]

    def add_article(self, feed_id: int, title: str, url: str, content: str, published_at: str) -> bool:
        """
        Add an article to the database.
        Returns True if added, False if it already exists (duplicate URL).
        """
        with self._get_connection() as conn:
            try:
                conn.execute(
                    """
                    INSERT INTO articles (feed_id, title, url, content, published_at) 
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (feed_id, title, url, content, published_at)
                )
                return True
            except sqlite3.IntegrityError:
                return False

    def get_articles(self, feed_id: Optional[int] = None, category: Optional[str] = None, unread_only: bool = False, saved_only: bool = False, search_query: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Retrieve articles based on various filters.
        
        Args:
            feed_id: Filter by specific feed ID.
            category: Filter by specific category name.
            unread_only: If True, return only unread articles.
            saved_only: If True, return only saved articles.
            search_query: Search term for title or content.
            limit: Maximum number of articles to return.
        """
        query = """
            SELECT a.*, f.title as feed_title 
            FROM articles a 
            JOIN feeds f ON a.feed_id = f.id
        """
        params = []
        conditions = []

        if feed_id:
            conditions.append("a.feed_id = ?")
            params.append(feed_id)
        
        if category:
            conditions.append("f.category = ?")
            params.append(category)
        
        if unread_only:
            conditions.append("a.is_read = 0")
            
        if saved_only:
            conditions.append("a.is_saved = 1")

        if search_query:
            conditions.append("(a.title LIKE ? OR a.content LIKE ?)")
            search_pattern = f"%{search_query}%"
            params.extend([search_pattern, search_pattern])

        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        query += " ORDER BY a.published_at DESC LIMIT ?"
        params.append(limit)

        with self._get_connection() as conn:
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def get_article_by_id(self, article_id: int) -> Optional[Dict[str, Any]]:
        """Retrieve a single article by its ID."""
        query = """
            SELECT a.*, f.title as feed_title 
            FROM articles a 
            JOIN feeds f ON a.feed_id = f.id
            WHERE a.id = ?
        """
        with self._get_connection() as conn:
            cursor = conn.execute(query, (article_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def mark_as_read(self, article_id: int, is_read: bool = True):
        """Update the read status of an article."""
        with self._get_connection() as conn:
            conn.execute("UPDATE articles SET is_read = ? WHERE id = ?", (1 if is_read else 0, article_id))

    def update_article_content(self, article_id: int, full_text: str):
        """Update the full text content of an article."""
        with self._get_connection() as conn:
            conn.execute("UPDATE articles SET full_content = ? WHERE id = ?", (full_text, article_id))

    # --- New Functions for Dashboard & Features ---

    def toggle_saved(self, article_id: int) -> bool:
        """Toggles the 'saved' status. Returns the new status (True=Saved)."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT is_saved FROM articles WHERE id = ?", (article_id,))
            row = cursor.fetchone()
            if row:
                new_status = not row['is_saved']
                conn.execute("UPDATE articles SET is_saved = ? WHERE id = ?", (1 if new_status else 0, article_id))
                return new_status
            return False

    def mark_feed_as_read(self, feed_id: int):
        """Mark all articles in a feed as read."""
        with self._get_connection() as conn:
            conn.execute("UPDATE articles SET is_read = 1 WHERE feed_id = ?", (feed_id,))

    def mark_category_as_read(self, category: str):
        """Mark all articles in a specific category as read."""
        with self._get_connection() as conn:
            # Subquery to find all articles belonging to feeds in this category
            conn.execute("""
                UPDATE articles 
                SET is_read = 1 
                WHERE feed_id IN (SELECT id FROM feeds WHERE category = ?)
            """, (category,))

    def mark_all_as_read(self):
        """Mark ALL articles in the database as read."""
        with self._get_connection() as conn:
            conn.execute("UPDATE articles SET is_read = 1")

    def get_unread_counts(self) -> Dict[int, int]:
        """Returns a dict {feed_id: count} with the number of unread articles per feed."""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT feed_id, COUNT(*) as count 
                FROM articles 
                WHERE is_read = 0 
                GROUP BY feed_id
            """)
            return {row['feed_id']: row['count'] for row in cursor.fetchall()}
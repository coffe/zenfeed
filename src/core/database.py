import sqlite3
from datetime import datetime
from typing import List, Optional, Dict, Any

class DatabaseManager:
    def __init__(self, db_path: str = "zenfeed.db"):
        self.db_path = db_path
        self._create_tables()
        self._migrate_schema()
        self._create_indexes()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _create_tables(self):
        """Initierar databasschemat (tabeller) om det inte finns."""
        schema = """
        CREATE TABLE IF NOT EXISTS feeds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT UNIQUE NOT NULL,
            title TEXT,
            category TEXT DEFAULT 'Uncategorized',
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
        """Skapar index efter att tabeller och kolumner är på plats."""
        indexes = """
        CREATE INDEX IF NOT EXISTS idx_articles_feed_id ON articles(feed_id);
        CREATE INDEX IF NOT EXISTS idx_articles_is_read ON articles(is_read);
        CREATE INDEX IF NOT EXISTS idx_articles_is_saved ON articles(is_saved);
        """
        with self._get_connection() as conn:
            conn.executescript(indexes)

    def _migrate_schema(self):
        """Enkel migrering för att lägga till is_saved om den saknas."""
        with self._get_connection() as conn:
            try:
                conn.execute("SELECT is_saved FROM articles LIMIT 1")
            except sqlite3.OperationalError:
                # Kolumnen saknas, lägg till den
                conn.execute("ALTER TABLE articles ADD COLUMN is_saved BOOLEAN DEFAULT 0")

    # --- Settings Management ---

    def set_setting(self, key: str, value: str):
        """Spara en inställning. Value sparas alltid som sträng."""
        with self._get_connection() as conn:
            conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))

    def get_setting(self, key: str, default: str = None) -> Optional[str]:
        """Hämta en inställning som sträng."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT value FROM settings WHERE key = ?", (key,))
            row = cursor.fetchone()
            return row['value'] if row else default

    def get_bool_setting(self, key: str, default: bool = False) -> bool:
        """Hjälpmetod för att hämta booleska inställningar."""
        val = self.get_setting(key)
        if val is None:
            return default
        return val.lower() in ('true', '1', 'yes', 'on')

    def add_feed(self, url: str, title: str, category: str = "Uncategorized") -> int:
        with self._get_connection() as conn:
            try:
                cursor = conn.execute(
                    "INSERT INTO feeds (url, title, category) VALUES (?, ?, ?)",
                    (url, title, category)
                )
                return cursor.lastrowid
            except sqlite3.IntegrityError:
                cursor = conn.execute("SELECT id FROM feeds WHERE url = ?", (url,))
                row = cursor.fetchone()
                return row['id'] if row else -1

    def get_feeds(self) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM feeds ORDER BY category, title")
            return [dict(row) for row in cursor.fetchall()]

    def add_article(self, feed_id: int, title: str, url: str, content: str, published_at: str):
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
        with self._get_connection() as conn:
            conn.execute("UPDATE articles SET is_read = ? WHERE id = ?", (1 if is_read else 0, article_id))

    def update_article_content(self, article_id: int, full_text: str):
        with self._get_connection() as conn:
            conn.execute("UPDATE articles SET full_content = ? WHERE id = ?", (full_text, article_id))

    # --- Nya funktioner för Dashboard & Features ---

    def toggle_saved(self, article_id: int) -> bool:
        """Växlar sparat-status. Returnerar nya statusen."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT is_saved FROM articles WHERE id = ?", (article_id,))
            row = cursor.fetchone()
            if row:
                new_status = not row['is_saved']
                conn.execute("UPDATE articles SET is_saved = ? WHERE id = ?", (1 if new_status else 0, article_id))
                return new_status
            return False

    def mark_feed_as_read(self, feed_id: int):
        """Markera allt i en feed som läst."""
        with self._get_connection() as conn:
            conn.execute("UPDATE articles SET is_read = 1 WHERE feed_id = ?", (feed_id,))

    def mark_category_as_read(self, category: str):
        """Markera allt i en kategori som läst."""
        with self._get_connection() as conn:
            # Subquery för att hitta alla articles som tillhör feeds i denna kategori
            conn.execute("""
                UPDATE articles 
                SET is_read = 1 
                WHERE feed_id IN (SELECT id FROM feeds WHERE category = ?)
            """, (category,))

    def mark_all_as_read(self):
        """Markera ALLT som läst."""
        with self._get_connection() as conn:
            conn.execute("UPDATE articles SET is_read = 1")

    def get_unread_counts(self) -> Dict[int, int]:
        """Returnerar en dict {feed_id: count} med antal olästa artiklar."""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT feed_id, COUNT(*) as count 
                FROM articles 
                WHERE is_read = 0 
                GROUP BY feed_id
            """)
            return {row['feed_id']: row['count'] for row in cursor.fetchall()}

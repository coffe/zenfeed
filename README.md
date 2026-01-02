# ZenFeed (Alpha)

**ZenFeed** is a minimalist RSS reader for the terminal (TUI), built with Python and [Textual](https://textual.textualize.io/). It is designed to provide a calm and focused reading experience directly in your terminal.

> **⚠️ Alpha Status:** This project is under development. Features may change and bugs may occur.

## Features

*   **Distraction-Free Reading:** Built-in reader mode that strips away noise and displays articles in plain text/markdown.
*   **Local Storage:** All feeds and articles are stored locally in a SQLite database.
*   **Manage Feeds:** Add new RSS feeds directly within the app.
*   **OPML Import:** Import entire collections of feeds from other readers.
*   **Customizable Themes:** Several different TUI themes (Brutalist, Bold, Dashed, Double).
*   **Categorization:** Organize your feeds into logical categories.
*   **Save for Later:** Bookmark articles you want to return to.
*   **Keyboard Focused:** Fast navigation optimized for the terminal.

## Installation

1.  Clone the repo:
    ```bash
    git clone git@github.com:coffe/zenfeed.git
    cd zenfeed
    ```

2.  Create a virtual environment and install dependencies:
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    ```

3.  Start the program:
    ```bash
    python main.py
    ```

## Usage

### Keyboard Shortcuts
*   `a` - Add new RSS feed
*   `r` - Refresh all feeds
*   `s` - Save/Unsave article (in list or reader mode)
*   `m` - Mark all (or category/feed) as read
*   `p` - Open Settings (Themes, AI Briefing, etc.)
*   `b` - Generate "Daily Briefing" (requires configuration)
*   `/` - Search articles
*   `d` - Toggle Dark/Light mode (if supported by theme)
*   `q` - Quit / Back

### Import OPML
You can easily import an OPML file from another RSS reader:

```bash
python main.py --import-opml my_feeds.opml
```

## License

MIT
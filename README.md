# ZenFeed (Alpha)

**ZenFeed** är en minimalistisk RSS-läsare för terminalen (TUI), byggd med Python och [Textual](https://textual.textualize.io/). Den är designad för att ge en lugn och fokuserad läsupplevelse direkt i din terminal.

> **⚠️ Alpha-status:** Detta projekt är under utveckling. Funktioner kan ändras och buggar kan förekomma.

## Funktioner

*   **Distraktionsfri läsning:** Inbyggt läsläge som skalar bort brus och visar artiklar i ren text/markdown.
*   **Lokal lagring:** Alla flöden och artiklar sparas lokalt i en SQLite-databas.
*   **Anpassningsbara teman:** Flera olika TUI-teman (Brutalist, Bold, Dashed, Double).
*   **Kategorisering:** Organisera dina flöden i logiska kategorier.
*   **Spara för senare:** Markera artiklar som du vill återkomma till.
*   **Tangentbordsfokuserad:** Snabb navigation optimerad för terminalen.

## Installation

1.  Klona repot:
    ```bash
    git clone git@github.com:coffe/zenfeed.git
    cd zenfeed
    ```

2.  Skapa en virtuell miljö och installera beroenden:
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    ```

3.  Starta programmet:
    ```bash
    python main.py
    ```

## Licens

MIT

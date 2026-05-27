"""
MCP Server – Song Search & Analysis Tools.

This module creates a FastMCP server that exposes tools for searching and
analysing Ibero-American popular songs.  The tools include:

* A local simulated catalogue (``search_songs``, ``get_song_by_id``, etc.)
* Live search against the **BDPI** (Biblioteca Digital del Patrimonio
  Iberoamericano) at iberoamericadigital.net
* Live search against the **Cantigas de Santa Maria** database at
  cantigas.fcsh.unl.pt

All search tools apply a *fuzzy* ranking step so that near-matches on
titles, composers, or keywords float to the top even when spellings differ.
"""

import difflib
import re
from urllib.parse import urlencode

import httpx
from bs4 import BeautifulSoup, Tag
from fastmcp import FastMCP

from config import MCP_SERVER_NAME

# ---------------------------------------------------------------------------
# Simulated song catalogue
# ---------------------------------------------------------------------------

SONGS_DB: list[dict] = [
    {
        "id": 1,
        "title": "La Bamba",
        "artist": "Ritchie Valens",
        "genre": "Son jarocho / Rock and Roll",
        "country": "México",
        "year": 1958,
        "key": "C major",
        "tempo_bpm": 140,
        "description": (
            "Traditional Mexican folk song from Veracruz popularised "
            "worldwide by Ritchie Valens."
        ),
    },
    {
        "id": 2,
        "title": "Clandestino",
        "artist": "Manu Chao",
        "genre": "Latin / Alternative",
        "country": "Francia / España",
        "year": 1998,
        "key": "A minor",
        "tempo_bpm": 96,
        "description": (
            "Iconic song about immigration and identity, blending "
            "Latin rhythms with French chanson."
        ),
    },
    {
        "id": 3,
        "title": "Gracias a la Vida",
        "artist": "Violeta Parra",
        "genre": "Nueva Canción",
        "country": "Chile",
        "year": 1966,
        "key": "E minor",
        "tempo_bpm": 108,
        "description": (
            "One of the most important songs in Latin-American folk "
            "music, expressing gratitude for life."
        ),
    },
    {
        "id": 4,
        "title": "Guantanamera",
        "artist": "Joseíto Fernández",
        "genre": "Son cubano",
        "country": "Cuba",
        "year": 1929,
        "key": "D major",
        "tempo_bpm": 120,
        "description": (
            "Patriotic Cuban song adapted with verses by José Martí, "
            "known worldwide as a symbol of Cuban culture."
        ),
    },
    {
        "id": 5,
        "title": "El Cóndor Pasa",
        "artist": "Daniel Alomía Robles",
        "genre": "Andean folk / Zarzuela",
        "country": "Perú",
        "year": 1913,
        "key": "E minor",
        "tempo_bpm": 100,
        "description": (
            "Peruvian orchestral piece based on Andean folk melodies, "
            "later popularised by Simon & Garfunkel."
        ),
    },
    {
        "id": 6,
        "title": "Bamboleo",
        "artist": "Gipsy Kings",
        "genre": "Rumba flamenca",
        "country": "Francia / España",
        "year": 1987,
        "key": "A minor",
        "tempo_bpm": 130,
        "description": (
            "Energetic rumba flamenca song that became an international "
            "hit in the late 1980s."
        ),
    },
    {
        "id": 7,
        "title": "Bésame Mucho",
        "artist": "Consuelo Velázquez",
        "genre": "Bolero",
        "country": "México",
        "year": 1940,
        "key": "D minor",
        "tempo_bpm": 72,
        "description": (
            "One of the most famous boleros ever written, covered by "
            "countless artists worldwide."
        ),
    },
    {
        "id": 8,
        "title": "La Flaca",
        "artist": "Jarabe de Palo",
        "genre": "Pop rock / Latin",
        "country": "España / Cuba",
        "year": 1996,
        "key": "G major",
        "tempo_bpm": 116,
        "description": (
            "Hit single blending Spanish pop rock with Cuban rhythms, "
            "inspired by the singer's travels in Havana."
        ),
    },
]

# ---------------------------------------------------------------------------
# Fuzzy-matching helpers
# ---------------------------------------------------------------------------

_FUZZY_THRESHOLD = 0.45  # minimum similarity ratio to be considered a match

_HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36 "
        "MIA_TFM-Research-Agent/1.0"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
}
_HTTP_TIMEOUT = 20.0  # seconds
_PAGE_TEXT_SNIPPET_SIZE = 4000   # chars of visible text returned in no-results diagnostics
_MAX_DEBUG_CLASSES = 50          # max distinct CSS class names returned in no-results diagnostics
_MAX_RESULT_LINKS = 30           # max raw anchor links returned in no-results fallback

def _fuzzy_score(query: str, text: str) -> float:
    """Return a similarity score in [0, 1] between *query* and *text*.

    An exact substring match always scores 1.0.  Otherwise the score is
    computed with :func:`difflib.SequenceMatcher`.
    """
    q = query.lower().strip()
    t = text.lower().strip()
    if not q or not t:
        return 0.0
    if q in t:
        return 1.0
    return difflib.SequenceMatcher(None, q, t).ratio()


def _best_score(query: str, *fields: str) -> float:
    """Return the highest fuzzy score of *query* against any of *fields*."""
    return max((_fuzzy_score(query, f) for f in fields if f), default=0.0)


def _fuzzy_rank(
    query: str,
    items: list[dict],
    fields: list[str],
    threshold: float = _FUZZY_THRESHOLD,
) -> list[dict]:
    """Filter *items* by fuzzy similarity and return them sorted best-first.

    Only items whose best score across *fields* is ≥ *threshold* are kept.
    """
    scored: list[tuple[float, dict]] = []
    for item in items:
        score = _best_score(query, *(str(item.get(k, "")) for k in fields))
        if score >= threshold:
            scored.append((score, item))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in scored]


# ---------------------------------------------------------------------------
# External-database HTML parsers
# ---------------------------------------------------------------------------

_BDPI_BASE = "https://www.iberoamericadigital.net"
_CANTIGAS_BASE = "https://cantigas.fcsh.unl.pt"


_BLOCK_LEVEL_TAGS: frozenset[str] = frozenset({"div", "li", "article", "section", "tr", "p"})


def _resolve_href(href: str) -> str:
    """Resolve a relative or absolute href against the BDPI base URL."""
    return href if href.startswith("http") else _BDPI_BASE + href


def _is_real_link(href: str) -> bool:
    """Return True only for hrefs that point to an actual content page.

    Rejects pure anchors (``#``, ``#foo``), empty strings, and anything
    that resolves to just the site root, since those are UI/navigation
    links, not BDPI record URLs.
    """
    stripped = href.strip()
    if not stripped or stripped.startswith("#"):
        return False
    # Reject URLs that resolve to exactly the base domain (with or without trailing slash/hash)
    return _resolve_href(stripped).rstrip("/#") != _BDPI_BASE.rstrip("/")


# Patterns for extracting URLs from JavaScript onclick attributes.
# Matches common JS navigation idioms used in Java/Spring web apps.
_ONCLICK_URL_RE = re.compile(
    r"""(?:window\.open|window\.location(?:\.href)?\s*=|location\.href\s*=)\s*['"]([^'"]+)['"]""",
    re.IGNORECASE,
)
# Fallback: any single-quoted or double-quoted absolute path (/something...)
_ONCLICK_PATH_RE = re.compile(r"""['"](/[A-Za-z][^'"]{3,})['"]""")


def _extract_url_from_attrs(tag: Tag) -> str:
    """Try to extract a navigable URL from non-href element attributes.

    Checks (in order):
    1. ``data-href``, ``data-url``, ``data-link`` attributes on *tag*
    2. ``onclick`` attribute — parses common JS navigation patterns

    Returns an absolute URL string, or ``""`` if nothing useful is found.
    """
    for attr in ("data-href", "data-url", "data-link"):
        val = tag.get(attr, "").strip()
        if val and _is_real_link(val):
            return _resolve_href(val)

    onclick = tag.get("onclick", "")
    if onclick:
        m = _ONCLICK_URL_RE.search(onclick)
        if m:
            return _resolve_href(m.group(1).strip())
        m = _ONCLICK_PATH_RE.search(onclick)
        if m:
            return _resolve_href(m.group(1))

    return ""


def _parse_bdpi_results(soup: BeautifulSoup) -> list[dict]:
    """Extract structured records from a BDPI search-results HTML page.

    The BDPI site is a Java/Spring web application.  In the current live
    markup, result items are rendered as ``<tr>`` rows inside
    ``<table class="recordList">``.  Each row contains a
    ``<p class="titleShort"><b><a href="…">`` element (title + URL) and
    one or more ``<span class="datos">`` elements (creator, date).

    Multiple CSS selector strategies are tried in order so that the parser
    remains functional even when the BDPI site layout is updated.
    """
    records: list[dict] = []

    def _build_record(el: Tag) -> dict | None:
        """Extract a record dict from a result element, or None to skip it."""
        url = ""
        title = ""

        # Pass 1 – look for an <a> with a real href
        for a in el.find_all("a", href=True):
            if _is_real_link(a["href"]):
                url = _resolve_href(a["href"])
                title = a.get_text(" ", strip=True)
                break

        # Pass 2 – many Java/Spring apps use href="#" + onclick for navigation;
        # fall back to extracting the URL from data-* / onclick attributes.
        if not url:
            for a in el.find_all("a"):
                extracted = _extract_url_from_attrs(a)
                if extracted:
                    url = extracted
                    title = a.get_text(" ", strip=True)
                    break

        # Pass 3 – check the container element itself for data attributes
        if not url:
            url = _extract_url_from_attrs(el)

        if not url:
            return None

        # Ensure we have a usable title (fall back to visible element text)
        if not title:
            title = el.get_text(" ", strip=True)[:200]

        record: dict = {"title": title, "url": url, "source": "BDPI"}

        # Extract labelled metadata pairs: <span class="etiqueta"> / <span class="valor">
        labels = el.select("span.etiqueta")
        values = el.select("span.valor")
        for lbl, val in zip(labels, values):
            key = lbl.get_text(strip=True).rstrip(":").lower()
            record[key] = val.get_text(" ", strip=True)

        # If no labelled pairs found, collect all non-empty text nodes
        if len(record) == 3:
            texts = [
                t.get_text(" ", strip=True)
                for t in el.find_all(["span", "td", "p", "dd"])
                if t.get_text(strip=True)
            ]
            if texts:
                record["metadata"] = "; ".join(texts)

        return record

    # ------------------------------------------------------------------
    # Selector strategy cascade
    # ------------------------------------------------------------------

    # Strategy 1 – original BDPI markup (div/li with class "resultado")
    result_divs = soup.select("div.resultado") or soup.select("li.resultado")

    # Strategy 1b – partial class match for "resultado" (catches resultado-item,
    # resultado-lista, etc.) which handles minor BDPI markup updates.
    # Note: do NOT require a real href here – BDPI often uses href="#" + onclick.
    if not result_divs:
        result_divs = soup.find_all(
            lambda tag: tag.name in {"div", "li", "article"}
            and any("resultado" in c for c in tag.get("class", []))
        )

    # Strategy 1c – BDPI current markup: <table class="recordList"> whose rows
    # each contain a <p class="titleShort"><b><a href="…"> element (title/URL)
    # and <span class="datos"> elements (author, date).  This strategy is tried
    # before Strategy 2 because the page also contains a <div class="resultados">
    # that holds only sort/filter controls (not the actual records), which would
    # otherwise hijack Strategy 2 and block all later strategies from running.
    if not result_divs:
        record_table = soup.find("table", class_="recordList")
        if record_table:
            for row in record_table.find_all("tr"):
                title_p = row.find("p", class_="titleShort")
                if not title_p:
                    continue
                a = title_p.find("a", href=True)
                if not a:
                    continue
                url = _resolve_href(a["href"])
                # Strip leading ordinal "N. " added by the server
                raw_title = a.get_text(" ", strip=True)
                title = re.sub(r"^\d+\.\s*", "", raw_title)
                record: dict = {"title": title, "url": url, "source": "BDPI"}
                datos = [
                    s.get_text(" ", strip=True).lstrip("- ").strip()
                    for s in row.find_all("span", class_="datos")
                    if s.get_text(strip=True).lstrip("- ").strip()
                ]
                if datos:
                    record["metadata"] = "; ".join(datos)
                records.append(record)
            if records:
                return records

    # Strategy 2 – container with id/class "resultados"
    if not result_divs:
        container = (
            soup.find(id="resultados")
            or soup.find(class_="resultados")
            or soup.find(id="results")
            or soup.find(class_="results")
        )
        if container:
            result_divs = container.find_all(["div", "li", "article"], recursive=False)

    # Strategy 3 – DSpace digital-library layout
    if not result_divs:
        result_divs = (
            soup.select("li.ds-artifact-item")
            or soup.select("div.ds-artifact-item")
            or soup.select("div.artifact-description")
        )

    # Strategy 4 – common result/item class patterns
    if not result_divs:
        for cls_fragment in (
            "result-item", "search-result", "item-metadata", "record",
            "item-resultado", "ficha", "registro", "obra",
        ):
            result_divs = soup.find_all(
                lambda tag, f=cls_fragment: tag.name in {"div", "li", "article"}
                and any(f in c for c in tag.get("class", []))
            )
            if result_divs:
                break

    # Strategy 4b – container whose class/id contains "lista" or "list" +
    # children that each contain at least one link.
    if not result_divs:
        for cls_fragment in ("listaResultados", "lista-resultados", "lista_resultados",
                             "resultList", "result-list", "search-results"):
            container = soup.find(
                lambda tag: tag.name in {"ul", "ol", "div", "table"}
                and any(cls_fragment.lower() in c.lower() for c in tag.get("class", []))
            )
            if container:
                candidates = container.find_all(
                    ["li", "div", "article", "tr"], recursive=False
                )
                if candidates:
                    result_divs = candidates
                    break

    # Strategy 5 – generic <article> elements on the page
    if not result_divs:
        result_divs = soup.find_all("article")

    # Strategy 6 – table rows (skip header row)
    if not result_divs:
        table = soup.find("table")
        if table:
            rows = table.find_all("tr")[1:]  # skip header
            for row in rows:
                cells = row.find_all(["td", "th"])
                if not cells:
                    continue
                link = next(
                    (a for a in row.find_all("a", href=True) if _is_real_link(a["href"])),
                    None,
                )
                if not link:
                    continue
                href = _resolve_href(link["href"])
                records.append({
                    "title": link.get_text(" ", strip=True),
                    "url": href,
                    "metadata": " | ".join(
                        c.get_text(" ", strip=True) for c in cells if c.get_text(strip=True)
                    ),
                    "source": "BDPI",
                })
            return records

    # Strategy 7 – anchor-based fallback: find <a> tags with real hrefs or
    # onclick-based navigation and collect their closest block-level parent.
    # Note: BDPI is an aggregator whose results link to external institutions
    # (Europeana, BNE, etc.), so we do NOT restrict to _BDPI_BASE URLs here.
    if not result_divs:
        seen_parents: set[int] = set()
        for a in soup.find_all("a"):
            # Accept either a real href or an onclick URL
            href = a.get("href", "")
            if _is_real_link(href):
                candidate_url = _resolve_href(href)
            else:
                candidate_url = _extract_url_from_attrs(a)
            if not candidate_url:
                continue
            # Walk up to the nearest block-level ancestor
            parent = a.parent
            while parent and parent.name not in _BLOCK_LEVEL_TAGS:
                parent = parent.parent
            if parent and id(parent) not in seen_parents:
                seen_parents.add(id(parent))
                result_divs.append(parent)

    # ------------------------------------------------------------------
    # Convert candidate elements to record dicts (shared post-processing)
    # ------------------------------------------------------------------
    for el in result_divs:
        rec = _build_record(el)
        if rec:
            records.append(rec)

    return records


def _parse_cantigas_results(soup: BeautifulSoup) -> list[dict]:
    """Extract structured records from a Cantigas de Santa Maria search page.

    The site renders results in an HTML ``<table>`` whose columns are
    (number, genre/type, incipit/title, manuscript source).
    """
    records: list[dict] = []

    table = soup.find("table")
    if not table:
        return records

    rows = table.find_all("tr")
    # Determine header row to map column positions
    header_row = rows[0] if rows else None
    headers: list[str] = []
    if header_row:
        headers = [
            th.get_text(strip=True).lower()
            for th in header_row.find_all(["th", "td"])
        ]

    for row in rows[1:]:
        cells = row.find_all(["td", "th"])
        if not cells:
            continue

        # Build record from header-aligned cells when headers are available
        if headers and len(cells) == len(headers):
            record: dict = {"source": "Cantigas de Santa Maria"}
            for h, cell in zip(headers, cells):
                link = cell.find("a", href=True)
                if link:
                    href = link["href"]
                    if not href.startswith("http"):
                        href = _CANTIGAS_BASE + "/" + href.lstrip("/")
                    record["url"] = href
                record[h] = cell.get_text(" ", strip=True)
        else:
            # Heuristic fallback: first cell = number/id, rest = text
            link = cells[0].find("a", href=True) if cells else None
            url = ""
            if link:
                href = link["href"]
                if not href.startswith("http"):
                    href = _CANTIGAS_BASE + "/" + href.lstrip("/")
                url = href

            record = {
                "source": "Cantigas de Santa Maria",
                "number": cells[0].get_text(strip=True) if cells else "",
                "title": cells[1].get_text(" ", strip=True) if len(cells) > 1 else "",
                "genre": cells[2].get_text(strip=True) if len(cells) > 2 else "",
                "manuscript": cells[3].get_text(strip=True) if len(cells) > 3 else "",
            }
            if url:
                record["url"] = url

        if any(v for k, v in record.items() if k not in {"source", "url"}):
            records.append(record)

    return records


# ---------------------------------------------------------------------------
# FastMCP Server
# ---------------------------------------------------------------------------

mcp = FastMCP(MCP_SERVER_NAME)


# ---- Local catalogue tools -------------------------------------------------

@mcp.tool()
def search_songs(query: str) -> list[dict]:
    """Fuzzy-search the local catalogue by title or artist name.

    Matches are ranked by similarity so near-spellings (e.g. "Guantanamera"
    vs "guantanamara") still surface the right results.

    Args:
        query: Search term to match against song titles and artist names.
            Must be a non-empty string – pass the song title or artist name
            from the user's question.

    Returns:
        A list of matching song records, best matches first.
        If query is empty, returns all records so the caller receives
        something useful rather than an empty list.
    """
    if not query or not query.strip():
        # Empty query: return the full catalogue so the model has something
        # to present rather than a silent no-results response.
        return SONGS_DB
    return _fuzzy_rank(query, SONGS_DB, ["title", "artist"])


@mcp.tool()
def get_song_by_id(song_id: int) -> dict | None:
    """Get detailed information about a song by its ID.

    Args:
        song_id: The unique identifier of the song.

    Returns:
        The song record, or None if not found.
    """
    for song in SONGS_DB:
        if song["id"] == song_id:
            return song
    return None


@mcp.tool()
def list_genres() -> list[str]:
    """List all distinct genres available in the catalogue.

    Returns:
        A sorted list of unique genre names.
    """
    return sorted({song["genre"] for song in SONGS_DB})


@mcp.tool()
def search_by_country(country: str) -> list[dict]:
    """Fuzzy-search songs by country of origin.

    Args:
        country: Country name or partial name to filter by.

    Returns:
        A list of matching song records, best matches first.
    """
    return _fuzzy_rank(country, SONGS_DB, ["country"])


@mcp.tool()
def analyze_song(song_id: int) -> dict | None:
    """Return a musical analysis summary for a song.

    The analysis includes key, tempo, and descriptive commentary.

    Args:
        song_id: The unique identifier of the song to analyse.

    Returns:
        A dictionary with the analysis, or None if the song is not found.
    """
    song = get_song_by_id(song_id)
    if song is None:
        return None

    tempo = song["tempo_bpm"]
    if tempo < 80:
        tempo_desc = "slow"
    elif tempo < 120:
        tempo_desc = "moderate"
    else:
        tempo_desc = "fast"

    return {
        "title": song["title"],
        "artist": song["artist"],
        "key": song["key"],
        "tempo_bpm": tempo,
        "tempo_description": tempo_desc,
        "genre": song["genre"],
        "country": song["country"],
        "summary": (
            f"'{song['title']}' by {song['artist']} is a {tempo_desc}-tempo "
            f"piece in {song['key']} ({tempo} BPM) rooted in the "
            f"{song['genre']} tradition from {song['country']}. "
            f"{song['description']}"
        ),
    }


# ---- External database tools -----------------------------------------------

@mcp.tool()
def search_bdpi(query: str, page_size: int = 10) -> list[dict]:
    """Search the BDPI (Biblioteca Digital del Patrimonio Iberoamericano).

    Queries the live BDPI catalogue at iberoamericadigital.net for items
    matching *query*.  Results are then fuzzy-ranked so the closest matches
    appear first.

    The search uses non-exact (substring/stemmed) matching on the BDPI side,
    and an additional client-side fuzzy re-ranking step is applied on the
    returned titles and creator names.

    Args:
        query: Search term — title, composer, keyword, or any free text.
        page_size: Maximum number of raw results to request from BDPI (1-50).

    Returns:
        A list of record dicts, each containing at minimum ``title`` and
        ``url``.  Additional keys (``autor``, ``fecha``, ``tipo``, etc.) are
        included when present in the BDPI response.  On network or parse
        failure an ``[{"error": "..."}]`` list is returned.
    """
    try:
        # Enforce a minimum of 10 so that a model passing page_size=1 still
        # retrieves enough results for useful output.
        page_size = max(10, min(int(page_size), 50))
    except (TypeError, ValueError):
        page_size = 10

    def _bdpi_simple_params(value: str) -> list[tuple[str, str]]:
        """Build simple (non-advanced) BDPI search parameters.

        The simplest form only needs ``text`` and pagination params.
        This is tried first because it avoids issues with invalid field
        names in the advanced form (e.g. ``todos`` may not be a valid
        BDPI field selector in all site versions).
        """
        return [
            ("text", value),
            ("pageNumber", "1"),
            ("pageSize", str(page_size)),
            ("languageView", "es"),
        ]

    def _bdpi_params(field: str, value: str, n: int) -> list[tuple[str, str]]:
        """Build BDPI advanced-search query parameters.

        The BDPI form uses ``numfields`` / ``field<N>`` / ``field<N>val`` /
        ``field<N>Op`` instead of the simple ``text`` parameter.  The
        ``text`` key must be present but empty when using advanced mode.
        """
        return [
            ("numfields", str(n)),
            ("field1", field),
            ("field1val", value),
            ("field1Op", "AND"),
            ("text", ""),
            ("advanced", "true"),
            ("pageNumber", "1"),
            ("pageSize", str(page_size)),
            ("languageView", "es"),
        ]

    def _bdpi_query_field_params(value: str, field: str = "todos") -> list[tuple[str, str]]:
        """Build query= + field= style parameters.

        The BDPI homepage simple-search form uses ``query`` (not ``text``)
        as the parameter name for the search input, and ``field`` (not the
        advanced numfields syntax) as the field selector.  This matches the
        URL pattern seen when submitting the homepage search box:
        ``Search.do?query=<text>&field=todos&pageSize=…``
        """
        return [
            ("query", value),
            ("field", field),
            ("oper", "AND"),
            ("pageNumber", "1"),
            ("pageSize", str(page_size)),
            ("languageView", "es"),
        ]

    # Search-pass strategy (broadest first).
    # Each entry is (tag, value) where tag drives which parameter builder is used:
    #   "_query"     → query=<v>&field=todos  (most likely actual BDPI homepage form)
    #   "_query_tit" → query=<v>&field=titulo
    #   "_simple"    → text=<v>              (alternate simple form)
    #   "_texto"     → texto=<v>             (Spanish param-name variant)
    #   "_busqueda"  → busqueda=<v>          (Spanish word for 'search')
    #   field name   → numfields/field1/field1val advanced form
    search_passes: list[tuple[str, str]] = [
        ("_query", query),       # query=<q>&field=todos  – homepage form (most likely)
        ("_query_tit", query),   # query=<q>&field=titulo – title-only fallback
        ("_simple", query),      # text=<q>               – alternate simple form
        ("_texto", query),       # texto=<q>              – Spanish param-name variant
        ("_busqueda", query),    # busqueda=<q>           – another Spanish variant
        ("todos", query),        # advanced numfields form, field=todos
        ("titulo", query),       # advanced numfields form, field=titulo
    ]

    resp_text = ""
    final_url = f"{_BDPI_BASE}/BDPI/Search.do"
    records: list[dict] = []
    soup: BeautifulSoup = BeautifulSoup("", "html.parser")

    # Per-request extra headers: Referer tells the server we came from the
    # BDPI homepage, which some Java/Spring apps require to return results.
    _search_headers = {
        **_HTTP_HEADERS,
        "Referer": f"{_BDPI_BASE}/BDPI/Inicio.do",
    }

    try:
        with httpx.Client(
            headers=_HTTP_HEADERS,
            timeout=_HTTP_TIMEOUT,
            follow_redirects=True,
        ) as client:
            # Session pre-flight: visit the BDPI homepage so the server issues a
            # JSESSIONID cookie.  Many Java/Spring portals require an active
            # session before Search.do returns result HTML (instead of redirecting
            # back to the homepage or returning an empty result set).
            try:
                inicio_resp = client.get(f"{_BDPI_BASE}/BDPI/Inicio.do")
                # Also try POST on the homepage form to establish the session more firmly.
                if inicio_resp.status_code < 400:
                    client.post(
                        f"{_BDPI_BASE}/BDPI/Search.do",
                        data={
                            "query": query,
                            "field": "todos",
                            "oper": "AND",
                            "pageNumber": "1",
                            "pageSize": str(page_size),
                            "languageView": "es",
                        },
                        headers=_search_headers,
                    )
            except httpx.HTTPError:
                pass  # Non-fatal; proceed even if the pre-flight fails.

            for pass_tag, value in search_passes:
                if pass_tag == "_query":
                    params = _bdpi_query_field_params(value, "todos")
                elif pass_tag == "_query_tit":
                    params = _bdpi_query_field_params(value, "titulo")
                elif pass_tag == "_simple":
                    params = _bdpi_simple_params(value)
                elif pass_tag == "_texto":
                    params = [
                        ("texto", value),
                        ("pageNumber", "1"),
                        ("pageSize", str(page_size)),
                        ("languageView", "es"),
                    ]
                elif pass_tag == "_busqueda":
                    params = [
                        ("busqueda", value),
                        ("pageNumber", "1"),
                        ("pageSize", str(page_size)),
                        ("languageView", "es"),
                    ]
                else:
                    params = _bdpi_params(pass_tag, value, 1)

                # Try GET first, then POST (some Spring MVC apps require POST for search).
                resp = None
                for method in ("GET", "POST"):
                    try:
                        if method == "GET":
                            resp = client.get(
                                f"{_BDPI_BASE}/BDPI/Search.do",
                                params=params,
                                headers=_search_headers,
                            )
                        else:
                            resp = client.post(
                                f"{_BDPI_BASE}/BDPI/Search.do",
                                data=dict(params),
                                headers=_search_headers,
                            )
                        resp.raise_for_status()
                    except httpx.HTTPError:
                        resp = None
                        continue

                    resp_text = resp.text
                    final_url = str(resp.url)
                    soup = BeautifulSoup(resp_text, "html.parser")
                    records = _parse_bdpi_results(soup)
                    if records:
                        break  # found results for this HTTP method

                if records:
                    break  # found results – no need for next pass
    except httpx.HTTPError as exc:
        return [{"error": f"BDPI request failed: {exc}"}]

    if not records:
        # Save the raw HTML so the developer can inspect what the BDPI returned.
        import os
        import tempfile
        debug_path = os.path.join(tempfile.gettempdir(), "bdpi_debug.html")
        try:
            with open(debug_path, "w", encoding="utf-8") as _f:
                _f.write(resp_text)
        except OSError:
            debug_path = "(could not write)"

        page_title = soup.title.get_text(strip=True) if soup.title else "(no title)"
        raw_text = soup.get_text(" ", strip=True)[:_PAGE_TEXT_SNIPPET_SIZE]
        body_text = " ".join(raw_text.split())

        # Collect CSS classes of all block-level tags to help diagnose selector
        # mismatches — this lets the developer see what class names BDPI uses.
        block_classes: list[str] = []
        for tag in soup.find_all(["div", "li", "article", "section", "ul", "table"]):
            classes = tag.get("class", [])
            tag_id = tag.get("id", "")
            if classes:
                block_classes.append(f"{tag.name}.{'.'.join(classes)}")
            elif tag_id:
                block_classes.append(f"{tag.name}#{tag_id}")
        # Deduplicate while preserving insertion order, keep max 50
        seen: dict[str, None] = {}
        for c in block_classes:
            seen[c] = None
        unique_classes = list(seen.keys())[:_MAX_DEBUG_CLASSES]

        # Extract all visible links with real hrefs as a LLM-usable fallback.
        # Even if the HTML parser cannot identify result containers, the LLM
        # can read these links and present them to the user.
        result_links: list[dict] = []
        for a in soup.find_all("a", href=True):
            href = a.get("href", "")
            if _is_real_link(href):
                text = a.get_text(" ", strip=True)
                if text:
                    result_links.append({"text": text, "url": _resolve_href(href)})
        # Remove duplicates by URL, keep first 30
        seen_urls: dict[str, None] = {}
        deduped_links: list[dict] = []
        for lnk in result_links:
            if lnk["url"] not in seen_urls:
                seen_urls[lnk["url"]] = None
                deduped_links.append(lnk)
        result_links = deduped_links[:_MAX_RESULT_LINKS]

        return [
            {
                "info": "No structured results found in BDPI for this query.",
                "direct_search_url": (
                    f"{_BDPI_BASE}/BDPI/Search.do?"
                    + urlencode({"query": query, "field": "todos",
                                 "pageSize": str(page_size)})
                ),
                "fetched_url": final_url,
                "page_title": page_title,
                "page_text_snippet": body_text,
                "debug_html_path": debug_path,
                "html_block_classes": unique_classes,
                "result_links": result_links,
            }
        ] + [
            # Surface each link as a flat pseudo-result so the model can
            # present the individual records to the user.
            {"title": lnk["text"], "url": lnk["url"], "source": "BDPI (link fallback)"}
            for lnk in result_links
        ]

    # Client-side fuzzy re-ranking; threshold=0.0 keeps ALL server-returned
    # records (the BDPI server already matched them by full-text search — their
    # titles may differ from the query, so filtering by title similarity would
    # silently discard genuinely relevant results).  We still sort so the
    # closest title matches float to the top.
    return _fuzzy_rank(query, records, ["title", "autor", "creator"], threshold=0.0)


@mcp.tool()
def search_cantigas(query: str) -> list[dict]:
    """Search the Cantigas de Santa Maria database (cantigas.fcsh.unl.pt).

    Queries the live online database of the 13th-century Galician-Portuguese
    *Cantigas de Santa Maria* corpus.  Results are fuzzy-ranked by incipit
    (first line / title) and genre.

    Args:
        query: Search term — incipit text, cantiga number, genre, or keyword.

    Returns:
        A list of record dicts with keys such as ``number``, ``title``
        (incipit), ``genre``, ``manuscript``, and ``url``.  On network or
        parse failure an ``[{"error": "..."}]`` list is returned.
    """
    # The Cantigas site exposes a search form at pesquisa.asp.
    # The main text-search parameter accepted by the form is "incipit".
    params = {"incipit": query}

    try:
        with httpx.Client(
            headers=_HTTP_HEADERS,
            timeout=_HTTP_TIMEOUT,
            follow_redirects=True,
        ) as client:
            resp = client.get(
                f"{_CANTIGAS_BASE}/pesquisa.asp", params=params
            )
            resp.raise_for_status()
    except httpx.HTTPError as exc:
        return [{"error": f"Cantigas request failed: {exc}"}]

    soup = BeautifulSoup(resp.text, "html.parser")
    records = _parse_cantigas_results(soup)

    if not records:
        return [{"info": "No results found in the Cantigas database for this query."}]

    # Fuzzy re-rank against title (incipit) and genre columns; threshold=0.0
    # keeps all server-returned records so no valid match is silently dropped.
    title_keys = ["title", "incipit", "título", "íncipit"]
    genre_keys = ["genre", "tipo", "género"]
    rank_fields = title_keys + genre_keys
    return _fuzzy_rank(query, records, rank_fields, threshold=0.0)


# ---------------------------------------------------------------------------
# Entry-point – run the server over stdio
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()

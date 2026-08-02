import json
import time
import urllib.parse
import urllib.request
from html.parser import HTMLParser

from arcgdlw.paths import get_app_data_dir

SOURCE_URL = "https://codeberg.org/mikf/gallery-dl/raw/branch/master/docs/supportedsites.md"

_CACHE_FILE = get_app_data_dir() / "supported_sites_cache.json"
_CACHE_TTL_SECONDS = 24 * 60 * 60


class _SupportedSitesParser(HTMLParser):
    """Parses the <table> embedded in gallery-dl's supportedsites.md.

    Row shape: <tr id="..."><td>Name</td><td>URL</td><td><span title="...">Cap</span> | ...</td><td>Auth</td></tr>
    """

    def __init__(self):
        super().__init__()
        self.sites: list[dict] = []
        self._in_tbody = False
        self._row: dict | None = None
        self._col = -1
        self._buffer: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "tbody":
            self._in_tbody = True
        elif tag == "tr" and self._in_tbody:
            self._row = {"name": "", "url": "", "capabilities": "", "auth": ""}
            self._col = -1
        elif tag == "td" and self._row is not None:
            self._col += 1
            self._buffer = []

    def handle_endtag(self, tag):
        if tag == "td" and self._row is not None:
            text = "".join(self._buffer)
            if self._col == 0:
                self._row["name"] = text.strip()
            elif self._col == 1:
                self._row["url"] = text.strip()
            elif self._col == 2:
                parts = [p.strip() for p in text.split("|")]
                self._row["capabilities"] = ", ".join(p for p in parts if p)
            elif self._col == 3:
                self._row["auth"] = text.strip()
        elif tag == "tr" and self._row is not None:
            if self._row["name"] and self._row["url"]:
                self.sites.append(self._row)
            self._row = None
        elif tag == "tbody":
            self._in_tbody = False

    def handle_data(self, data):
        if self._row is not None and self._col >= 0:
            self._buffer.append(data)


def fetch_sites(timeout: float = 15.0) -> list[dict]:
    """Downloads and parses the live supported-sites table. Raises on network failure."""
    request = urllib.request.Request(SOURCE_URL, headers={"User-Agent": "ARCGDLW"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        html_text = response.read().decode("utf-8", errors="replace")
    parser = _SupportedSitesParser()
    parser.feed(html_text)
    return parser.sites


def _load_cache() -> tuple[list[dict], float] | None:
    if not _CACHE_FILE.exists():
        return None
    try:
        data = json.loads(_CACHE_FILE.read_text())
        return data["sites"], data["fetched_at"]
    except Exception:
        return None


def _save_cache(sites: list[dict]) -> None:
    _CACHE_FILE.write_text(json.dumps({"sites": sites, "fetched_at": time.time()}, indent=2))


def get_cached_sites() -> list[dict] | None:
    """Sites from disk cache only (no network), regardless of age. None if never fetched."""
    cached = _load_cache()
    return cached[0] if cached else None


def get_cache_age_seconds() -> float | None:
    cached = _load_cache()
    return (time.time() - cached[1]) if cached else None


def get_sites(force_refresh: bool = False) -> list[dict]:
    """Cached sites if fresh enough, otherwise fetches live (and re-caches).

    Falls back to a stale cache if the live fetch fails, so a flaky connection
    doesn't break something that already worked before.
    """
    if not force_refresh:
        cached = _load_cache()
        if cached and (time.time() - cached[1]) < _CACHE_TTL_SECONDS:
            return cached[0]
    try:
        sites = fetch_sites()
        _save_cache(sites)
        return sites
    except Exception:
        cached = _load_cache()
        if cached:
            return cached[0]
        raise


def _hostname(url: str) -> str | None:
    host = urllib.parse.urlparse(url).hostname
    if not host:
        return None
    host = host.lower()
    return host[4:] if host.startswith("www.") else host


def extract_hostnames(sites: list[dict]) -> set[str]:
    hosts: set[str] = set()
    for site in sites:
        host = _hostname(site["url"])
        if host:
            hosts.add(host)
    return hosts


def is_well_formed_url(url: str) -> bool:
    try:
        parsed = urllib.parse.urlparse(url)
    except ValueError:
        return False
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def unrecognized_urls(urls: list[str], known_hosts: set[str]) -> list[str]:
    """URLs whose host (or any parent domain) isn't in known_hosts.

    Soft signal only — gallery-dl also supports generic/direct-link URLs that
    aren't in the curated supported-sites table, so this never blocks by itself.
    """
    unknown = []
    for url in urls:
        host = _hostname(url)
        if not host:
            continue
        parts = host.split(".")
        candidates = {".".join(parts[i:]) for i in range(len(parts))}
        if not candidates & known_hosts:
            unknown.append(url)
    return unknown

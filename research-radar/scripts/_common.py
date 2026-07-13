"""Shared helpers for research-radar source scripts.

Every source script prints ONE JSON object to stdout and exits:

    success: {"source": <name>, "count": N, "hits": [<hit>, ...]}
    failure: {"source": <name>, "count": 0, "hits": [], "error": "<msg>"}

The orchestrator (SKILL.md) always parses stdout as JSON, so a failing source
must never crash with a traceback — it emits the error envelope and returns.

Unified hit contract (every key present, values may be empty/zero):

    id           str   canonical key for dedup (see SKILL.md "Dedupe")
    title        str
    url          str
    kind         str   one of: paper | code | discuss | model
    date         str   ISO 8601 (full or YYYY-MM-DD); "" if unknown
    summary_raw  str   raw abstract / description / selftext snippet
    metrics      dict  source-specific popularity numbers (stars, points, ...)
    extra        dict  anything else worth carrying (authors, license, topics)
"""
import json
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone, timedelta

# HTTP status codes worth retrying (transient server/rate-limit failures).
_RETRY_CODES = {429, 500, 502, 503, 504}

DEFAULT_UA = "research-radar/1.0 (+local skill; python-urllib)"

# Cap how long we'll honor a server's Retry-After on a 429, so a hostile/huge
# value can't stall a run indefinitely. arXiv asks for ~3s between requests.
_RATELIMIT_BACKOFF_CAP_S = 30.0


def utcnow():
    return datetime.now(timezone.utc)


def parse_since(s="30d"):
    """Parse a cutoff expression into an aware UTC datetime.

    Accepted forms:
      "Nd"        -> now minus N days
      "YYYY-MM"   -> first day of that month
      "YYYY-MM-DD"-> that date
      ISO string  -> parsed directly
    """
    s = (s or "30d").strip()
    m = re.fullmatch(r"(\d+)d", s)
    if m:
        return utcnow() - timedelta(days=int(m.group(1)))
    m = re.fullmatch(r"(\d{4})-(\d{2})", s)
    if m:
        return datetime(int(m.group(1)), int(m.group(2)), 1, tzinfo=timezone.utc)
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), tzinfo=timezone.utc)
    try:
        dt = datetime.fromisoformat(s)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        raise ValueError(
            "Unrecognized --since %r (use Nd, YYYY-MM, or YYYY-MM-DD)" % s
        )


def emit(source, hits, error=None):
    """Print the standard JSON envelope to stdout. Always valid JSON."""
    doc = {"source": source, "count": len(hits), "hits": hits}
    if error:
        doc["error"] = error
    print(json.dumps(doc, ensure_ascii=False))


def _backoff_seconds(http_err, attempt):
    """How long to sleep before retrying a retryable HTTPError.

    For 429 (rate limit): honor the server's `Retry-After` header (capped at
    _RATELIMIT_BACKOFF_CAP_S) when it's a plain delta-seconds value; otherwise
    use a longer base — arXiv asks for >=3s between requests, so on a saturated
    shared IP we slow down rather than hammer harder. For 5xx, the usual 2s/4s
    ladder. `attempt` is 0-based.
    """
    if http_err.code == 429:
        headers = getattr(http_err, "headers", None)
        retry_after = headers.get("Retry-After") if headers else None
        if retry_after:
            try:
                return min(float(retry_after), _RATELIMIT_BACKOFF_CAP_S)
            except (TypeError, ValueError):
                pass  # Retry-After as an HTTP-date — fall through to the ladder
        return (attempt + 1) * 3  # 3s, 6s, 9s, ...
    return (attempt + 1) * 2      # 5xx: 2s, 4s, 6s, ...


def get_bytes(url, headers=None, timeout=20, retries=2):
    """Fetch URL bytes with simple exponential backoff on transient errors.

    Retries on HTTP 429/5xx and network/timeout errors so a single slow or
    rate-limited endpoint (arXiv is notorious for this) doesn't sink a run.
    On 429 the server's Retry-After is honored (capped) so we don't pile on a
    saturated IP. Raises the last error if all attempts fail.
    """
    last_err = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url)
            req.add_header("User-Agent", DEFAULT_UA)
            for k, v in (headers or {}).items():
                req.add_header(k, v)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code in _RETRY_CODES and attempt < retries:
                time.sleep(_backoff_seconds(e, attempt))
                continue
            raise
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last_err = e
            if attempt < retries:
                time.sleep((attempt + 1) * 2)
                continue
            raise
    raise last_err


def get_text(url, headers=None, timeout=20, retries=2):
    return get_bytes(url, headers, timeout, retries).decode("utf-8", "replace")


def get_json(url, headers=None, timeout=20, retries=2):
    return json.loads(get_text(url, headers, timeout, retries))


def truncate(s, n=600):
    # Be defensive: some sources hand us a list/other where a string is expected
    # (e.g. DBLP 'venue' can be a list). Coerce rather than crash.
    if not isinstance(s, str):
        if isinstance(s, list):
            s = s[0] if s and isinstance(s[0], str) else (str(s[0]) if s else "")
        elif s is None:
            s = ""
        else:
            s = str(s)
    s = s.strip()
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def to_iso(dt):
    """Best-effort ISO-8601 'Z' string from datetime / epoch / str."""
    if not dt:
        return ""
    if isinstance(dt, (int, float)):
        dt = datetime.fromtimestamp(float(dt), tz=timezone.utc)
    if isinstance(dt, str):
        return dt
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

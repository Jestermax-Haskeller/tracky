"""Small shared helpers used by multiple Tracky modules."""

from __future__ import annotations

# Standard-library helpers cover stable cache filenames, Windows environment
# folders, process-name cleanup, IP/domain validation, and packaged-runtime
# detection. Keeping these helpers in one module prevents browser and database
# code from slowly developing different URL rules.
import hashlib
import ipaddress
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse


# These host names are intentionally allowed even though they do not contain a
# public suffix. They are common local-development targets that a real browser
# can legitimately open. Public single-word strings such as "colour" or "home"
# are rejected because they are usually page text accidentally read by UIA.
LOCAL_HOST_EXACT = {
    "localhost",
    "localhost.localdomain",
}
LOCAL_HOST_SUFFIXES = (
    ".localhost",
    ".local",
    ".test",
)

# DNS labels may contain letters, numbers, and hyphens, but a label cannot begin
# or end with a hyphen. Internationalized domains reach Python in their ASCII
# punycode form and therefore also match this expression.
DNS_LABEL_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")


def app_data_dir() -> Path:
    """Return a writable per-user folder for Tracky's local data.

    Windows applications should not write beside the executable because that
    folder may be read-only, for example under Program Files. LOCALAPPDATA is
    the conventional place for app-specific caches and databases.

    TRACKY_DATA_DIR is also supported for advanced users who intentionally want
    Tracky's data in a portable or custom folder.
    """
    override = os.environ.get("TRACKY_DATA_DIR")
    if override:
        root = Path(override)
    elif sys.platform == "win32":
        root = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Tracky"
    else:
        # The application targets Windows, but a conventional home-folder fallback
        # keeps shared utility code predictable when inspected on another OS.
        root = Path.home() / ".tracky"

    root.mkdir(parents=True, exist_ok=True)
    (root / "icons").mkdir(exist_ok=True)
    (root / "favicons").mkdir(exist_ok=True)
    return root


def week_start_for(moment: datetime) -> datetime:
    """Return Monday 00:00 for the week containing *moment*."""
    midnight = moment.replace(hour=0, minute=0, second=0, microsecond=0)
    return midnight - timedelta(days=midnight.weekday())


def format_duration(seconds: float) -> str:
    """Format seconds as a compact human-readable screen-time duration."""
    seconds = max(0, int(seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes = remainder // 60
    if hours:
        return f"{hours}h {minutes:02d}m"
    return f"{minutes}m"


def pretty_process_name(process_name: str) -> str:
    """Convert names such as ``minecraft.exe`` into ``Minecraft``."""
    stem = re.sub(r"\.exe$", "", process_name, flags=re.IGNORECASE)
    stem = re.sub(r"[_-]+", " ", stem).strip()
    return stem.title() or process_name


def is_valid_web_host(host: str | None) -> bool:
    """Return True only for believable public, local, or IP browser hosts.

    Windows UI Automation can occasionally return text from a webpage input
    instead of the address bar. Requiring a valid IP, an approved local host, or
    a syntactically valid dotted DNS name removes fake entries such as ``as`` or
    ``colour`` while still allowing ``localhost`` and common development hosts.
    """
    if not host:
        return False

    candidate = host.strip().lower().rstrip(".")
    if not candidate:
        return False

    # Convert internationalized host names to their ASCII DNS form before
    # applying label rules, so legitimate Unicode domains are not discarded.
    try:
        candidate = candidate.encode("idna").decode("ascii")
    except UnicodeError:
        return False

    if candidate in LOCAL_HOST_EXACT or candidate.endswith(LOCAL_HOST_SUFFIXES):
        return True

    # IP addresses are valid browser targets even though they have no domain
    # suffix. ipaddress also rejects malformed numeric lookalikes for us.
    try:
        ipaddress.ip_address(candidate)
        return True
    except ValueError:
        pass

    # A normal public hostname needs at least one dot. The final label must look
    # like a real TLD, which filters strings such as "document.title" less
    # aggressively than a maintained public-suffix database while staying fully
    # offline and dependency free.
    labels = candidate.split(".")
    if len(labels) < 2 or any(not DNS_LABEL_RE.fullmatch(label) for label in labels):
        return False

    tld = labels[-1]
    if tld.startswith("xn--"):
        return len(tld) > 4
    return len(tld) >= 2 and tld.isalpha()


def normalise_url(raw: str | None) -> str | None:
    """Turn an address-bar string into a validated HTTP or HTTPS URL."""
    if not raw:
        return None

    value = raw.strip()
    if not value or any(ch.isspace() for ch in value):
        return None

    if "://" not in value:
        value = "https://" + value

    try:
        parsed = urlparse(value)
        if parsed.scheme.lower() not in {"http", "https"}:
            return None
        if not is_valid_web_host(parsed.hostname):
            return None

        # Accessing parsed.port validates malformed ports such as :abc. We do not
        # need the value itself, but forcing the parse prevents broken addresses
        # from entering the tracker.
        _ = parsed.port
        return value
    except ValueError:
        return None


def domain_from_url(url: str | None) -> str | None:
    """Extract a validated lowercase host without a leading ``www.``."""
    if not url:
        return None
    try:
        host = (urlparse(url).hostname or "").lower().rstrip(".")
    except ValueError:
        return None

    if host.startswith("www."):
        host = host[4:]
    return host if is_valid_web_host(host) else None


def shorten_text(text: str, limit: int = 65) -> str:
    """Return text no longer than *limit*, ending long values with three periods.

    Labeling rows use 65 characters by default so long browser paths cannot push
    the label and category controls off smaller Tracky windows.
    """
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)] + "..."


def safe_icon_filename(entity_key: str, extension: str = ".png") -> str:
    """Create a filesystem-safe stable filename from an entity key."""
    digest = hashlib.sha256(entity_key.encode("utf-8")).hexdigest()[:20]
    return digest + extension


def resource_path(relative: str) -> Path:
    """Find bundled assets both from source and inside a PyInstaller build."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base = Path(getattr(sys, "_MEIPASS"))
    else:
        # utils.py lives in tracky/, while assets/ is one level above it.
        base = Path(__file__).resolve().parent.parent
    return base / relative

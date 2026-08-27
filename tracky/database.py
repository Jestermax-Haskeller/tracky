"""SQLite persistence for Tracky.

The database layer deliberately opens short lived connections. Tracky's UI and
its tracking loop run on different threads, and one connection per operation
keeps SQLite thread ownership simple for people learning from the code.
"""

from __future__ import annotations

# sqlite3 is Tracky's local data store. contextmanager makes connection cleanup
# automatic, Path handles data locations, and Iterable documents batch helpers.
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable

from .utils import app_data_dir, is_valid_web_host, pretty_process_name


# A brand-new Tracky install deliberately starts with only two folders.
# Misc is the normal purple catch-all, while Browsing is a neutral gray bucket
# for browser activity that has not yet become a mature website entity.
DEFAULT_CATEGORIES = (
    ("Misc", "#9B5CFF", 1),
    ("Browsing", "#85818E", 1),
)

# Browser process names are repeated here rather than importing tracker.py.
# Keeping the persistence layer independent prevents a circular import while
# still letting a browser with an unreadable URL default to Browsing.
BROWSER_PROCESS_NAMES = {
    "chrome.exe",
    "msedge.exe",
    "brave.exe",
    "firefox.exe",
    "opera.exe",
    "opera_gx.exe",
    "vivaldi.exe",
}

# Calendar rendering uses the same one-minute confirmation threshold as the live
# tracker. This also cleans up sub-minute fragments already stored by older
# Tracky builds before the debounce behavior existed.
MIN_CONFIRMED_SESSION_SECONDS = 60.0


class Database:
    """Own all persistent data used by the tracker and interface."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (app_data_dir() / "tracky.sqlite3")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._create_schema()

    @contextmanager
    def connect(self):
        """Open a transaction and always close it before returning."""
        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        try:
            # WAL lets the background tracker write while the Home page reads.
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA foreign_keys=ON")
            yield connection
            connection.commit()
        finally:
            connection.close()

    def _create_schema(self) -> None:
        """Create tables and seed categories without deleting older user data."""
        with self.connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    started_at REAL NOT NULL,
                    ended_at REAL NOT NULL,
                    duration REAL NOT NULL DEFAULT 0,
                    process_name TEXT NOT NULL,
                    process_path TEXT,
                    window_title TEXT,
                    url TEXT,
                    domain TEXT,
                    entity_key TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_sessions_time
                    ON sessions(started_at, ended_at);
                CREATE INDEX IF NOT EXISTS idx_sessions_entity
                    ON sessions(entity_key);

                CREATE TABLE IF NOT EXISTS labels (
                    entity_key TEXT PRIMARY KEY,
                    label TEXT NOT NULL,
                    custom_icon TEXT
                );

                CREATE TABLE IF NOT EXISTS categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    color TEXT NOT NULL,
                    is_builtin INTEGER NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS entity_categories (
                    entity_key TEXT PRIMARY KEY,
                    category_id INTEGER NOT NULL,
                    FOREIGN KEY(category_id) REFERENCES categories(id)
                        ON UPDATE CASCADE ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                """
            )
            db.executemany(
                """
                INSERT INTO categories(name, color, is_builtin)
                VALUES (?, ?, ?)
                ON CONFLICT(name) DO NOTHING
                """,
                DEFAULT_CATEGORIES,
            )

            # Older Tracky builds called the catch-all category Other. Upgrade
            # that built-in cleanly to Misc without losing any assignments. If
            # both rows exist, move old assignments to Misc before deleting the
            # obsolete built-in row. User-created categories are never removed.
            misc = db.execute(
                "SELECT id FROM categories WHERE name = 'Misc' COLLATE NOCASE"
            ).fetchone()
            other = db.execute(
                "SELECT id, is_builtin FROM categories WHERE name = 'Other' COLLATE NOCASE"
            ).fetchone()
            if misc and other and int(other["is_builtin"]):
                db.execute(
                    "UPDATE entity_categories SET category_id = ? WHERE category_id = ?",
                    (int(misc["id"]), int(other["id"])),
                )
                db.execute("DELETE FROM categories WHERE id = ?", (int(other["id"]),))

            # Previous releases also seeded Work, Study, Creative, Gaming,
            # Social, and Entertainment. Remove only legacy built-ins that have
            # never been assigned. If a user actually organized something into
            # one of them, keep that category so an upgrade never loses intent.
            db.execute(
                """
                DELETE FROM categories
                 WHERE is_builtin = 1
                   AND lower(name) NOT IN ('misc', 'browsing')
                   AND id NOT IN (SELECT category_id FROM entity_categories)
                """
            )

            # Built-in colors are part of the default visual language. Updating
            # these two rows also makes upgraded databases match fresh installs.
            db.execute(
                "UPDATE categories SET color = '#9B5CFF' WHERE name = 'Misc' COLLATE NOCASE"
            )
            db.execute(
                "UPDATE categories SET color = '#85818E' WHERE name = 'Browsing' COLLATE NOCASE"
            )

            # Older browser UI Automation builds could occasionally store page
            # text such as "colour" as a fake one-word website. Preserve that
            # screen time by converting invalid web entities back to their owning
            # browser application instead of deleting the user's tracked minutes.
            invalid_web_rows = db.execute(
                """
                SELECT id, process_name, domain, entity_key
                  FROM sessions
                 WHERE entity_key LIKE 'web:%'
                """
            ).fetchall()
            for row in invalid_web_rows:
                domain = (row["domain"] or row["entity_key"].removeprefix("web:")).lower()
                if is_valid_web_host(domain):
                    continue
                process_name = (row["process_name"] or "browser.exe").lower()
                db.execute(
                    """
                    UPDATE sessions
                       SET url = NULL, domain = NULL, entity_key = ?
                     WHERE id = ?
                    """,
                    (f"app:{process_name}", int(row["id"])),
                )

    # ------------------------------------------------------------------
    # Session recording
    # ------------------------------------------------------------------
    def start_session(self, activity: dict, timestamp: float) -> int:
        """Create one row when focused activity changes.

        The tracker already validates browser URLs, but the database repeats the
        host check as a trust boundary. If accessibility text ever slips through
        again, the time is kept as generic browser use instead of a fake website.
        """
        activity = dict(activity)
        entity_key = activity.get("entity_key") or ""
        if entity_key.startswith("web:"):
            host = activity.get("domain") or entity_key.removeprefix("web:")
            if not is_valid_web_host(host):
                activity["url"] = None
                activity["domain"] = None
                process_name = (activity.get("process_name") or "browser.exe").lower()
                activity["entity_key"] = f"app:{process_name}"

        with self.connect() as db:
            cursor = db.execute(
                """
                INSERT INTO sessions(
                    started_at, ended_at, duration, process_name, process_path,
                    window_title, url, domain, entity_key
                ) VALUES (?, ?, 0, ?, ?, ?, ?, ?, ?)
                """,
                (
                    timestamp,
                    timestamp,
                    activity["process_name"],
                    activity.get("process_path"),
                    activity.get("window_title"),
                    activity.get("url"),
                    activity.get("domain"),
                    activity["entity_key"],
                ),
            )
            return int(cursor.lastrowid)

    def extend_session(self, session_id: int, ended_at: float) -> None:
        """Extend the current row instead of inserting one row every second."""
        with self.connect() as db:
            db.execute(
                """
                UPDATE sessions
                   SET ended_at = ?, duration = MAX(0, ? - started_at)
                 WHERE id = ?
                """,
                (ended_at, ended_at, session_id),
            )

    def sessions_between(self, start_ts: float, end_ts: float) -> list[dict]:
        """Return all sessions that overlap the requested range."""
        with self.connect() as db:
            rows = db.execute(
                """
                SELECT * FROM sessions
                 WHERE ended_at > ? AND started_at < ?
                 ORDER BY started_at ASC
                """,
                (start_ts, end_ts),
            ).fetchall()
        return [dict(row) for row in rows]

    def total_between(self, start_ts: float, end_ts: float) -> float:
        """Return clipped screen time for a range, including edge sessions."""
        total = 0.0
        for row in self.sessions_between(start_ts, end_ts):
            total += max(
                0.0,
                min(float(row["ended_at"]), end_ts)
                - max(float(row["started_at"]), start_ts),
            )
        return total

    # ------------------------------------------------------------------
    # Labels and custom icons
    # ------------------------------------------------------------------
    def label_map(self) -> dict[str, dict]:
        with self.connect() as db:
            rows = db.execute("SELECT * FROM labels").fetchall()
        return {row["entity_key"]: dict(row) for row in rows}

    def set_label(self, entity_key: str, label: str) -> None:
        label = label.strip()
        if not label:
            return
        with self.connect() as db:
            db.execute(
                """
                INSERT INTO labels(entity_key, label, custom_icon)
                VALUES (?, ?, NULL)
                ON CONFLICT(entity_key) DO UPDATE SET label = excluded.label
                """,
                (entity_key, label),
            )

    def set_custom_icon(self, entity_key: str, icon_path: str) -> None:
        """Save an icon override without replacing an existing label."""
        with self.connect() as db:
            existing = db.execute(
                "SELECT label FROM labels WHERE entity_key = ?", (entity_key,)
            ).fetchone()
            if existing:
                db.execute(
                    "UPDATE labels SET custom_icon = ? WHERE entity_key = ?",
                    (icon_path, entity_key),
                )
            else:
                db.execute(
                    "INSERT INTO labels(entity_key, label, custom_icon) VALUES (?, '', ?)",
                    (entity_key, icon_path),
                )

    # ------------------------------------------------------------------
    # Categories
    # ------------------------------------------------------------------
    def categories(self) -> list[dict]:
        """Return available categories in a stable, friendly order."""
        with self.connect() as db:
            rows = db.execute(
                """
                SELECT * FROM categories
                ORDER BY CASE name
                    WHEN 'Misc' THEN 0
                    WHEN 'Browsing' THEN 1
                    ELSE 10
                END, name COLLATE NOCASE
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def create_category(self, name: str, color: str) -> int:
        """Create or recolor a category and return its database id."""
        name = name.strip()
        color = color.strip().upper()
        if not name:
            raise ValueError("Category name cannot be empty")
        if len(color) != 7 or not color.startswith("#"):
            raise ValueError("Category color must be a six digit hex value")
        int(color[1:], 16)
        with self.connect() as db:
            db.execute(
                """
                INSERT INTO categories(name, color, is_builtin)
                VALUES (?, ?, 0)
                ON CONFLICT(name) DO UPDATE SET color = excluded.color
                """,
                (name, color),
            )
            row = db.execute(
                "SELECT id FROM categories WHERE name = ? COLLATE NOCASE", (name,)
            ).fetchone()
            return int(row["id"])

    def set_entity_category(self, entity_key: str, category_id: int) -> None:
        """Remember the category chosen for an app or mature website."""
        with self.connect() as db:
            db.execute(
                """
                INSERT INTO entity_categories(entity_key, category_id)
                VALUES (?, ?)
                ON CONFLICT(entity_key) DO UPDATE SET category_id = excluded.category_id
                """,
                (entity_key, category_id),
            )

    def delete_category(self, category_id: int) -> str:
        """Delete one user-created category without losing activity history.

        Misc and Browsing are permanent because Tracky's automatic grouping
        rules depend on them. Before deleting a custom category, every entity
        assigned to it is moved to Misc. Session rows themselves are untouched.
        The deleted category name is returned so callers can provide feedback.
        """
        with self.connect() as db:
            category = db.execute(
                "SELECT id, name, is_builtin FROM categories WHERE id = ?",
                (int(category_id),),
            ).fetchone()
            if category is None:
                raise ValueError("Category no longer exists")
            if int(category["is_builtin"]):
                raise ValueError("Misc and Browsing cannot be deleted")

            misc = db.execute(
                "SELECT id FROM categories WHERE name = 'Misc' COLLATE NOCASE"
            ).fetchone()
            if misc is None:
                raise RuntimeError("Tracky's Misc category is missing")

            db.execute(
                "UPDATE entity_categories SET category_id = ? WHERE category_id = ?",
                (int(misc["id"]), int(category_id)),
            )
            db.execute("DELETE FROM categories WHERE id = ?", (int(category_id),))
            return str(category["name"])

    def _category_maps(self) -> tuple[dict[int, dict], dict[str, int]]:
        with self.connect() as db:
            categories = [dict(r) for r in db.execute("SELECT * FROM categories").fetchall()]
            assignments = {
                r["entity_key"]: int(r["category_id"])
                for r in db.execute("SELECT * FROM entity_categories").fetchall()
            }
        return {int(c["id"]): c for c in categories}, assignments

    def category_for_entity(self, entity_key: str, auto_browsing: bool = False) -> dict:
        """Resolve an entity category, optionally forcing the Browsing bucket."""
        categories, assignments = self._category_maps()
        by_name = {c["name"].lower(): c for c in categories.values()}
        if auto_browsing:
            return by_name["browsing"]
        category_id = assignments.get(entity_key)
        return categories.get(category_id) or by_name["misc"]

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------
    def get_setting(self, key: str, default: str | None = None) -> str | None:
        with self.connect() as db:
            row = db.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return str(row["value"]) if row else default

    def set_setting(self, key: str, value: str | int | float | bool) -> None:
        with self.connect() as db:
            db.execute(
                """
                INSERT INTO settings(key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (key, str(value)),
            )

    # ------------------------------------------------------------------
    # Aggregation for Labeling and Home
    # ------------------------------------------------------------------
    def entity_summaries(self) -> list[dict]:
        """Aggregate sessions into the rows shown on the Labeling page."""
        with self.connect() as db:
            rows = db.execute(
                """
                SELECT
                    s.entity_key,
                    SUM(s.duration) AS total_duration,
                    MAX(s.ended_at) AS last_seen,
                    (SELECT s2.process_name FROM sessions s2
                      WHERE s2.entity_key = s.entity_key
                      ORDER BY s2.ended_at DESC LIMIT 1) AS process_name,
                    (SELECT s2.process_path FROM sessions s2
                      WHERE s2.entity_key = s.entity_key
                      ORDER BY s2.ended_at DESC LIMIT 1) AS process_path,
                    (SELECT s2.url FROM sessions s2
                      WHERE s2.entity_key = s.entity_key AND s2.url IS NOT NULL
                      ORDER BY s2.ended_at DESC LIMIT 1) AS latest_url,
                    l.label,
                    l.custom_icon,
                    ec.category_id
                FROM sessions s
                LEFT JOIN labels l ON l.entity_key = s.entity_key
                LEFT JOIN entity_categories ec ON ec.entity_key = s.entity_key
                GROUP BY s.entity_key
                ORDER BY last_seen DESC
                """
            ).fetchall()

        categories, _assignments = self._category_maps()
        by_name = {c["name"].lower(): c for c in categories.values()}
        result: list[dict] = []
        for row in rows:
            item = dict(row)
            key = item["entity_key"]
            if key.startswith("web:") and not is_valid_web_host(key.removeprefix("web:")):
                # This is a second defensive layer for externally edited or very
                # old databases. Normal tracking should never reach this branch.
                continue
            total = float(item.get("total_duration") or 0)
            auto_browsing = key.startswith("web:") and total < 600
            browser_process = (item.get("process_name") or "").lower() in BROWSER_PROCESS_NAMES

            if item.get("label"):
                effective = item["label"]
            elif auto_browsing:
                effective = "Browsing"
            elif key.startswith("web:"):
                # Mature websites use only their domain by default. The full URL
                # remains in latest_url for the Labeling detail line.
                effective = key.removeprefix("web:")
            else:
                effective = pretty_process_name(item.get("process_name") or key)

            if auto_browsing:
                category = by_name["browsing"]
            else:
                assigned = categories.get(item.get("category_id"))
                if assigned:
                    category = assigned
                elif browser_process and key.startswith("app:"):
                    # Browser processes with no readable URL still belong in the
                    # gray Browsing folder by default, but remain user-editable.
                    category = by_name["browsing"]
                else:
                    category = by_name["misc"]

            item["effective_label"] = effective
            item["category_id"] = int(category["id"])
            item["category_name"] = category["name"]
            item["category_color"] = category["color"]
            item["auto_browsing"] = auto_browsing
            result.append(item)
        return result

    def resolved_session_labels(self, sessions: Iterable[dict]) -> dict[str, str]:
        """Keep the compact helper for older callers that still use this API."""
        labels = self.label_map()
        totals = {
            item["entity_key"]: float(item["total_duration"] or 0)
            for item in self.entity_summaries()
        }
        result: dict[str, str] = {}
        for session in sessions:
            key = session["entity_key"]
            if key in result:
                continue
            if labels.get(key, {}).get("label"):
                result[key] = labels[key]["label"]
            elif key.startswith("web:"):
                result[key] = (
                    "Browsing"
                    if totals.get(key, 0) < 600
                    else key.removeprefix("web:")
                )
            else:
                result[key] = pretty_process_name(session["process_name"])
        return result

    def _duration_before(self, entity_key: str, timestamp: float) -> float:
        """Return historical duration for an entity before an exact timestamp."""
        with self.connect() as db:
            rows = db.execute(
                """
                SELECT started_at, ended_at
                  FROM sessions
                 WHERE entity_key = ? AND started_at < ?
                """,
                (entity_key, timestamp),
            ).fetchall()
        total = 0.0
        for row in rows:
            total += max(0.0, min(float(row["ended_at"]), timestamp) - float(row["started_at"]))
        return total

    @staticmethod
    def _confirmed_sessions_for_calendar(sessions: list[dict]) -> list[dict]:
        """Remove old sub-minute noise and bridge quick returns to the same entity.

        New tracking already debounces focus changes, but existing databases can
        contain tiny rows created by older builds. If a short interruption sits
        between two rows for the same entity, treat the whole interval as the
        original entity. Otherwise omit the short row, leaving a genuine blank
        gap instead of a misleading zero-minute block.
        """
        rows = [dict(row) for row in sessions]
        result: list[dict] = []
        index = 0

        while index < len(rows):
            row = rows[index]
            duration = max(
                float(row.get("duration") or 0.0),
                float(row.get("ended_at") or 0.0) - float(row.get("started_at") or 0.0),
            )

            if duration >= MIN_CONFIRMED_SESSION_SECONDS:
                result.append(row)
                index += 1
                continue

            next_row = rows[index + 1] if index + 1 < len(rows) else None
            if (
                result
                and next_row is not None
                and result[-1].get("entity_key") == next_row.get("entity_key")
            ):
                # Extend the prior visual session through the brief interruption
                # and the following same-entity row, matching the new live tracker.
                merged = dict(result[-1])
                merged["ended_at"] = next_row["ended_at"]
                merged["duration"] = max(
                    0.0,
                    float(merged["ended_at"]) - float(merged["started_at"]),
                )
                result[-1] = merged
                index += 2
                continue

            # A short row with no matching activity on both sides is simply not
            # painted. The empty vertical space communicates uncertain/transient
            # focus without cluttering the graph.
            index += 1

        return result

    def calendar_segments_between(self, start_ts: float, end_ts: float) -> list[dict]:
        """Build renderable calendar segments with labels and category colors.

        Website time has a special rule. The first ten cumulative minutes for a
        domain are represented as Browsing. If the ten minute mark is crossed in
        the middle of one session, this method splits that session at the exact
        threshold so the calendar visibly changes at that point.
        """
        sessions = self._confirmed_sessions_for_calendar(
            self.sessions_between(start_ts, end_ts)
        )
        labels = self.label_map()
        categories, assignments = self._category_maps()
        by_name = {c["name"].lower(): c for c in categories.values()}

        web_keys = {s["entity_key"] for s in sessions if s["entity_key"].startswith("web:")}
        cumulative = {key: self._duration_before(key, start_ts) for key in web_keys}
        result: list[dict] = []

        for row in sessions:
            row_start = max(float(row["started_at"]), start_ts)
            row_end = min(float(row["ended_at"]), end_ts)
            if row_end <= row_start:
                continue

            key = row["entity_key"]
            if key.startswith("web:") and not is_valid_web_host(key.removeprefix("web:")):
                continue
            if key.startswith("web:"):
                before = cumulative.get(key, 0.0)
                duration = row_end - row_start
                threshold_left = max(0.0, 600.0 - before)

                if threshold_left > 0:
                    browsing_end = min(row_end, row_start + threshold_left)
                    if browsing_end > row_start:
                        result.append(
                            self._make_calendar_segment(
                                row,
                                row_start,
                                browsing_end,
                                "Browsing",
                                by_name["browsing"],
                                auto_browsing=True,
                            )
                        )
                    site_start = browsing_end
                else:
                    site_start = row_start

                if site_start < row_end:
                    label = labels.get(key, {}).get("label") or key.removeprefix("web:")
                    category = categories.get(assignments.get(key)) or by_name["misc"]
                    result.append(
                        self._make_calendar_segment(
                            row,
                            site_start,
                            row_end,
                            label,
                            category,
                            auto_browsing=False,
                        )
                    )
                cumulative[key] = before + duration
            else:
                label = labels.get(key, {}).get("label") or pretty_process_name(row["process_name"])
                assigned = categories.get(assignments.get(key))
                if assigned:
                    category = assigned
                elif (row.get("process_name") or "").lower() in BROWSER_PROCESS_NAMES:
                    category = by_name["browsing"]
                else:
                    category = by_name["misc"]
                result.append(
                    self._make_calendar_segment(
                        row,
                        row_start,
                        row_end,
                        label,
                        category,
                        auto_browsing=False,
                    )
                )

        return result

    @staticmethod
    def _make_calendar_segment(
        row: dict,
        started_at: float,
        ended_at: float,
        label: str,
        category: dict,
        auto_browsing: bool,
    ) -> dict:
        segment = dict(row)
        segment["started_at"] = started_at
        segment["ended_at"] = ended_at
        segment["duration"] = max(0.0, ended_at - started_at)
        segment["activity_label"] = label
        # The hover card should never expose a browser path/query. For website
        # entities it therefore receives only the domain, while app entities use
        # the same friendly activity label painted in the calendar.
        segment["hover_label"] = (
            segment["entity_key"].removeprefix("web:")
            if segment["entity_key"].startswith("web:")
            else label
        )
        segment["category_id"] = int(category["id"])
        segment["category_name"] = category["name"]
        segment["category_color"] = category["color"]
        segment["auto_browsing"] = auto_browsing
        return segment

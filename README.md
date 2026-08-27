# tracky

Tracky is a Windows screen time tracker written primarily in Python. It records only the application that owns the foreground window. For supported browsers it also attempts to read the visible address bar through Windows UI Automation. Tracking history, labels, categories, colors, and preferences are stored locally in SQLite under `%LOCALAPPDATA%\Tracky`.

<p align="center">
  <img src="assets/media/1.png" alt="Tracky home screen" width="900">
</p>

## Installation

### Recommended: download the installer

If you just want to use Tracky, you do **not** need Python, Git, Inno Setup, or any development tools.

Download the latest stable Windows installer from:

**[Download Tracky from GitHub Releases](https://github.com/Jestermax-Haskeller/tracky/releases/tag/Stable)**

Download `TrackySetup.exe`, open it, approve the Windows administrator prompt, and complete the setup wizard.

Tracky will then be installed normally on Windows and will appear under:

```text
Settings > Apps > Installed apps
```

After installation, search for **tracky** from the Windows Start menu to launch it.

## Build Tracky yourself

Tracky is completely open source, so you can also clone the repository and build the Windows installer yourself.

### Requirements

Tracky currently targets:

* Windows 10 or Windows 11
* 64-bit Python 3.14
* Inno Setup 6
* Git

You can install the required development tools with `winget`:

```powershell
winget install -e --id Python.Python.3.14
winget install -e --id JRSoftware.InnoSetup
winget install -e --id Git.Git
```

Clone the repository:

```powershell
git clone https://github.com/Jestermax-Haskeller/tracky.git
cd tracky
```

Build the installer:

```powershell
.\build_installer.bat
```

The build script handles the rest automatically. It creates a Python virtual environment, installs the dependencies from `requirements.txt`, builds Tracky with PyInstaller, finds Inno Setup, creates the Windows setup package, and removes the temporary PyInstaller output afterward.

The finished installer will be placed at:

```text
installer_dist\TrackySetup.exe
```

The setup wizard opens automatically after a successful build.

### Run the Python source directly

If you are developing Tracky and want to run it without creating an installer:

```powershell
.\run_dev.bat
```

This creates the local virtual environment if required, installs dependencies, and launches `main.py`.

## Project structure

```text
tracky/
│
├── assets/
│   ├── media/
│   │   ├── 1.png
│   │   ├── 2.png
│   │   └── 3.png
│   ├── tracky.ico
│   └── tracky.png
│
├── tracky/
│   ├── pages/
│   │   ├── __init__.py
│   │   ├── home.py
│   │   ├── labeling.py
│   │   └── settings.py
│   │
│   ├── __init__.py
│   ├── browser.py
│   ├── database.py
│   ├── font_loader.py
│   ├── icons.py
│   ├── main_window.py
│   ├── startup.py
│   ├── styles.py
│   ├── tracker.py
│   ├── utils.py
│   └── widgets.py
│
├── .gitignore
├── build_installer.bat
├── installer.iss
├── LICENSE.txt
├── main.py
├── README.md
├── requirements.txt
├── run_dev.bat
├── tracky.spec
└── version_info.txt
```

### What each part does

`main.py` is the entry point for both development and the packaged application. It starts Qt, loads the theme and fonts, opens the local database, creates the main window, and starts Tracky.

`tracky/tracker.py` contains the foreground application tracking loop and Windows idle detection.

`tracky/browser.py` handles supported browser address-bar detection using Windows UI Automation.

`tracky/database.py` owns the SQLite database, session history, labels, categories, preferences, migrations, and the data used to build the Home calendar.

`tracky/widgets.py` contains the custom calendar and reusable interface components.

`tracky/pages/` contains the Home, Labeling, and Settings pages.

`tracky/icons.py` handles application icons, website favicons, cached icons, and custom user-selected icons.

`tracky/styles.py` contains Tracky's Obsidian-inspired dark theme and purple styling.

`tracky/startup.py` manages the Windows launch-at-startup preference.

`build_installer.bat`, `tracky.spec`, and `installer.iss` are the Windows release build pipeline.

<p align="center">
  <img src="assets/media/2.png" alt="Tracky screen time interface" width="900">
</p>

## How Tracky works

Tracky is designed around one simple rule:

> **Only the window you are actively focused on counts as screen time.**

It does not add up every application that happens to be open in the background.

### 1. Reading the foreground application

Tracky's tracking loop runs on a lightweight background Python thread while the PySide6 interface remains on Qt's main UI thread.

Approximately once per second, Tracky asks Windows which window currently owns the foreground using the Win32 API:

```text
GetForegroundWindow
```

It then retrieves the process ID that owns that window with:

```text
GetWindowThreadProcessId
```

From that process ID, Tracky uses `psutil` to obtain information such as:

```text
Process name
Executable path
```

The current window title is read with the normal Win32 window text APIs.

Tracky also checks its own process ID and deliberately refuses to count its own window, so checking your screen-time statistics does not increase Tracky's own screen time.

### 2. Applications become entities

Normal applications are represented internally using an entity key such as:

```text
app:minecraft.exe
app:code.exe
app:spotify.exe
```

This gives Tracky a stable identifier that can be connected to a label, icon, and category without modifying the original session history.

For example:

```text
app:minecraft.exe
        │
        ├── Label: Minecraft
        ├── Category: Gaming
        └── Color: category color
```

### 3. Browser URL tracking

When the focused process belongs to a supported browser, Tracky performs an additional check.

Supported browser processes currently include Chrome, Edge, Brave, Firefox, Opera, Opera GX, and Vivaldi.

Windows does not provide a normal API that says "give me the URL currently open in Chrome", so Tracky uses **Windows UI Automation** through `pywinauto`.

Tracky inspects the accessibility tree of the foreground browser window and searches for controls that look like the browser address bar.

It prefers controls with names or automation IDs similar to:

```text
Address and search bar
Address bar
Search or enter address
urlbar-input
omnibox
```

If those are unavailable, Tracky only considers suitable edit controls near the top browser chrome instead of blindly accepting every text box on a webpage.

The result then goes through Tracky's URL validation.

Invalid values are discarded. This prevents accidental accessibility captures such as random webpage text from becoming fake websites.

Valid public domains are accepted, along with supported local development addresses such as:

```text
localhost
127.0.0.1
192.168.1.10
```

A valid website is stored under a domain entity such as:

```text
web:github.com
web:youtube.com
web:localhost
```

The calendar and hover cards use the domain rather than exposing long paths, query strings, or page URLs.

If Tracky cannot reliably obtain a browser URL, it still tracks the browser itself instead of losing the screen time.

### 4. Short switches are filtered

A common problem with screen-time trackers is creating hundreds of tiny entries when someone quickly Alt-Tabs between windows.

Tracky avoids that with a **60 second confirmation period**.

If you switch from one activity to another, the new activity becomes a pending switch.

If you return to the original activity before 60 seconds have passed, Tracky treats the interruption as temporary and folds it back into the original session.

For example:

```text
VS Code
  │
  ├── Chrome for 18 seconds
  │
VS Code
```

becomes:

```text
VS Code
```

If Chrome remains focused for at least 60 seconds, Tracky confirms the switch and backdates the new session to the real moment the switch happened.

This keeps totals accurate without filling the calendar with tiny fragments.

### 5. Idle time is removed

Tracky also checks how long it has been since Windows received keyboard or mouse input using:

```text
GetLastInputInfo
```

After two minutes of inactivity, Tracky stops counting the current activity.

It adjusts the end of the session back to the actual last-input time, so the two-minute detection delay is not added to your screen-time total.

### 6. Website Browsing rule

New Tracky databases begin with two built-in categories:

```text
Misc
Browsing
```

`Misc` is the default purple category.

`Browsing` is gray and is used automatically for general browser usage.

A website remains part of **Browsing** during its first 10 cumulative minutes of tracked use.

If a domain reaches 10 minutes in the middle of a session, Tracky splits the calendar activity at the exact 600-second point.

For example:

```text
0m                    10m                   20m
|----------------------|---------------------|
       Browsing                  github.com
```

After the threshold, the domain becomes its own activity and can be labeled or assigned to another category by the user.

The original session history remains intact. This rule is applied while Tracky prepares the data used by the calendar and labeling interface.

## Labeling and categories

The Labeling page lets activities be organized without changing the underlying tracking records.

Applications can be renamed:

```text
minecraft.exe  ->  Minecraft
Code.exe       ->  Programming
```

Activities can also be assigned to color-coded category folders.

Categories can be collapsed to make large activity lists easier to manage.

Custom categories can be deleted by right-clicking the folder. Before the category is removed, Tracky moves every activity assigned to it back to `Misc`, so deleting a category never deletes screen-time history.

`Misc` and `Browsing` are built-in and cannot be deleted.

Application icons come from the Windows executable where possible. Website icons are cached separately, and users can replace an activity icon with their own image.

Activities with less than one cumulative minute are still stored in the database, but they are hidden from the Labeling page to reduce clutter.

<p align="center">
  <img src="assets/media/3.png" alt="Tracky labeling and categories interface" width="900">
</p>

## SQLite database

Tracky does not use a remote server.

All tracking history is stored locally using Python's built-in **SQLite** support.

The main database is stored at:

```text
%LOCALAPPDATA%\Tracky\tracky.sqlite3
```

For a normal Windows account that resolves to something similar to:

```text
C:\Users\YourName\AppData\Local\Tracky\tracky.sqlite3
```

### Why SQLite?

SQLite is useful for Tracky because it is:

* Local
* Serverless
* Fast
* Included with Python
* Stored in a single database file
* Easy to inspect while learning
* Suitable for concurrent lightweight reads and writes

Tracky enables:

```sql
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
```

**WAL**, or Write-Ahead Logging, allows the background tracker to write session updates while the interface reads statistics with much less contention.

Foreign keys keep relationships such as category assignments consistent.

Tracky opens short-lived database connections for individual operations instead of sharing one SQLite connection between the Qt UI thread and tracking thread.

### Database structure

The database contains five main tables.

#### `sessions`

This is the actual screen-time history.

```sql
CREATE TABLE sessions (
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
```

Each confirmed activity session stores its start and end timestamps, duration, process information, browser information when available, and the entity it belongs to.

Tracky does **not** create a new database row every second.

When an activity begins, one row is inserted:

```text
started_at = current time
ended_at   = current time
duration   = 0
```

As that same activity continues, Tracky updates that row:

```sql
UPDATE sessions
SET ended_at = ?,
    duration = MAX(0, ? - started_at)
WHERE id = ?;
```

This keeps the database much smaller than storing one sample every second.

Indexes are also created for time and entity lookups:

```sql
CREATE INDEX idx_sessions_time
ON sessions(started_at, ended_at);

CREATE INDEX idx_sessions_entity
ON sessions(entity_key);
```

These help the weekly calendar and statistics find relevant sessions efficiently.

#### `labels`

```sql
CREATE TABLE labels (
    entity_key TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    custom_icon TEXT
);
```

This stores a user's custom display name and optional icon for an activity.

The session itself is not renamed.

For example, the database can keep:

```text
app:minecraft.exe
```

while the interface displays:

```text
Minecraft
```

#### `categories`

```sql
CREATE TABLE categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    color TEXT NOT NULL,
    is_builtin INTEGER NOT NULL DEFAULT 0
);
```

This stores category folders and their colors.

Fresh installs start with:

```text
Misc
Browsing
```

The `is_builtin` flag protects those required categories from deletion.

#### `entity_categories`

```sql
CREATE TABLE entity_categories (
    entity_key TEXT PRIMARY KEY,
    category_id INTEGER NOT NULL,
    FOREIGN KEY(category_id) REFERENCES categories(id)
        ON UPDATE CASCADE
        ON DELETE CASCADE
);
```

This table connects an application or website to a category.

Keeping this relationship separate means the original tracking history does not have to be rewritten whenever the user reorganizes an activity.

#### `settings`

```sql
CREATE TABLE settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
```

This stores small persistent preferences such as calendar zoom and interface configuration.

Settings therefore survive application restarts without requiring another configuration file format.

### How the Home page gets its data

When Tracky displays a week, it requests only sessions that overlap the visible date range:

```sql
SELECT *
FROM sessions
WHERE ended_at > ?
  AND started_at < ?
ORDER BY started_at ASC;
```

Sessions that begin before or finish after the requested range are clipped to the visible range before totals are calculated.

Tracky then resolves:

```text
Session
  ↓
Entity
  ↓
User label
  ↓
Category
  ↓
Category color
  ↓
Calendar block / statistics
```

Website sessions additionally pass through the 10-minute Browsing rule before they are rendered.

This separation means the raw tracking history stays simple while labels, categories, and presentation can evolve independently.

## Technology

Tracky is primarily Python and uses:

| Technology     | Purpose                                                 |
| -------------- | ------------------------------------------------------- |
| Python 3.14    | Main application language                               |
| PySide6 / Qt 6 | Windows interface, animations, widgets, painting        |
| SQLite         | Local screen-time history and preferences               |
| Win32 APIs     | Foreground-window and idle-time detection               |
| psutil         | Process names and executable paths                      |
| pywinauto      | Windows UI Automation for browser address bars          |
| PyInstaller    | Packages the Python application as a Windows executable |
| Inno Setup     | Creates the normal Windows setup installer              |

## Privacy

Tracky is designed to keep your screen-time history on your own computer.

**We do not collect your screen-time data.**

There is no Tracky account, cloud database, analytics service, telemetry backend, or tracking-history server.

Your activity history remains in:

```text
%LOCALAPPDATA%\Tracky\tracky.sqlite3
```

Tracky does not record keyboard contents, passwords, mouse clicks, screenshots, or every application running on the machine. It records the foreground application and, where supported, the visible browser address information needed to determine the active domain.

The core tracking system, SQLite database, labeling, categories, statistics, and calendar all work locally without a cloud connection.

Tracky may make optional network requests for website favicons and, if Nunito is not already available on the computer, its first-run font cache. These requests are not used to upload screen-time history. The tracking database itself is never sent as part of those requests.

All Tracky source code is publicly available in this repository, so its behavior can be inspected, modified, or built independently.

Tracky is released under the **MIT License**.

### Verify your installer with SHA-256

A SHA-256 checksum lets you verify that the installer you downloaded is exactly the same file that was published in the release.

After downloading `TrackySetup.exe`, open PowerShell in the download folder and run:

```powershell
Get-FileHash .\TrackySetup.exe -Algorithm SHA256
```

PowerShell will display something like:

```text
Algorithm : SHA256
Hash      : <SHA256 HASH>
Path      : C:\...\TrackySetup.exe
```

Compare that hash with the SHA-256 value published alongside the matching Tracky release.

If the two hashes are identical, the installer has not changed since that checksum was generated.

You can generate the checksum for a release build yourself with the same command:

```powershell
Get-FileHash .\installer_dist\TrackySetup.exe -Algorithm SHA256
```

## License

Tracky is free and open source software licensed under the [MIT License](LICENSE.txt).

Source code: **https://github.com/Jestermax-Haskeller/tracky**

Stable releases: **https://github.com/Jestermax-Haskeller/tracky/releases/tag/Stable**

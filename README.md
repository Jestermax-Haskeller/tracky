# tracky

Tracky is a Windows screen time tracker written primarily in Python. It records
only the application that owns the foreground window. For supported browsers it
also attempts to read the visible address bar through Windows UI Automation.
Tracking history, labels, categories, colors, and preferences are stored locally
in SQLite under `%LOCALAPPDATA%\Tracky`.

## Project layout

```text
|-- main.py                    # Development and packaged entry point
|-- build_installer.bat        # Build the Windows setup package
|-- run_dev.bat                # Run Tracky from source
|-- requirements.txt
|-- tracky.spec                # PyInstaller recipe
|-- installer.iss              # Inno Setup recipe
|-- version_info.txt           # Windows EXE version metadata
|-- assets/
|   |-- tracky.ico
|   `-- tracky.png
`-- tracky/
    |-- browser.py             # Browser address-bar detection
    |-- database.py            # SQLite sessions, settings, labels, categories
    |-- font_loader.py         # Nunito loading and first-run cache
    |-- icons.py               # EXE icons, favicons, custom icons
    |-- startup.py             # Windows startup registration
    |-- tracker.py             # Foreground-window tracking and switch debounce
    |-- styles.py              # Obsidian-style purple theme
    |-- widgets.py             # Calendar and reusable custom widgets
    |-- main_window.py         # Navigation and rounded window shell
    `-- pages/
        |-- home.py
        |-- labeling.py
        `-- settings.py
```

## Python version

The build scripts target 64-bit Python 3.14. PySide6 and PyInstaller versions in
`requirements.txt` are selected for Python 3.14 support.

## Run from source on Windows

1. Install 64-bit Python 3.14 from python.org.
2. During Python setup, install the Python Launcher (`py`).
3. Extract this project to a writable folder.
4. Double-click `run_dev.bat`.

The script creates `.venv`, installs dependencies, and starts `main.py`.

Manual equivalent:

```bat
py -3.14 -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python main.py
```

## Build the Windows installer

Tracky is distributed through its Windows setup package rather than as a portable
EXE. The build script creates the executable internally, packages it with Inno
Setup, then removes the temporary PyInstaller output so the installer remains the
only release artifact.

1. Install 64-bit Python 3.14 from python.org, including the Python Launcher.
2. Install Inno Setup 6. With winget you can use:

```bat
winget install JRSoftware.InnoSetup
```

3. Run:

```bat
build_installer.bat
```

The script creates `.venv` when needed, installs the pinned build dependencies,
runs PyInstaller, locates Inno Setup in the current-user installation, Program
Files, or PATH, and builds:

```text
installer_dist\TrackySetup.exe
```

The temporary `build\` and `dist\` folders are removed after a successful setup
build. `TrackySetup.exe` opens automatically. Complete that wizard to install
Tracky under Program Files and register it in:

```text
Settings > Apps > Installed apps
```

The installer requests administrator permission because it performs a normal
machine-wide Program Files installation and uninstall registration.

## How website tracking works

There is no universal Windows API that directly returns another application's
current browser URL. Tracky uses Windows UI Automation to inspect the address bar
of Chrome, Edge, Brave, Firefox, Opera, Opera GX, and Vivaldi.

Browser accessibility trees can change between browser releases. If URL reading
fails, application-level foreground tracking still works. That browser process
defaults to the gray Browsing folder.

### The 10-minute Browsing rule

Tracky stores website sessions by domain, then applies the Browsing rule when it
prepares calendar segments:

1. It calculates how much time that domain accumulated before the displayed
   range.
2. The first 600 cumulative seconds are assigned to Browsing.
3. If one session crosses second 600, Tracky splits that visual session at the
   exact timestamp.
4. Time after that is represented by the domain only and defaults to Misc until
   the user chooses another category.

The full latest URL remains available as secondary context on the Labeling page,
but it is shortened to 65 characters in the row so it cannot push controls off
screen.

## Categories

A brand-new database contains only:

- `Misc`, colored `#9B5CFF`.
- `Browsing`, colored `#85818E`.

Use `+ Category` in Labeling to create another folder. The popup provides red,
orange, yellow, light green, dark green, teal, light blue, dark blue, purple, and
baby pink presets, or a custom six-digit HEX value. Right-click any custom
category folder and choose `Delete category` to remove it. Its activities are
reassigned to Misc before the category is deleted.

Older databases are migrated from the previous built-in `Other` folder to
`Misc` without losing entity assignments. Existing user-created categories are
preserved.

## Screen time, switches, and idle behavior

Only the foreground window is counted. Tracky does not count its own window.
After two minutes without keyboard or mouse input, the tracker ends the current
session at the user's last real input time.

When focus changes to another activity, Tracky waits for that exact new activity
to remain focused for 60 seconds. If the user returns sooner, the short switch is
ignored and the original session is extended across it. If the new activity
remains focused for at least 60 seconds, Tracky backdates the confirmed session
to the real switch time, so screen-time totals stay accurate.

## Favicons and privacy

Tracky attempts a 128px Google favicon first, then a site's Apple touch icon,
then the traditional `/favicon.ico`. This improves icon quality where the site
publishes a larger image.

Network favicon requests reveal the requested domain to the remote server. If
you prefer no favicon network requests, remove the network fallback code in
`tracky/icons.py` and use manual icons instead.

## Nunito and offline use

Tracky does not bundle font binaries in this source archive. At startup it:

1. Checks whether Windows already has Nunito.
2. Checks `%LOCALAPPDATA%\Tracky\fonts` for its cached copy.
3. If needed, downloads the Nunito variable font into Tracky's private cache.
4. Falls back to Segoe UI if the first launch is offline.

The interface uses normal, medium, semibold, bold, and extra-bold weights.

## Learning notes

The source is intentionally commented around each major section and design
choice. Good places to start are:

- `tracker.py` for the background thread and one-minute focus-switch debounce.
- `database.py` for SQLite access, default folders, and the ten-minute site split.
- `widgets.py` for custom sidebar icons, hover overlays, painting, wheel controls,
  animations, and the rounded application shell.
- `main_window.py` for navigation and taskbar-respecting maximize behavior.
- `pages/labeling.py` for the frameless category popup and folder grouping.
- `startup.py` for a per-user Windows startup registry entry.
- `installer.iss` for the Windows installation and uninstall registration.

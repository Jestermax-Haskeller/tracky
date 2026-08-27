# tracky

tracky is a simple screen time tracking app for windows, it organizes your screen time into categories, and displays everything in a simple weekly google calendar style.

<p align="center">
  <img src="assets/media/1.png" alt="Tracky" width="900">
</p>

## Installation

Download the latest **[Stable Release](https://github.com/Jestermax-Haskeller/tracky/releases/tag/Stable)**.

(No Python installation is required.)

## Build it yourself

### Requirements

Install Python 3.14, Git, and Inno Setup: (Powershell)

```powershell
winget install -e --id Python.Python.3.14
winget install -e --id Git.Git
winget install -e --id JRSoftware.InnoSetup
```

Clone tracky:

```powershell
git clone https://github.com/Jestermax-Haskeller/tracky.git
cd tracky
```

Compile:

```powershell
.\build_installer.bat
```

The finished build will be here:

```text
installer_dist\TrackySetup.exe
```

<p align="center">
  <img src="assets/media/2.png" alt="tracky Home" width="900">
</p>

## Project structure

```text
tracky/
├── assets/
│   └── media/
├── tracky/
│   ├── pages/
│   ├── browser.py
│   ├── database.py
│   ├── main_window.py
│   ├── tracker.py
│   ├── styles.py
│   └── widgets.py
├── main.py
├── requirements.txt
├── run_dev.bat
├── build_installer.bat
├── tracky.spec
└── installer.iss
```

## How it works


On Windows it uses:

* **Win32 APIs** to detect the foreground window and user idle time
* **psutil** to identify the application and executable
* **Windows UI Automation** to detect the current website in supported browsers
* **PySide6** for the interface
* **SQLite** for local screen time history and settings

Browser URLs are validated before being stored. tracky only counts the currently focused application.

Short switches (<1 min) between applications are ignored to keep the timeline clean (e.g. if you're switching song on Spotify).

<p align="center">
  <img src="assets/media/3.png" alt="Tracky Labeling" width="900">
</p>

## Database info

All data is stored locally in:

```text
%LOCALAPPDATA%\Tracky\tracky.sqlite3
```

SQLite stores:

* Screen time sessions
* Applications and websites
* Categories and colors
* Custom Labels
* Configured settings

tracky updates the current session instead of creating a new database entry every second, keeping the database small, simple and fast.

## Privacy

tracky is a privacy-first application.

* No accounts
* Offline database
* No analytics/telemetry
* No online backing-up
* All source code is open source

### Verify the installer

Each release includes a SHA-256 checksum.

To check your downloaded installer: (Powershell)

```powershell
Get-FileHash .\TrackySetup.exe -Algorithm SHA256
```

Latest SHA-256 checksum release:
`83B66FF57C60F83F44E843FD07CBF70FA233A4D5EAD6E2D2DE1E268DEA68172E`

## License

tracky is free and open source under the [MIT License](LICENSE.txt).

**[Download tracky](https://github.com/Jestermax-Haskeller/tracky/releases/tag/Stable)** · **[Source Code](https://github.com/Jestermax-Haskeller/tracky)**

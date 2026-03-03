# Fanbox & Patreon Extractor

A powerful and user-friendly tool to download content from pixivFANBOX and Patreon creators. It supports media/file downloads, cloud-drive link extraction, and archive link parsing.

## Features

- **Multi-threaded Downloading**: Efficiently download multiple files concurrently.
- **Multi-Platform Source**: Supports FANBOX API flow and Patreon RSS flow.
- **Smart Extraction**: Automatically detects and extracts links from text, PDF files, and archives (zip, rar, tar, 7z, gz, bz2, xz).
- **External Link Support**: Built-in support for Google Drive, Mega.nz, Dropbox, OneDrive, MediaFire, and direct file links.
- **Web UI**: A modern web interface powered by NiceGUI for easy interaction.
- **Content Organization**: Organizes downloads by creator and post date/title.
- **Resume Capability**: Skips already downloaded files to save bandwidth.
- **Markdown Generation**: Creates a `README.md` for each post with description, tags, and file links.

## Prerequisites

- **Python 3.11+**
- **[uv](https://github.com/astral-sh/uv)** (Recommended for dependency management)
- A valid `FANBOXSESSID` cookie from your browser session (required for FANBOX paid content).
- A valid Patreon RSS URL (required for Patreon mode).

## Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/yourusername/fanbox-extract.git
    cd fanbox-extract
    ```

2.  **Install dependencies:**
    Using `uv`:
    ```bash
    uv sync
    ```

## Quick Start

```bash
uv sync
uv run web_ui.py
```

Then open `http://localhost:8086` in your browser and choose `FANBOX` or `Patreon`.

Optional: protect Web UI with password login.
```bash
export WEB_UI_PASSWORD=YOUR_PASSWORD
uv run web_ui.py
```

## Usage

### Method 1: Web Interface (Recommended)

The Web UI provides a graphical way to select platform, input credentials, and monitor download progress.

```bash
uv run web_ui.py
```
Open your browser and navigate to `http://localhost:8086`.

If `WEB_UI_PASSWORD` is set, you must login first before using the Web UI.

You can put runtime config in a `.env` file at project root:

```dotenv
FANBOXSESSID=YOUR_FANBOXSESSID
PATREON_RSS_URL=https://www.patreon.com/rss?auth=...
WEB_UI_PASSWORD=YOUR_WEB_PASSWORD
```

You can configure:
- **Skip existing files**: Reuse previous downloads and save bandwidth.
- **Extract links from archives**: Parse links in PDF/ZIP/RAR/TAR/GZ files.
- **Parallel Downloads**: Control worker count for concurrent post processing.
- **Stop**: Gracefully stop the current download task.

### Method 2: Command Line Interface (CLI)

You can run the script directly from the terminal.

1.  **FANBOX interactive mode:**
    ```bash
    uv run main.py
    ```
    The script will prompt you for your `FANBOXSESSID`.

2.  **FANBOX mode with explicit platform:**
    ```bash
    uv run main.py fanbox YOUR_FANBOXSESSID
    ```

3.  **Pass Session ID as Argument (backward compatible):**
    ```bash
    uv run main.py YOUR_FANBOXSESSID
    ```
    The script will prompt you to select a creator.

4.  **Use Environment Variable:**
    ```bash
    export FANBOXSESSID=YOUR_FANBOXSESSID
    uv run main.py
    ```

5.  **Pass Session ID and Creator ID:**
    ```bash
    uv run main.py YOUR_FANBOXSESSID YOUR_CREATOR_ID
    ```

6.  **Patreon mode:**
    ```bash
    uv run main.py patreon YOUR_PATREON_RSS_URL [CREATOR_ID]
    ```

## Configuration

The tool automatically handles configuration. Downloads are saved in the `downloads/<creator_id>/` directory.

Environment variables are loaded from `.env` automatically for both `main.py` and `web_ui.py`.

### Web UI Options
- **Skip existing files**: Skip files that are already downloaded.
- **Extract links from archives**: Extract links from downloaded archive and PDF files.
- **Parallel Downloads**: Adjust the number of concurrent workers.
- **Password Login**: Set `WEB_UI_PASSWORD` to require login for `/` and `/downloads`.

### Notes
- Mega.nz auto-download uses the Python `mega.py` library and no longer requires local `mega-get`.
- Patreon mode is based on RSS. Ensure your RSS URL has permission to access creator posts.
- Some cloud drives require login, captcha, or anti-bot checks; unsupported links are still preserved in markdown.
- When auto-download fails, generated post README records machine-readable failure reason codes.

## How to get FANBOXSESSID

1.  Open your browser and log in to [pixivFANBOX](https://fanbox.cc/).
2.  Press `F12` to open Developer Tools.
3.  Go to the **Application** tab (Chrome/Edge) or **Storage** tab (Firefox).
4.  Expand **Cookies** and select `https://fanbox.cc`.
5.  Find the `FANBOXSESSID` cookie and copy its value.

## Project Structure

- `fanbox_extractor/`: Core logic package.
  - `downloader.py`: FANBOX downloader.
  - `patreon_downloader.py`: Patreon RSS downloader.
  - `extractor.py`: Link extraction logic (PDF, archives, compressed files).
  - `drivers.py`: Drivers for cloud links and direct files.
- `web_ui.py`: NiceGUI-based web interface.
- `main.py`: CLI entry point.
- `pyproject.toml`: Project configuration and dependencies.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Disclaimer

This tool is for educational purposes only. Please respect the copyright of content creators and the terms of service of pixivFANBOX.

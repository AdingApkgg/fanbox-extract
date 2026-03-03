# Fanbox Extractor

A powerful and user-friendly tool to download content from pixivFANBOX creators. This tool supports downloading images, files, and extracting external links from posts, including Google Drive and Mega.nz links.

## Features

- **Multi-threaded Downloading**: Efficiently download multiple files concurrently.
- **Smart Extraction**: Automatically detects and extracts links from text, PDF files, and archives (zip, rar, tar).
- **External Link Support**: Built-in support for downloading from Google Drive and Mega.nz.
- **Web UI**: A modern web interface powered by NiceGUI for easy interaction.
- **Content Organization**: Organizes downloads by creator and post date/title.
- **Resume Capability**: Skips already downloaded files to save bandwidth.
- **Markdown Generation**: Creates a `README.md` for each post with description, tags, and file links.

## Prerequisites

- **Python 3.11+**
- **[uv](https://github.com/astral-sh/uv)** (Recommended for dependency management)
- A valid `FANBOXSESSID` cookie from your browser session (required for accessing paid content).

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

## Usage

### Method 1: Web Interface (Recommended)

The Web UI provides a graphical way to input your Session ID, select creators, and monitor download progress.

```bash
uv run web_ui.py
```
Open your browser and navigate to `http://localhost:8081`.

### Method 2: Command Line Interface (CLI)

You can run the script directly from the terminal.

1.  **Interactive Mode:**
    ```bash
    uv run main.py
    ```
    The script will prompt you for your `FANBOXSESSID`.

2.  **Pass Session ID as Argument:**
    ```bash
    uv run main.py YOUR_FANBOXSESSID
    ```

3.  **Use Environment Variable:**
    ```bash
    export FANBOXSESSID=YOUR_FANBOXSESSID
    uv run main.py
    ```

## Configuration

The tool automatically handles configuration. Downloads are saved in the `downloads/<creator_id>/` directory.

### specific options (Web UI):
- **Skip existing files**: Check to skip files that already exist.
- **Extract links from archives**: Check to extract links from downloaded archives.
- **Parallel Downloads**: Adjust the number of concurrent downloads.

## How to get FANBOXSESSID

1.  Open your browser and log in to [pixivFANBOX](https://fanbox.cc/).
2.  Press `F12` to open Developer Tools.
3.  Go to the **Application** tab (Chrome/Edge) or **Storage** tab (Firefox).
4.  Expand **Cookies** and select `https://fanbox.cc`.
5.  Find the `FANBOXSESSID` cookie and copy its value.

## Project Structure

- `fanbox_extractor/`: Core logic package.
  - `downloader.py`: Main downloader class.
  - `extractor.py`: Link extraction logic (PDF, Archives).
  - `drivers/`: Drivers for external sites (Google Drive, Mega).
- `web_ui.py`: NiceGUI-based web interface.
- `main.py`: CLI entry point.
- `pyproject.toml`: Project configuration and dependencies.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Disclaimer

This tool is for educational purposes only. Please respect the copyright of content creators and the terms of service of pixivFANBOX.

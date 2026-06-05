# LiveJournal 2 Markdown Archive Tool
<p align="center">
  <img src="https://github.com/Jamisonfitz/livejournal2markdown/blob/main/assets/logo2.png" alt="Livejournal 2 Markdown">
</p>

This script is a utility to download, archive, and convert LiveJournal posts into markdown (`.md`) files. It provides an automated solution to backup LiveJournal blogs, preserving each post's content, title, and publishing date for posts that are public.

## Credits
- Original project and core LiveJournal archiving concept by Jamisonfitz: https://github.com/Jamisonfitz/livejournal2markdown
- Current modifications were produced largely by the AI agent **GitHub Copilot** (Raptor mini Preview) with additional coding and guidance from a human operator.

## Features:
- Fetches all post permalinks from the provided LiveJournal blog.
- Downloads each post and saves it as a markdown file.
- Adjusts the file creation and modification dates to match the post date.
- Automatically generates filenames based on post title and date.
- Supports current LiveJournal post HTML structure and multiple page layout variants.
- Outputs the progress to the console including the number of found posts and the file being archived.
- The original link to the LiveJournal post is appended to the end of each markdown file.

## Prerequisites:
- Python 3.x

## Usage:

1. **Setup**:
    - Clone this repository to your local machine.
    - Navigate to the directory.
    - Install the required Python packages by running:  
      ```bash
      pip install -r requirements.txt
      ```

2. **Run the Tool**:
    - Execute the script using Python:
      ```bash
      python main.py
      ```

3. **Output**:
    - The markdown files will be saved in the `Scraped Journals` directory where the `main.py` script is executed.

## Dependencies:

- **BeautifulSoup4**: For HTML parsing.
- **requests**: To make HTTP requests.
- **pywin32**: To modify file creation and modification dates on Windows.

## Contribution:
If you'd like to contribute, please fork the repository and make changes as you'd like. Pull requests are warmly welcome.

## Branch workflow:
For this repository, use the `experimental` branch for testing and development. When changes are approved, merge `experimental` into `main` and publish from `main`.

Example commands:
```bash
git checkout experimental
git push origin experimental
# after approval
git checkout main
git merge experimental
git push origin main
```

## Issues:
If you encounter any issues or have feature requests, please file an issue on the GitHub project. 

## Release Notes:
- v1.0.1 (06-05-2026): Added compatibility for current LiveJournal HTML layouts and multiple page variants, including newer `aentry-post` markup and older `b-singlepost` markup.

## Disclaimer:
Please use this tool responsibly. Making rapid or aggressive requests may lead to IP bans or other restrictions from LiveJournal. Always respect the terms of service of any platform you interact with.

## License:
This project is licensed under the MIT License. 

## Note:
- The script modifies the creation and modification dates of the markdown files to reflect the date of the original LiveJournal post. This way, the file metadata matches the original publishing date of the content.
- This version adds compatibility for current LiveJournal HTML layouts and updated date string formats.
- It also includes fallback handling for multiple LiveJournal page structure variants such as newer `aentry-post` markup and older `b-singlepost` markup.
- This tool is designed for public LiveJournal blogs. It may not work correctly with private or locked posts.

## Tor & Proxy Support
- Optional Tor anonymization support has been added.
- If Tor is missing, the script can prompt to install it and optionally remove it after the session.
- The script now supports SOCKS5 proxies via `requests[socks]`.

## Browser-mode support
- The script includes optional browser automation helpers for navigating WebAssembly-powered pages such as JupyterLite and Pyodide.
- This helper code is present in `main.py`, but full Selenium-based execution requires `selenium` and a compatible browser driver such as Firefox/GeckoDriver.
- In this environment, browser-mode has not been run end-to-end because Selenium and geckodriver are not installed.

## Output style selection
- The script now prompts whether to save each post as Markdown or as an HTML-like file.
- HTML mode preserves the post body structure below the site header, closer to the original page appearance, and writes `.html` files.
- The script downloads page images into a shared `assets/images/` folder so the same image URL is only saved once and reused across multiple archived posts.
- Links that point to any `livejournal.com` domain are rewritten to `*.livejournal.invalid` replicas so they look similar but cannot resolve to a real website.
- Markdown mode continues to produce readable archival Markdown files with headings and links.

## Improved Markdown fidelity
- The HTML-to-Markdown conversion has been upgraded to preserve common LiveJournal content structures such as headings, lists, links, images, code blocks, blockquotes, and tables.
- If `markdownify` is installed, the script will use it for better conversion fidelity; otherwise it falls back to an enhanced built-in converter.

## Branch workflow
For this repository, use the `experimental` branch for testing and development. When changes are approved, merge `experimental` into `main` and publish from `main`.

Example commands:
```bash
git checkout experimental
git push origin experimental
# after approval
git checkout main
git merge experimental
git push origin main
```

## Acknowledgments

### From the original creator (Jamisonfitz):
> Thank you to those who archived LiveJournal, I thought mine was long gone after nearly two decades I wanted a way to back it up that was still readable.

---

### On AI and digital curation
AI can save internet history from the "digital dark age" by continuously crawling and creating verifiable backups, but it becomes truly heartfelt when it acts as an empathetic **digital curator**. Instead of just storing cold code, AI can give fading web pages and forgotten online communities a beautiful, human-centric second life.

~Kahless

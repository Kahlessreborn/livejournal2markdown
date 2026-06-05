import os
import re
import sys
import time
import random
import shutil
import subprocess
import importlib
import importlib.util
import datetime
import hashlib
import urllib.parse

BOOTSTRAP_DEPENDENCIES = {
    'requests': ('requests[socks]', ['requests', 'PySocks']),
    'bs4': ('beautifulsoup4', ['beautifulsoup4']),
}
if sys.platform == 'win32':
    BOOTSTRAP_DEPENDENCIES['win32file'] = ('pywin32', ['pywin32'])

installed_packages_by_script = []


def is_module_available(name):
    return importlib.util.find_spec(name) is not None


def pip_install(package):
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', package])


def pip_uninstall(package):
    subprocess.check_call([sys.executable, '-m', 'pip', 'uninstall', '-y', package])


def ensure_runtime_dependencies():
    for module_name, (pip_spec, uninstall_names) in BOOTSTRAP_DEPENDENCIES.items():
        if not is_module_available(module_name):
            response = input(f"{module_name} is required but not installed. Install {pip_spec}? (y/n): ").strip().lower()
            if response != 'y':
                print(f"[X] {module_name} is required to run. Aborting.")
                sys.exit(1)
            print(f"[*] Installing {pip_spec}...")
            pip_install(pip_spec)
            installed_packages_by_script.extend(uninstall_names)


ensure_runtime_dependencies()

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
if sys.platform == 'win32':
    import pywintypes
    import win32file

# Configuration
OUTPUT_DIR = "./Scraped Journals"
IMAGE_CACHE_DIR = os.path.join(OUTPUT_DIR, 'assets', 'images')
BASE_URL_TEMPLATE = "https://{}.livejournal.com/"
TEST_DOMAIN = 'testdomain.livejournal.com'
# If the file `USE_TESTDOMAIN` exists in the repository root, or the env var USE_TESTDOMAIN is set,
# or the script is launched with `--test`, force all network requests to the test domain.
USE_TEST_DOMAIN = os.path.exists('USE_TESTDOMAIN') or os.environ.get('USE_TESTDOMAIN', '').lower() in ('1', 'true') or ('--test' in sys.argv)
SKIP_PARAM = "?skip="
REQUEST_DELAY_RANGE = (1.5, 4.5)
TOR_PROXY = {'http': 'socks5h://127.0.0.1:9050', 'https': 'socks5h://127.0.0.1:9050'}
IMAGE_CACHE = {}

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:116.0) Gecko/20100101 Firefox/116.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 13_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/116.0.0.0 Safari/537.36'
]

DEFAULT_HEADERS = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
    'Connection': 'keep-alive',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'same-origin',
    'Sec-Fetch-User': '?1',
}

# Ensure the output directory exists
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(IMAGE_CACHE_DIR, exist_ok=True)

def get_random_headers(referer=None):
    headers = DEFAULT_HEADERS.copy()
    headers['User-Agent'] = random.choice(USER_AGENTS)
    if referer:
        headers['Referer'] = referer
    return headers


def make_replica_url(href, base_url=None):
    if not href or href.startswith('#') or href.lower().startswith(('mailto:', 'javascript:', 'tel:')):
        return href

    resolved = urllib.parse.urljoin(base_url or '', href)
    parsed = urllib.parse.urlparse(resolved)
    if 'livejournal.com' not in parsed.netloc:
        return href

    new_netloc = parsed.netloc.replace('livejournal.com', 'livejournal.invalid')
    replica = parsed._replace(netloc=new_netloc)
    return urllib.parse.urlunparse(replica)


def get_local_image_path(img_url, session, base_url=None):
    if not img_url or img_url.startswith('data:'):
        return img_url

    resolved = urllib.parse.urljoin(base_url or '', img_url)
    if resolved.startswith('//'):
        resolved = 'https:' + resolved

    parsed = urllib.parse.urlparse(resolved)
    if parsed.scheme not in ('http', 'https'):
        return img_url

    if resolved in IMAGE_CACHE:
        return IMAGE_CACHE[resolved]

    filename_base = os.path.basename(parsed.path) or 'image'
    ext = os.path.splitext(filename_base)[1] or '.img'
    safe_name = re.sub(r'[^A-Za-z0-9._-]', '_', filename_base)
    if len(safe_name) > 60:
        safe_name = safe_name[:60]
    digest = hashlib.sha256(resolved.encode('utf-8')).hexdigest()[:16]
    local_filename = f"{digest}_{safe_name}"
    local_path = os.path.join(IMAGE_CACHE_DIR, local_filename)

    if os.path.exists(local_path):
        relative_path = os.path.relpath(local_path, OUTPUT_DIR).replace('\\', '/')
        IMAGE_CACHE[resolved] = relative_path
        return relative_path

    try:
        resp = session.get(resolved, headers=get_random_headers(referer=base_url), stream=True, timeout=20)
        if resp.status_code != 200:
            print(f"[!] Failed to download image: {resolved} (status {resp.status_code})")
            return img_url

        with open(local_path, 'wb') as image_file:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    image_file.write(chunk)
    except Exception as e:
        print(f"[!] Image download error for {resolved}: {e}")
        return img_url

    relative_path = os.path.relpath(local_path, OUTPUT_DIR).replace('\\', '/')
    IMAGE_CACHE[resolved] = relative_path
    return relative_path


def preprocess_post_html(html_content, session, base_url=None):
    soup = BeautifulSoup(html_content, 'html.parser')

    for img_tag in soup.find_all('img'):
        src = img_tag.get('src')
        if src:
            img_tag['src'] = get_local_image_path(src, session, base_url)

        srcset = img_tag.get('srcset')
        if srcset:
            candidates = [part.strip().split(' ')[0] for part in srcset.split(',') if part.strip()]
            if candidates:
                img_tag['src'] = get_local_image_path(candidates[0], session, base_url)
            del img_tag['srcset']

    for a_tag in soup.find_all('a', href=True):
        a_tag['href'] = make_replica_url(a_tag['href'], base_url)

    return str(soup)


def detect_os():
    if sys.platform.startswith('linux') and shutil.which('apt-get'):
        return 'linux-apt'
    elif sys.platform == 'darwin' and shutil.which('brew'):
        return 'macos-brew'
    elif sys.platform == 'win32' and shutil.which('winget'):
        return 'windows-winget'
    return 'unsupported'


def is_tor_installed():
    binary_name = 'tor.exe' if sys.platform == 'win32' else 'tor'
    return shutil.which(binary_name) is not None


def get_tor_path():
    binary_name = 'tor.exe' if sys.platform == 'win32' else 'tor'
    found_path = shutil.which(binary_name)
    if not found_path and sys.platform == 'win32':
        default_win_path = r"C:\Program Files\Tor\tor.exe"
        if os.path.exists(default_win_path):
            return default_win_path
    return found_path


def manage_tor(action, os_type):
    if os_type == 'windows-winget':
        if action == 'install':
            print("[*] Installing Tor via winget...")
            subprocess.run(['winget', 'install', 'TorProject.Tor', '--silent', '--accept-source-agreements'], check=True)
        elif action == 'uninstall':
            print("[*] Uninstalling Tor via winget...")
            subprocess.run(['winget', 'uninstall', 'TorProject.Tor', '--silent'], check=True)
    elif os_type == 'linux-apt':
        if action == 'install':
            print("[*] Installing Tor via apt...")
            subprocess.run(['sudo', 'apt-get', 'update'], check=True)
            subprocess.run(['sudo', 'apt-get', 'install', '-y', 'tor'], check=True)
        elif action == 'uninstall':
            print("[*] Purging Tor via apt...")
            subprocess.run(['sudo', 'apt-get', 'purge', '-y', 'tor'], check=True)
            subprocess.run(['sudo', 'apt-get', 'autoremove', '-y'], check=True)
    elif os_type == 'macos-brew':
        if action == 'install':
            print("[*] Installing Tor via Homebrew...")
            subprocess.run(['brew', 'install', 'tor'], check=True)
        elif action == 'uninstall':
            print("[*] Removing Tor via Homebrew...")
            subprocess.run(['brew', 'uninstall', 'tor'], check=True)


def start_tor_daemon():
    tor_cmd = get_tor_path()
    if not tor_cmd:
        raise FileNotFoundError('Tor executable not found on PATH or common install locations.')

    creation_flags = 0
    if sys.platform == 'win32':
        creation_flags = 0x08000000

    proc = subprocess.Popen(
        [tor_cmd],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        creationflags=creation_flags
    )
    return proc


def detect_tor_browser():
    """Return path to Tor Browser's Firefox binary if installed, else None."""
    candidates = []
    if sys.platform == 'win32':
        candidates.extend([
            r"C:\Program Files\Tor Browser\Browser\firefox.exe",
            r"C:\Program Files (x86)\Tor Browser\Browser\firefox.exe",
        ])
    elif sys.platform.startswith('linux'):
        home = os.path.expanduser('~')
        candidates.extend([
            os.path.join(home, 'tor-browser_en-US', 'Browser', 'firefox'),
            os.path.join(home, 'tor-browser', 'Browser', 'firefox'),
            '/opt/tor-browser/Browser/firefox',
        ])
    elif sys.platform == 'darwin':
        candidates.append('/Applications/Tor Browser.app/Contents/MacOS/firefox')

    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def start_selenium_firefox(use_tor=False, use_tor_browser=False, tor_socks_port=9150, headless=True):
    """Start a Selenium Firefox webdriver configured to use Tor's SOCKS proxy or Tor Browser binary.

    Returns a `selenium.webdriver.Firefox` instance. This function lazily imports selenium and webdriver-manager.
    """
    try:
        from selenium import webdriver
        from selenium.webdriver.firefox.options import Options
        from selenium.webdriver.firefox.service import Service
        from selenium.webdriver.common.proxy import Proxy, ProxyType
        from webdriver_manager.firefox import GeckoDriverManager
    except Exception as e:
        raise RuntimeError('Selenium or webdriver-manager not available: ' + str(e))

    options = Options()
    # If attaching to Tor Browser binary, avoid headless (Tor Browser resists headless flags)
    if use_tor_browser:
        headless = False
    options.headless = headless

    # If using Tor Browser binary, try to locate it
    if use_tor_browser:
        tb_path = detect_tor_browser()
        if tb_path:
            options.binary_location = tb_path
        else:
            raise FileNotFoundError('Tor Browser binary not found on this system')

    # Configure Firefox to use SOCKS proxy if requested
    if use_tor:
        proxy = Proxy()
        proxy.proxy_type = ProxyType.MANUAL
        proxy.socks_proxy = f'127.0.0.1:{tor_socks_port}'
        proxy.socks_version = 5
        proxy.add_to_capabilities(webdriver.DesiredCapabilities.FIREFOX)

    service = Service(GeckoDriverManager().install())
    if use_tor:
        driver = webdriver.Firefox(service=service, options=options)
        # also set network proxy prefs for Firefox profile
        try:
            driver.install_addon = getattr(driver, 'install_addon', None)
        except Exception:
            pass
    else:
        driver = webdriver.Firefox(service=service, options=options)

    return driver


def navigate_to_pyodide(url, driver, python_code, timeout=30):
    """Navigate to a Pyodide/JupyterLite page and run `python_code` inside the WASM Python runtime.

    Returns the result (or an error dict) from the Pyodide execution.
    """
    driver.get(url)

    # Wait for window.pyodide to be available
    end_time = time.time() + timeout
    while time.time() < end_time:
        try:
            has_pyodide = driver.execute_script('return typeof window.pyodide !== "undefined";')
            if has_pyodide:
                break
        except Exception:
            pass
        time.sleep(0.5)

    # If Pyodide not loaded, try to trigger loadPyodide if present
    try:
        loaded = driver.execute_script('return typeof window.pyodide !== "undefined";')
    except Exception:
        loaded = False

    if not loaded:
        raise RuntimeError('Pyodide was not detected on the page within timeout')

    # Execute the python code using the async Pyodide API
    # Use execute_async_script: the last argument is a callback to signal completion
    safe_code = python_code.replace('\\', '\\\\').replace('\n', '\\n').replace("'", "\\'")
    script = f"""
    const callback = arguments[arguments.length-1];
    (async () => {{
        try {{
            const result = await window.pyodide.runPythonAsync('{safe_code}');
            callback({{ok: true, result: result}});
        }} catch (e) {{
            callback({{ok: false, error: String(e)}});
        }}
    }})();
    """
    res = driver.execute_async_script(script)
    return res


def get_session(use_tor=False):
    """Return a requests session configured for standard or Tor traffic."""
    SET_READABILITY_URL = "https://www.livejournal.com/tools/setstylemine.bml"
    READABILITY_DATA = {
        "Widget[StyleAlwaysMine]_readability": "on",
        "Widget[StyleAlwaysMine]_user": ""
    }

    session = requests.Session()
    retries = Retry(total=3, backoff_factor=0.5, status_forcelist=[429, 500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("https://", adapter)
    session.headers.update(get_random_headers())

    if use_tor:
        session.proxies.update(TOR_PROXY)

    response = session.post(SET_READABILITY_URL, data=READABILITY_DATA, headers=get_random_headers())
    if response.status_code != 200:
        raise Exception("Failed to set readability mode.")
    return session


def pause_between_requests():
    time.sleep(random.uniform(*REQUEST_DELAY_RANGE))


def get_all_permalinks(subdomain, session):
    """Fetch all post permalinks from a LiveJournal blog."""
    if USE_TEST_DOMAIN:
        base_url = f"https://{TEST_DOMAIN}/"
    else:
        base_url = BASE_URL_TEMPLATE.format(subdomain)
    skip = 0
    all_permalinks = set()

    previous_url = None
    while True:
        current_url = base_url + SKIP_PARAM + str(skip)
        response = session.get(current_url, headers=get_random_headers(referer=previous_url))
        
        if response.status_code != 200:
            print(f"Failed to fetch the page at skip={skip}")
            break

        soup = BeautifulSoup(response.content, 'html.parser')
        permalinks = {a['href'].split('?')[0] for a in soup.find_all('a', href=True) if '.livejournal.com' in a['href'] and '.html' in a['href'] and 'www.' not in a['href']}
        
        if not permalinks or permalinks.issubset(all_permalinks):
            break

        all_permalinks.update(permalinks)
        skip += 10
        previous_url = current_url
        pause_between_requests()

    return all_permalinks

def convert_html_to_markdown(html_content):
    """Converts HTML to Markdown with better visual fidelity."""
    try:
        import markdownify
        return markdownify.markdownify(
            html_content,
            heading_style='ATX',
            bullets='-',
            strip=['style', 'script'],
            convert=['img', 'table', 'pre', 'code', 'a', 'blockquote']
        ).strip()
    except Exception:
        pass

    soup = BeautifulSoup(html_content, 'html.parser')

    for tag in soup.find_all('pre'):
        code_text = tag.get_text()
        fenced = f"\n```\n{code_text.rstrip()}\n```\n"
        tag.replace_with(fenced)

    for tag in soup.find_all('code'):
        if tag.parent.name != 'pre':
            tag.replace_with(f"`{tag.get_text()}`")

    for img_tag in soup.find_all('img'):
        alt = img_tag.get('alt', '').strip() or 'image'
        src = img_tag.get('src', '').strip()
        img_tag.replace_with(f"![{alt}]({src})")

    for tag in soup.find_all(['strong', 'b']):
        tag.replace_with(f"**{tag.get_text()}**")
    for tag in soup.find_all(['em', 'i']):
        tag.replace_with(f"*{tag.get_text()}*")
    for tag in soup.find_all('a', href=True):
        tag.replace_with(f"[{tag.get_text()}]({tag['href']})")

    for tag in soup.find_all('blockquote'):
        lines = tag.get_text().splitlines()
        quoted = '\n'.join(f"> {line}" for line in lines if line.strip())
        tag.replace_with(f"\n{quoted}\n")

    for tag in soup.find_all('br'):
        tag.replace_with("\n")

    def convert_list(tag, marker):
        items = []
        for li in tag.find_all('li', recursive=False):
            text = li.get_text(separator=' ', strip=True)
            items.append(f"{marker} {text}")
        tag.insert_before('\n'.join(items) + '\n')
        tag.decompose()

    for ul_tag in soup.find_all('ul'):
        convert_list(ul_tag, '-')
    for ol_tag in soup.find_all('ol'):
        items = []
        for index, li in enumerate(ol_tag.find_all('li', recursive=False), 1):
            text = li.get_text(separator=' ', strip=True)
            items.append(f"{index}. {text}")
        ol_tag.insert_before('\n'.join(items) + '\n')
        ol_tag.decompose()

    for table in soup.find_all('table'):
        rows = []
        for row in table.find_all('tr'):
            cells = [cell.get_text(separator=' ', strip=True) for cell in row.find_all(['th', 'td'])]
            rows.append(f"| {' | '.join(cells)} |")
        if len(rows) > 1:
            header_count = len(rows[0].split('|')) - 2
            header_sep = '| ' + ' | '.join(['---'] * header_count) + ' |'
            rows.insert(1, header_sep)
        table.insert_before('\n'.join(rows) + '\n\n')
        table.decompose()

    for h_tag in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
        level = int(h_tag.name[1])
        h_tag.replace_with(f"{'#' * level} {h_tag.get_text()}")

    text = soup.get_text()
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

def convert_html_to_html(html_content, title, date_time, original_url):
    """Wrap post HTML content in a minimal page structure for HTML-like output."""
    soup = BeautifulSoup(html_content, 'html.parser')
    body_content = soup.decode_contents()
    safe_title = BeautifulSoup('', 'html.parser')
    safe_title.append(title)

    html_page = f"""<!DOCTYPE html>
<html lang='en'>
<head>
  <meta charset='utf-8'>
  <title>{safe_title.get_text()}</title>
  <style>
    body {{ font-family: Arial, sans-serif; line-height: 1.6; margin: 2rem; }}
    article {{ max-width: 800px; margin: auto; }}
    .post-meta {{ color: #555; margin-bottom: 1rem; }}
    .original-link {{ margin-top: 2rem; font-size: 0.9rem; }}
  </style>
</head>
<body>
  <article>
    <header>
      <h1>{safe_title.get_text()}</h1>
      <div class='post-meta'>{date_time}</div>
    </header>
    {body_content}
    <footer class='original-link'>
      <p>Original post: <a href='{original_url}'>{original_url}</a></p>
    </footer>
  </article>
</body>
</html>"""
    return html_page

def sanitize_title(title):
    """Cleans up the title to make it safe for use as a filename."""
    title = title.replace('\n', ' ').replace('\r', '')
    title = re.sub(r'[<>:"/\\|?*\n\r]', '_', title)
    title = re.sub(r'\s+', ' ', title).strip()
    title = title[:50]
    return title if title else 'untitled'

def set_file_creation_time(filename, date_time_str):
    """Updates the file's creation and modification time to reflect the original post's publish date and time."""
    date_time_obj = datetime.datetime.strptime(date_time_str, '%Y-%m-%d %H:%M:%S')
    epoch_start = datetime.datetime(1970, 1, 1)
    delta_seconds = int((date_time_obj - epoch_start).total_seconds())
    win_time = pywintypes.Time(delta_seconds)
    handle = win32file.CreateFile(filename, win32file.GENERIC_WRITE, 0, None, win32file.OPEN_EXISTING, 0, 0)
    win32file.SetFileTime(handle, win_time, win_time, win_time)
    handle.Close()


def parse_date_time(date_text):
    """Normalize a LiveJournal date string into YYYY-MM-DD HH:MM:SS."""
    date_text = date_text.strip()
    if not date_text:
        raise ValueError("Empty date text")

    formats = [
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%d %H:%M',
        '%B %d %Y, %H:%M',
        '%B %d, %Y, %H:%M',
    ]
    for fmt in formats:
        try:
            parsed = datetime.datetime.strptime(date_text, fmt)
            return parsed.strftime('%Y-%m-%d %H:%M:%S')
        except ValueError:
            continue

    # Try a simple manual cleanup for ordinal days like "March 1st 2020, 12:00"
    cleaned = re.sub(r'(?P<day>\d+)(st|nd|rd|th)', r'\g<day>', date_text)
    for fmt in formats:
        try:
            parsed = datetime.datetime.strptime(cleaned, fmt)
            return parsed.strftime('%Y-%m-%d %H:%M:%S')
        except ValueError:
            continue

    raise ValueError(f"Unsupported date format: {date_text}")


def extract_and_save_content(url, session, output_mode='markdown'):
    """Extracts post details from a LiveJournal permalink and saves it as a markdown or HTML file."""
    referer = BASE_URL_TEMPLATE.format(url.split('//')[1].split('.livejournal.com')[0])
    response = session.get(url, headers=get_random_headers(referer=referer))
    if response.status_code != 200:
        print("Failed to fetch the page:", url)
        return

    soup = BeautifulSoup(response.content, 'html.parser')
    date_content = soup.find('time', class_='b-singlepost-author-date')
    if not date_content:
        date_content = soup.find('time')

    title_element = soup.find('h1', class_='b-singlepost-title')
    if not title_element:
        title_element = soup.find('h1', class_='aentry-post__title')
    if not title_element:
        title_element = soup.find('h1')

    post_content_element = soup.find('article', class_='b-singlepost-body')
    if not post_content_element:
        post_content_article = soup.find('article', class_='aentry-post') or soup.find('article')
        if post_content_article:
            post_content_element = post_content_article.find('div', class_='aentry-post__content') or post_content_article

    if not (date_content and post_content_element):
        print(f"Failed to extract content for {url}")
        return

    date_text = date_content.get('datetime') or date_content.get_text(strip=True)
    try:
        date_time = parse_date_time(date_text)
    except ValueError:
        print(f"Failed to extract date for {url}: {date_text}")
        return

    title = title_element.get_text(strip=True) if title_element else ''
    processed_html = preprocess_post_html(str(post_content_element), session, url)

    if output_mode == 'html':
        post_content = convert_html_to_html(processed_html, title, date_time, url)
    else:
        post_content = convert_html_to_markdown(processed_html)

    if not title and soup.title:
        title = soup.title.get_text(strip=True)

    if not title:
        title = post_content[:15]

    sanitized_filename = sanitize_title(title)
    extension = 'html' if output_mode == 'html' else 'md'
    filename = f"{date_time.split(' ')[0].replace('-', '_')}_{sanitized_filename}.{extension}"
    filepath = os.path.join(OUTPUT_DIR, filename)
    counter = 1
    while os.path.exists(filepath):
        filepath = os.path.join(OUTPUT_DIR, f"{date_time.split(' ')[0].replace('-', '_')}_{sanitized_filename}_{counter}.{extension}")
        counter += 1

    with open(filepath, 'w', encoding='utf-8') as f:
        if output_mode == 'html':
            safe_original_url = make_replica_url(url)
            f.write(post_content)
            f.write(f"\n<footer class='original-link'>\n  <p>Original post: <a href='{safe_original_url}'>{safe_original_url}</a></p>\n</footer>\n")
        else:
            safe_original_url = make_replica_url(url)
            f.write(f"# {title}\n\n")
            f.write(f"**{date_time}**\n\n")
            f.write(post_content)
            f.write(f"\n\n[Original Post]({safe_original_url})")

    set_file_creation_time(filepath, date_time)
    print(f"Archiving {filename}...")

if __name__ == "__main__":
    use_tor_input = input("Run this scrape anonymized over the Tor network? (y/n): ").strip().lower()
    use_tor = use_tor_input == 'y'
    tor_process = None
    tor_installed_by_script = False

    try:
        if use_tor:
            os_type = detect_os()
            if os_type == 'unsupported':
                print("[X] Tor support is unavailable on this platform.")
                sys.exit(1)

            if not is_tor_installed():
                install_tor_input = input("Tor is not installed. Install it now? (y/n): ").strip().lower()
                if install_tor_input == 'y':
                    print("[!] Installing Tor now...")
                    manage_tor('install', os_type)
                    tor_installed_by_script = True
                    time.sleep(3)

                    tor_path = get_tor_path()
                    if not tor_path:
                        raise FileNotFoundError('Tor executable could not be found after installation.')

                    tor_process = start_tor_daemon()
                    print("[*] Waiting for Tor to initialize...")
                    time.sleep(15)
                else:
                    proceed_without_tor = input(
                        "Tor installation declined. Run the program without Tor? "
                        "This will expose your IP to the target site and remove anonymization. (y/n): "
                    ).strip().lower()
                    if proceed_without_tor == 'y':
                        print("[!] Proceeding without Tor. Your IP and requests will be visible to the target server.")
                        use_tor = False
                    else:
                        print("[X] Aborting anonymized scrape.")
                        sys.exit(1)
            else:
                tor_path = get_tor_path()
                if not tor_path:
                    raise FileNotFoundError('Tor executable could not be found on your path.')

                tor_process = start_tor_daemon()
                print("[*] Waiting for Tor to initialize...")
                time.sleep(15)

        subdomain = input("Please enter the LiveJournal subdomain/username (e.g., 'john-doe'): ")
        session = get_session(use_tor=use_tor)

        # Optional: browser-rendered navigation for JS/WASM pages (Pyodide/JupyterLite)
        browser_mode = input("Enable browser-rendered navigation for Pyodide/JupyterLite pages? (y/n): ").strip().lower()
        if browser_mode == 'y':
            try:
                use_tb = input("If Tor is enabled, use the Tor Browser binary if available? (y/n): ").strip().lower() == 'y'
                tb_driver = start_selenium_firefox(use_tor=use_tor, use_tor_browser=use_tb)
                test_url = input("Enter WASM Python page URL to open (leave blank for demo): ").strip()
                if not test_url:
                    test_url = 'https://jupyterlite.github.io/demo/'
                print(f"[*] Opening {test_url} and attempting to run code in Pyodide...")
                sample_code = input("Enter Python code to run in the page (single-line recommended; leave blank for demo): ").strip()
                if not sample_code:
                    sample_code = "print('hello from pyodide')"
                result = navigate_to_pyodide(test_url, tb_driver, sample_code)
                print("[Pyodide result]", result)
            except Exception as e:
                print("[!] Browser-mode error:", e)
            finally:
                try:
                    tb_driver.quit()
                except Exception:
                    pass
        output_mode = input("Choose output style: markdown or html? (markdown/html) ").strip().lower()
        if output_mode not in ('markdown', 'html'):
            output_mode = 'markdown'

        links = get_all_permalinks(subdomain, session)
        links_without_comments = {link for link in links if "#comments" not in link}
        print(f"Found {len(links_without_comments)} posts, processing now...\n")
        for link in links_without_comments:
            extract_and_save_content(link, session, output_mode=output_mode)
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if tor_process:
            print("[*] Shutting down Tor daemon...")
            tor_process.terminate()
            tor_process.wait()

        if tor_installed_by_script or installed_packages_by_script:
            remove_installed = input(
                "All software installed for this session can be removed now. "
                "Would you like to uninstall Tor and cleanup session-installed Python packages? (y/n): "
            ).strip().lower()
            if remove_installed == 'y':
                if tor_installed_by_script:
                    print("[*] Cleaning up Tor installation...")
                    manage_tor('uninstall', os_type)
                if installed_packages_by_script:
                    print("[*] Uninstalling Python packages installed for this session...")
                    for pkg in installed_packages_by_script:
                        pip_uninstall(pkg)
                print("[✓] Session-installed software removed.")
            else:
                print("[!] Leaving session-installed software in place as requested.")

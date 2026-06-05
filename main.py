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
BASE_URL_TEMPLATE = "https://{}.livejournal.com/"
SKIP_PARAM = "?skip="
REQUEST_DELAY_RANGE = (1.5, 4.5)
TOR_PROXY = {'http': 'socks5h://127.0.0.1:9050', 'https': 'socks5h://127.0.0.1:9050'}

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

def get_random_headers(referer=None):
    headers = DEFAULT_HEADERS.copy()
    headers['User-Agent'] = random.choice(USER_AGENTS)
    if referer:
        headers['Referer'] = referer
    return headers


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
    """Converts HTML to Markdown."""
    soup = BeautifulSoup(html_content, 'html.parser')
    for tag in soup.find_all(['strong', 'b']):
        tag.replace_with(f"**{tag.get_text()}**")
    for tag in soup.find_all(['em', 'i']):
        tag.replace_with(f"*{tag.get_text()}*")
    for tag in soup.find_all('a', href=True):
        tag.replace_with(f"[{tag.get_text()}]({tag['href']})")
    for tag in soup.find_all('blockquote'):
        tag.replace_with(f"> {tag.get_text()}")
    for tag in soup.find_all('br'):
        tag.replace_with("\n")
    for ul_tag in soup.find_all('ul'):
        items = []
        for li_tag in ul_tag.find_all('li', recursive=False):
            items.append(f"- {li_tag.get_text()}")
            li_tag.extract()
        ul_tag.insert_before('\n'.join(items))
        ul_tag.unwrap()
    for ol_tag in soup.find_all('ol'):
        items = []
        for index, li_tag in enumerate(ol_tag.find_all('li', recursive=False), 1):
            items.append(f"{index}. {li_tag.get_text()}")
            li_tag.extract()
        ol_tag.insert_before('\n'.join(items))
        ol_tag.unwrap()
    for h_tag in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
        level = int(h_tag.name[1])
        h_tag.replace_with(f"{'#' * level} {h_tag.get_text()}")
    return soup.get_text()

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


def extract_and_save_content(url, session):
    """Extracts post details from a LiveJournal permalink and saves it as a markdown file."""
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

    post_content = convert_html_to_markdown(str(post_content_element))
    if title_element:
        title = title_element.get_text(strip=True)
    else:
        title = ''

    if not title and soup.title:
        title = soup.title.get_text(strip=True)

    if not title:
        title = post_content[:15]

    sanitized_filename = sanitize_title(title)
    filename = f"{date_time.split(' ')[0].replace('-', '_')}_{sanitized_filename}.md"
    filepath = os.path.join(OUTPUT_DIR, filename)
    counter = 1
    while os.path.exists(filepath):
        filepath = os.path.join(OUTPUT_DIR, f"{date_time.split(' ')[0].replace('-', '_')}_{sanitized_filename}_{counter}.md")
        counter += 1

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(f"# {title}\n\n")
        f.write(f"**{date_time}**\n\n")
        f.write(post_content)
        f.write(f"\n\n[Original Post]({url})")

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
        links = get_all_permalinks(subdomain, session)
        links_without_comments = {link for link in links if "#comments" not in link}
        print(f"Found {len(links_without_comments)} posts, processing now...\n")
        for link in links_without_comments:
            extract_and_save_content(link, session)
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

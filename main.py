import os
import re
import requests
from bs4 import BeautifulSoup
import datetime
import pywintypes
import win32file

# Configuration
OUTPUT_DIR = "./MD"
BASE_URL_TEMPLATE = "https://{}.livejournal.com/"
SKIP_PARAM = "?skip="

# Headers
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.63 Safari/537.36'
}

# Ensure the output directory exists
os.makedirs(OUTPUT_DIR, exist_ok=True)

def get_session():
    """Return a requests session with readability mode set."""
    SET_READABILITY_URL = "https://www.livejournal.com/tools/setstylemine.bml"
    READABILITY_DATA = {
        "Widget[StyleAlwaysMine]_readability": "on",
        "Widget[StyleAlwaysMine]_user": ""
    }
    
    session = requests.Session()
    response = session.post(SET_READABILITY_URL, data=READABILITY_DATA, headers=HEADERS)
    if response.status_code != 200:
        raise Exception("Failed to set readability mode.")
    return session

def get_all_permalinks(subdomain, session):
    """Fetch all post permalinks from a LiveJournal blog."""
    base_url = BASE_URL_TEMPLATE.format(subdomain)
    skip = 0
    all_permalinks = set()

    while True:
        response = session.get(base_url + SKIP_PARAM + str(skip), headers=HEADERS)
        
        if response.status_code != 200:
            print(f"Failed to fetch the page at skip={skip}")
            break

        soup = BeautifulSoup(response.content, 'html.parser')
        permalinks = {a['href'].split('?')[0] for a in soup.find_all('a', href=True) if '.livejournal.com' in a['href'] and '.html' in a['href'] and 'www.' not in a['href']}
        
        if not permalinks or permalinks.issubset(all_permalinks):
            break

        all_permalinks.update(permalinks)
        skip += 10

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
    return title[:50]

def set_file_creation_time(filename, date_time_str):
    """Updates the file's creation and modification time to reflect the original post's publish date and time."""
    date_time_obj = datetime.datetime.strptime(date_time_str, '%Y-%m-%d %H:%M:%S')
    epoch_start = datetime.datetime(1970, 1, 1)
    delta_seconds = int((date_time_obj - epoch_start).total_seconds())
    win_time = pywintypes.Time(delta_seconds)
    handle = win32file.CreateFile(filename, win32file.GENERIC_WRITE, 0, None, win32file.OPEN_EXISTING, 0, 0)
    win32file.SetFileTime(handle, win_time, win_time, win_time)
    handle.Close()

def extract_and_save_content(url, session):
    """Extracts post details from a LiveJournal permalink and saves it as a markdown file."""
    response = session.get(url, headers=HEADERS)
    if response.status_code != 200:
        print("Failed to fetch the page:", url)
        return
    soup = BeautifulSoup(response.content, 'html.parser')
    date_content = soup.find('time', class_='b-singlepost-author-date')
    title_element = soup.find('h1', class_='b-singlepost-title')
    post_content_element = soup.find('article', class_='b-singlepost-body')
    if not (date_content and post_content_element):
        print(f"Failed to extract content for {url}")
        return
    date_match = re.search(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", date_content.get_text())
    if not date_match:
        print(f"Failed to extract date for {url}")
        return
    date_time = date_match.group(1)
    post_content = convert_html_to_markdown(str(post_content_element))
    if title_element:
        title = title_element.get_text(strip=True)
    else:
        title = post_content[:15]
    sanitized_filename = sanitize_title(title)
    filename = f"{date_time.split(' ')[0].replace('-', '_')}_{sanitized_filename}.md"
    filepath = os.path.join(OUTPUT_DIR, filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(f"# {title}\n\n")
        f.write(f"**{date_time}**\n\n")
        f.write(post_content)
        f.write(f"\n\n[Original Post]({url})")
    set_file_creation_time(filepath, date_time)
    print(f"Archiving {filename}...")

if __name__ == "__main__":
    subdomain = input("Please enter the LiveJournal subdomain/username (e.g., 'john-doe'): ")
    try:
        session = get_session()
        links = get_all_permalinks(subdomain, session)
        links_without_comments = {link for link in links if "#comments" not in link}
        print(f"Found {len(links_without_comments)} posts, processing now...\n")
        for link in links_without_comments:
            extract_and_save_content(link, session)
    except Exception as e:
        print(f"Error: {e}")

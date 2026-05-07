import re
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS
from math import inf
import json

# region scratchbook
#
# 1. Data about URLs and words will be logged into a JSON file
# 2. Parse the json file with a separate script to obtain the following info
# when the crawler is done (frontier empty)
# 3. information needed:
#   * unique pages count
#   * longest page (in terms of word count)
#   * top 50 words
#   * total unique subdomains found (will be the same as total pages count since only host + path matter)
#   * list of subdomains alphabetically with count
#
# endregion

# region Constants
_ALLOWED_SUBDOMAINS = (
    ".ics.uci.edu",
    ".cs.uci.edu",
    ".informatics.uci.edu",
    ".stat.uci.edu",
)
_ALLOWED_SUBDOMAINS_BUT_NO_PERIOD_IN_THE_BEGINNING = (
    "ics.uci.edu",
    "cs.uci.edu",
    "informatics.uci.edu",
    "stat.uci.edu",
)
_DISALLOWED_QUERY_PARAMS = {
    "session",
    "sessionid",
    "sid",
    "phpsessid",
    "jsessionid",
    "action",
}
_CALENDAR_WORDS = {
    "year",
    "month",
    "day",
    "date",
    "calendar",
    "time",
    "week"
}
_DISALLOWED_PATHS = {
    "events",
    "calendar",
}
_ADDITIONAL_STOP_WORDS = {
    "nt",
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
    "https",
    "http",
    "com",
    "www",
    "login",
    "about",
    "search",
    "help",
    "copyright",
    "wiki",
    "sidebar",
    "navigation",
    "view",
    "history",
}
_NON_TEXT_TAGS = ["script", "style", "iframe", "noscript", "svg", "canvas", "head", "title", "meta"]
_PUNCTUATION_TO_STRIP = {'.', ',', '!', '?', '"'}

CALENDAR_WORD_LIMIT = 2
MAX_QUERY_PARAMS = 4
MAX_QUERY_LENGTH = 200
MAX_PATH_SEGMENTS = 15
MAX_URL_LENGTH = 1000
MAX_VISITS_PER_URL = 10000
#endregion


# region Global Variables
unique_urls_set = set()
largest_page = ("", 0) #tuple of (url, count)
unique_pages_set = set()
subdomain_counter = {}
# endregion

# region Helpers

def can_crawl(resp) -> bool:
    return resp.status == 200 and resp.raw_response and resp.raw_response.content

# just write into a json file for every valid url that we visit and process
# { url: string, core_url: string, num_words: int, words: list of words }
def log_data(url, resp):

    if not is_valid(url) or not can_crawl(resp):
        return

    core_url = get_formatted_url(url) #core_url is the host + path
    total_words, valid_word_count_dict = get_formatted_words(url, resp)

    with open("crawl_results.json", "a") as f:
        json = {
            "url": url,
            "core_url": core_url,
            "word_count": total_words,
            "words": valid_word_count_dict
        }
        json.dump(json, f)


def get_formatted_words(url, resp):
    soup = BeautifulSoup(resp.raw_response.content, "lxml")
        
    for tag in soup(_NON_TEXT_TAGS):
        tag.decompose()
    
    text = soup.get_text().lower()
    words = re.findall(r'[a-z]+', text)

    total_words = len(words)
    valid_word_count_dict = {}

    for w in words:
        if w not in ENGLISH_STOP_WORDS or w not in _ADDITIONAL_STOP_WORDS:
            valid_word_count_dict[w] = valid_word_count_dict.get(w, 0) + 1
        
    return total_words, valid_word_count_dict

def get_formatted_url(url):

    if not is_valid(url):
        return

    parsed = urlparse(url)
    host = parsed.hostname.lower()
    path = parsed.path or "/"
    if not path.endswith('/'):
        path = path + '/'
    full_page = host + path

    return full_page

def is_valid_page(url):
    core_url = get_formatted_url(url)
    times_visited = subdomain_counter.get(core_url, 0)
    if times_visited > MAX_VISITS_PER_URL:
        return False
    
    return True

def is_valid_host(host: str) -> bool:
    if not host:
        return False
    host = host.lower()
    if host in _ALLOWED_SUBDOMAINS_BUT_NO_PERIOD_IN_THE_BEGINNING:
        return True
    for subdomain in _ALLOWED_SUBDOMAINS:
        if host.endswith(subdomain):
            return True

    return False

def get_top_50_words():
    word_freq_tuples = list(word_freq.items())

    top_50 = sorted(word_freq_tuples, key=lambda x: x[1], reverse=True)[:50]
    return top_50

# endregion

# region main functions
def scraper(url, resp):
    # valid response -> get the url counted in subdomains
    log_data(url, resp)
    links = extract_next_links(url, resp)
    return [link for link in links if is_valid(link)]

def extract_next_links(url, resp):
    if not can_crawl(resp):
        return []

    soup = BeautifulSoup(resp.raw_response.content, "lxml")
    urls = []

    base_url = resp.url if resp.url else url
    for element in soup.find_all('a', href = True):
        raw_url = element.get('href')
        stripped_url = raw_url.strip()
        stripped_url_lowered = stripped_url.lower() 
        
        if (stripped_url_lowered == "" 
            or stripped_url_lowered[0] == "#"
            or stripped_url_lowered.startswith("tel:")
            or stripped_url_lowered.startswith("mailto:")
            or stripped_url_lowered.startswith("sms:")
            or stripped_url_lowered.startswith("javascript:")):
            continue
        
        full_url = urljoin(base_url, stripped_url)
        clean_url = full_url.split('#')[0] # defragmenting

        urls.append(clean_url)



    return urls

def is_valid(url):
    try:
        # length of url checking
        if len(url) > MAX_URL_LENGTH: 
            return False

        parsed = urlparse(url)

        # scheme checking

        if parsed.scheme not in set(["http", "https"]):
            return False

        # host checking. (must expand for traps later... for now just keep it to the
        # basic set of four urls)
        host = parsed.hostname
        
        if not is_valid_host(host):
            return False

        # path checking

        # checking for paths that repeat 3 times or more (like /about/about/about
        # or /about/people/about/people/about/...
        # checking for paths that are longer than 15 segments (just a rough number i chose)
        # also check path

        if any(bad_path in parsed.path.lower() for bad_path in _DISALLOWED_PATHS):
            return False

        path_segments = parsed.path.split('/')

        path_dict = {}
        for segment in path_segments:
            if segment == '':
                continue
            path_dict[segment] = path_dict.get(segment, 0) + 1
            if path_dict[segment] > 2:
                return False

        if len(path_segments) > MAX_PATH_SEGMENTS:
            return False

        # query checking

        # checking for query length being 4 or more (too long)
        # Repetitive Directories: URLs that repeat patterns, such as /folder/page/folder/page/, 
        # frequently signal a loop trap.Excessive Dynamic Parameters: Long, messy query strings 
        # or excessive session IDs (?sessionid=...) can generate unique URLs for identical content.
        # Infinite Calendar/Filtering: Dynamic calendars that allow navigation to the year 9999 
        # or complex filter combinations (e.g., size, color, price) on e-commerce sites often 
        # create endless crawl paths.Similar Content, Different URL: If multiple deep-path URLs 
        # return identical page content, it is likely a trap. (found online)
        # 
        # also block action= queries because it has unwanted effects like downloading

        # also check for query of long character lengths (one query param might be long)
        if len(parsed.query) > MAX_QUERY_LENGTH:
            return False 

        queries = parsed.query.split('&')
        if len(queries) > MAX_QUERY_PARAMS:
            return False
        cal_words = 0
        for query in queries:
            key = query.split("=", 1)[0].lower()
            if key in _DISALLOWED_QUERY_PARAMS:
                return False
            if key in _CALENDAR_WORDS:
                    # this is to prevent false positives based off
                    # only 1 calendar word such as year
                cal_words += 1
                if cal_words > CALENDAR_WORD_LIMIT: 
                    return False

        # blocks weird extensions taht arenbt websites
        
        if re.match(
            r".*\.(css|js|bmp|gif|jpe?g|ico"
            + r"|png|tiff?|mid|mp2|mp3|mp4"
            + r"|wav|avi|mov|mpeg|ram|m4v|mkv|ogg|ogv|pdf"
            + r"|ps|eps|tex|ppt|pptx|doc|docx|xls|xlsx|names"
            + r"|data|dat|exe|bz2|tar|msi|bin|7z|psd|dmg|iso"
            + r"|epub|dll|cnf|tgz|sha1"
            + r"|thmx|mso|arff|rtf|jar|csv"
            + r"|rm|smil|wmv|swf|wma|zip|rar|gz)$", parsed.path.lower()):
            return False
        
        return True

    except TypeError:
        print ("TypeError for ", parsed)
        raise

def make_report():
    with open("crawl_results.json") as f_cr:
        data = json.load(f_cr)

        with open("report.txt", "w") as f_r:
            ...

    pass
# endregion
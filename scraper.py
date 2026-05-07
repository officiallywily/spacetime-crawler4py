import re
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from spacy.lang.en.stop_words import STOP_WORDS as ENGLISH_STOP_WORDS
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
    "do",
    "idx",
    "image",
    "tab_files",
    "ns",
    "share",
    "sort",
    "orderby",
    "order",
    "view",
    "lang",
    "skin",
    "replyto",
    "print",
    "format"
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
    "login",
    "requesttracker",
    "dtr",
    "accounts",
    "services"
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
    "support",
    "username",
    "password",
    "support",
    "certification",
    "share",
    "spring",
    "summer",
    "fall",
    "winter",
    "autumn",
    "quarter"
}
_NON_TEXT_TAGS = ["script", "style", "iframe", "noscript", "svg", "canvas", "head", "title", "meta"]

CALENDAR_WORD_LIMIT = 2
MAX_QUERY_PARAMS = 4
MAX_QUERY_LENGTH = 200
MAX_PATH_SEGMENTS = 7
MAX_URL_LENGTH = 1000
MAX_VISITS_PER_PAGE = 5 # default to 200. testing with lower values to make crawler end faster
BUFFER_DUMP_SIZE = 2000 # default to 2000. testing with lower values to make crawler end faster
#endregion


# region Global Variables
unique_urls_set = set()
largest_page = ("", 0) #tuple of (url, count)
unique_pages_set = set()
visited_counter = {} # for trap avoiding
json_entry_buffer = [] # to limit io operations as much as possible
word_counter_buffer = {}
# endregion

# region Helpers

def can_crawl(resp) -> bool:
    return resp.status == 200 and resp.raw_response and resp.raw_response.content

# just write into a json file for every valid url that we visit and process
# { url: string, core_url: string, num_words: int, words: list of words }
# from https://www.geeksforgeeks.org/python/append-to-json-file-using-python/
def update_json():
    global json_entry_buffer
    try:
        with open("crawl_results.json", "x") as file:
            json.dump({"words_counter": {}, "url_info": [] }, file)
    except FileExistsError:
        pass
        
    with open("crawl_results.json", 'r+') as file:
        file_data = json.load(file)
        file_data["url_info"] = file_data.get("url_info", [])
        file_data["url_info"].extend(json_entry_buffer)
        file_data["words_counter"] = file_data.get("words_counter", {})
        file_data["words_counter"] = combine_counters(file_data["words_counter"], word_counter_buffer)
        file.seek(0)
        json.dump(file_data, file, indent=4)
        file.truncate() # to prevent extra bytes leftover

def combine_counters(counter1, counter2):
    for key, value in counter2.items():
        counter1[key] = counter1.get(key, 0) + value
    
    return counter1

def flush_buffer():
    if json_entry_buffer:
        update_json()
        json_entry_buffer.clear()
        word_counter_buffer.clear()


def log_data(url, resp):
    global json_entry_buffer
    global unique_pages_set

    if not is_valid(url) or not can_crawl(resp):
        return
    
    if url in unique_pages_set:
        return
    unique_pages_set.add(url)

    core_url = get_core_url(url) #core_url is the host + path
    if "wiki" in core_url: # wiki gets a bigger allowance since it's okay for wiki to have a lot of pages
        visited_counter[core_url] = visited_counter.get(core_url, 0) + 1
    else:
        visited_counter[core_url] = visited_counter.get(core_url, 0) + 2
        
    total_words = process_words(resp)
    json_entry = {
        "url": url,
        "core_url": core_url, # needed to count visited places and the count associated with them
        "word_count": total_words
    }
    json_entry_buffer.append(json_entry)

    if len(json_entry_buffer) > BUFFER_DUMP_SIZE:
        flush_buffer()

def process_words(resp):
    soup = BeautifulSoup(resp.raw_response.content, "lxml")
        
    for tag in soup(_NON_TEXT_TAGS):
        tag.decompose()
    
    text = soup.get_text().lower()
    words = re.findall(r'[a-z]+', text)

    total_words = len(words)

    # handling buffer
    for w in words:
        if (w not in ENGLISH_STOP_WORDS 
        and w not in _ADDITIONAL_STOP_WORDS 
        and len(w) > 1
        and not w.isdigit()):
            word_counter_buffer[w] = word_counter_buffer.get(w, 0) + 1
        
    return total_words

def get_core_url(url):

    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    path = parsed.path or "/"
    if not path.endswith('/'):
        path = path + '/'
    full_page = host + path

    return full_page

def visits_exceeded(url):
    core_url = get_core_url(url)
    times_visited = visited_counter.get(core_url, 0)
    return times_visited > MAX_VISITS_PER_PAGE

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

def get_top_50_words(words_counter):
    top_50_tuples = sorted(list(words_counter.items()), key=lambda x: x[1], reverse=True)[:50]
    return top_50_tuples

# endregion

# region main functions
def scraper(url, resp):
    if visits_exceeded(url):
        return []
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
        # Inside is_valid(url):
        if re.search(r"/\d{5,}/?$", parsed.path) or re.search(r":\d{5,}/?$", parsed.path):
            return False
            
        if any(bad_path in parsed.path.lower() for bad_path in _DISALLOWED_PATHS):
            return False

        path_segments = re.split(r'[:/]', parsed.path) 

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
    flush_buffer()


    with open("crawl_results.json") as file_cr:
        file_data = json.load(file_cr)
        top_50_words = get_top_50_words(file_data["words_counter"])
        # file_data["url_info"] is an array of entries
        largest_page = max(file_data["url_info"],  key=lambda x: x["word_count"])

        host_and_core_urls = {}
        for item in file_data["url_info"]:
            core_url = item["core_url"]
            host = core_url.split("/", 1)[0] # gets only the host
            host_and_core_urls[host] = host_and_core_urls.get(host, set())
            host_and_core_urls[host].add(core_url)

        with open("report.txt", "w") as file_report:
            file_report.write(f"Total pages visited: {len(file_data['url_info'])}\n\n")
            file_report.write(f"Longest page: {largest_page['url']},\t{largest_page['word_count']} words\n\n")

            file_report.write(f"Unique subdomains visited: {len(host_and_core_urls)}\n\n")
            file_report.write("List of subdomains and the amount of pages in them\n")
            for i, (host, core_urls) in enumerate(sorted(host_and_core_urls.items(), key=lambda x: x[0])):
                file_report.write(f"{i + 1}.\t{host}\n\thas {len(core_urls)} unique pages\n")
            file_report.write("\n\nTop 50 words\n")
            for i, (word, count) in enumerate(top_50_words):
                file_report.write(f"\t{i + 1}. {word}:\t{count}\n")

# endregion
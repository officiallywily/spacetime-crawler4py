import re
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

# logging... 
# total unique pages
#   use a set and add to the set on every VALID page visit WITHOUT FRAGMENT
# page with most words: keep track of 
#   "most_words_page" dictionary:
#   { url: FULL_URL (string) , word_count: (int) }
#   everytime we crawl a page, keep accumulate the number of words 
#   and chck against most_word_page.word_count value. 
#   update as needed
# 50 most common words found
#   use a hash table where keys are all the NON-STOP WORD words seen (lowercase)
#   and values are the count.
#   every single word the crawler sees will be accounted for
#   to sort:
#   convert hash table into a list of tuples [(word, count)]
#   run a sorting algorithm on the count
#   Get the top 50 words and their count
#
# number of subdomains and the amount of each listed alphabetically
#   treat http and https as the same subdomain.
#   treat www.example.com and example.com as different subdomains
#   treat example.com/ and example.com/?randomquery the same subdomain & page (ignore queries)
#   basically only keep subdomain + domain + path as unique page. Trim everything else
#   use hash table: {subdomain: subdomain + domain}
#   increment each subdomain each time it's visited
#   turn into list of tuples and sort by alphabetical order

# also need persistence on shutoff of crawler. Maybe I should program it to output 
# the data into a json file on shut off. load in from json file on start as long as 
# frontier is empty. if frontier is empty on start, i should wipe the logged file 

# data structures
unique_urls_set = set()
largest_page = ("", 0) #tuple of (url, count)
unique_pages_set = set()
subdomain_count = {}

# helpers
def can_crawl(resp) -> bool:
    return resp.status == 200 and resp.raw_response and resp.raw_response.content
def update_data(url, resp):
    if not is_valid(url) or not can_crawl(resp):
        return
    
    increment_subdomain_count(url)
    soup = BeautifulSoup(resp.raw_response.content, "lxml")
    process_page_words(url, soup)

def process_page_words(url, soup):
    pass
def increment_subdomain_count(url):
    parsed = urlparse(url)
    host = parsed.hostname
    path = parsed.path or ""
    full_page = host + path
    if full_page not in unique_pages_set:
        unique_pages_set.add(full_page)
        subdomain_count[host] = subdomain_count.get(host, 0) + 1
    










# constants
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

CALENDAR_WORD_LIMIT = 2
MAX_QUERY_PARAMS = 4
MAX_QUERY_LENGTH = 200
MAX_PATH_SEGMENTS = 15
MAX_URL_LENGTH = 1000

# helper functions

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


# https://www.iquanti.com/blog/guide-seo-spider-traps-causes-solutions/ helps a lot
# https://www.conductor.com/academy/crawler-traps/
# because i missed the testing due date, i am building the crawler a bit blind, and
# trying to make it very robust. adklsfjlkadsfjkldasjfkldasjfkladjslkfjaslkfjdslakjfdl

def scraper(url, resp):
    # valid response -> get the url counted in subdomains
    update_data(url, resp)
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

import re
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# https://www.iquanti.com/blog/guide-seo-spider-traps-causes-solutions/ helps a lot

def scraper(url, resp):
    links = extract_next_links(url, resp)
    return [link for link in links if is_valid(link)]

def extract_next_links(url, resp):
    if resp.status != 200:
        # probably will do more than just logging on console
        return []

    if not resp.raw_response.content:
        print(f"{resp.raw_response}")
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
        clean_url = full_url.split('#')[0]

        urls.append(clean_url)



    return urls

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
    "action"
}
MAX_QUERY_PARAMS = 4
MAX_QUERY_LENGTH = 200
MAX_PATH_SEGMENTS = 15
MAX_URL_LENGTH = 1000

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
        host = parsed.hostname.lower()
        
        if not is_valid_host(host):
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
        for query in queries:
            key = query.split("=", 1)[0].lower()
            if key in _DISALLOWED_QUERY_PARAMS:
                return False

        # path checking

        # checking for paths that repeat 3 times or more (like /about/about/about
        # or /about/people/about/people/about/...
        # checking for paths that are longer than 15 segments (just a rough number i chose)
        path_segments = parsed.path.split('/')

        path_dict = {}
        for segment in path_segments:
            path_dict[segment] = path_dict.get(segment, 0) + 1
            if path_dict[segment] > 2:
                return False

        if len(path_segments) > MAX_PATH_SEGMENTS:
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

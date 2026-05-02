import re
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from urllib.parse import urljoin

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
        parsed = urlparse(url)
        if parsed.scheme not in set(["http", "https"]):
            return False

        host = parsed.hostname
        
        if not is_valid_host(host):
            return False

        
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

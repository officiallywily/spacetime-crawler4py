import re
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from urllib.parse import urljoin

def scraper(url, resp):
    links = extract_next_links(url, resp)
    return [link for link in links if is_valid(link)]

def extract_next_links(url, resp):
    # Implementation required.
    # url: the URL that was used to get the page
    # resp.url: the actual url of the page
    # resp.status: the status code returned by the server. 200 is OK, you got the page. Other numbers mean that there was some kind of problem.
    # resp.error: when status is not 200, you can check the error here, if needed.
    # resp.raw_response: this is where the page actually is. More specifically, the raw_response has two parts:
    #         resp.raw_response.url: the url, again
    #         resp.raw_response.content: the content of the page!
    # Return a list with the hyperlinks (as strings) scrapped from resp.raw_response.content

    # pseudocode:
    # response validity tests
    # if the response is invalid (response code is not 200)
    #   get the error code and console log it for debugging
    #   return an empty list
    # otherwise proceed with the regular logic
    # get all the <a> tags (they have the links)
    # get the links from the <a> tags using soup.findall
    # get the findall and make a list of parsed urls, then return it
    if resp.status != 200:
        # probably will do more than just logging on console
        print(f"Status code: {resp.status}\nError message: {resp.error}")
        return list()
    
    soup = BeautifulSoup(resp.raw_response.content, "lxml")
    urls = []
    # go through all the a tags and extract only the urls
    # print(soup.find_all('a', href = True))
    for element in soup.find_all('a', href = True):
        # remove fragments
        # https://stackoverflow.com/questions/5815747/beautifulsoup-getting-href
        base_url = resp.url
        raw_url = element.get('href')
        stripped_url = raw_url.strip()
        
        if stripped_url == "" or stripped_url[0] == "#":
            continue
        
        full_url = urljoin(base_url, stripped_url)

        clean_url = stripped_url.split('#')[0]
        # need to make a full url now to cover for things like /about or ../about or about
        # probably need to handle edge cases
        # empty href
        # only a fragment in href
        # other links
        urls.append(clean_url)



    return urls

def is_valid(url):
    # Decide whether to crawl this url or not. 
    # If you decide to crawl it, return True; otherwise return False.
    # There are already some conditions that return False.
    try:
        parsed = urlparse(url)
        if parsed.scheme not in set(["http", "https"]):
            return False
        return not re.match(
            r".*\.(css|js|bmp|gif|jpe?g|ico"
            + r"|png|tiff?|mid|mp2|mp3|mp4"
            + r"|wav|avi|mov|mpeg|ram|m4v|mkv|ogg|ogv|pdf"
            + r"|ps|eps|tex|ppt|pptx|doc|docx|xls|xlsx|names"
            + r"|data|dat|exe|bz2|tar|msi|bin|7z|psd|dmg|iso"
            + r"|epub|dll|cnf|tgz|sha1"
            + r"|thmx|mso|arff|rtf|jar|csv"
            + r"|rm|smil|wmv|swf|wma|zip|rar|gz)$", parsed.path.lower())

    except TypeError:
        print ("TypeError for ", parsed)
        raise

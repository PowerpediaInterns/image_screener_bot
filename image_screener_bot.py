"""
Bot Goal:
 If the image description page is empty, tag it with {{di-no source no license}} and notify uploader
"""

import json
import requests
import urllib3
import pywikibot
import pdb

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

REV_PAGE = "Powerpedia:image_screen_REV"
PAGES_LIMIT = 2


def get_api_url() -> str:
    """
    Retrieves the API URL of the wiki

    :return: String of the path to the API URL of the wiki
    """

    site = pywikibot.Site()
    url = site.protocol() + "://" + site.hostname() + site.apipath()
    return url
def check_last_page() -> str:
    """
    Checks to see if REV_PAGE has any useful last page to start the script from
    If it does return that page as the last_page, and if not return an empty string.
    Need to query the wiki for page rev information.
    Using this: https://www.mediawiki.org/wiki/API:Revisions

    :param: none
    :return: page last modified. Stored at REV_PAGE on wiki.  returns empty string if
    no information is available at that page.
    """

    page = pywikibot.Page(pywikibot.Site(), title=REV_PAGE)

    #Check to make sure the revision page exists.  If it doesn't create a new empty page and return
    #an empty string.
    if not page.exists():
        print("Revision page \""+ REV_PAGE +"\" not found...  Adding")
        page.text = ""
        page.save()
        return ""

    if not page.get():
        print("No valid revision on this page found\n")
        return ""


    #Need to replace ' with " so json.loads() can properly change it from a string to a dict.
    page_text = page.get().replace('\'', '\"')
    page_contents = json.loads(page_text)

    if page_contents['title']:
        return page_contents['title']

    print("No valid revision page found\n")
    return ""

def get_revisions(page_title: str) -> list:
    """
    Gets the revision information from a page specifed by its page title.

    :param page_title: string of the page title to get the revisions of
    :return: list containing user, time, and title of last revision on
    this page.
    """

    session = requests.Session()
    params = {
        "action": "query",
        "prop": "revisions",
        "titles": page_title,
        "rvprop": "timestamp|user",
        "rvslots": "main",
        "formatversion": "2",
        "format": "json"
    }

    request = session.get(url=get_api_url(), params=params, verify=False)
    data = request.json()

    #Need to make sure key values 'query' and 'pages' are in the data dict.
    if not ('query' in data and 'pages' in data['query']):
        print("No valid page found...")
        return ""

    page = data['query']['pages'][0]

    #Checking for 'missing' or no 'revisions' if so that means nothing of value
    #is page and should just return ""
    if 'missing' in page or not 'revisions' in page:
        print("No revision information found for page " + page_title + "\n")
        return ""
    rev_info = page['revisions'][0]

    return {"user": rev_info['user'],
            "time": rev_info['timestamp'],
            "title": page_title}

def update_last_page(current_page: str) -> None:
    """
    Sets the page text of REV_PAGE to the latest revision information from current_page

    :param: current_page title of page to set revision information of
    :return: none
    """
    rev = get_revisions(current_page)
    page = pywikibot.Page(pywikibot.Site(), title=REV_PAGE)
    page.text = rev
    page.save()


def get_params(continue_from="") -> {}:
    """
    Gets the parameters dictionary to make the GET request to the wiki

    :param continue_from: String of page title to continue from; defaults to beginning of wiki
    :return: a dictionary of the parameters
    """
    return {
        "action": "query",
        "format": "json",
        "list": "allimages",
        "aifrom": continue_from,
        "ailimit": PAGES_LIMIT
    }


def get_image_info(img_title: str) -> dict:
    """
    Grabs the info of an image from the mediawiki api
    """
    params = {
    "action": "query",
    "format": "json",
    "prop": "imageinfo",
    "titles": img_title
    }

    session = requests.Session()
    request = session.get(url=get_api_url(), params=params, verify=False)
    image_info = request.json()

    if not ("query" in image_info and "pages" in image_info["query"]):
        print("Image info error...  Exiting")
        quit()
    last_key = next(iter(image_info['query']['pages']))
    return image_info['query']['pages'][last_key]

def notify(img_title: str, message: str) -> None:
    """
    Sends an email to the image uploader.
    """

    image_info = get_image_info(img_title)['imageinfo'][0]
    user = image_info['user']

    params = {
        "action": "query",
        "meta": "tokens",
        "format": "json"
    }
    session = requests.Session()
    request = session.get(url=get_api_url(), params=params, verify=False)
    data = request.json()
    email_token = data['query']['tokens']['csrftoken']


    email_params = {
        "action": "emailuser",
        "target": user,
        "subject": "POWERPEDIA IMAGE BOT",
        "token": email_token,
        "text": message,
        "format": "json"
    }

    request = session.post(url=get_api_url(), data=email_params)
    data = request.text

    print(data)



def check_page(image_title: str) -> None:
    """
    If the image description page is empty,
    tag it with {{di-no source no license}} and notify uploader
    """
    page = pywikibot.Page(pywikibot.Site(), title=image_title)
    message = """I am a robot that checks image uploads to the Powerpedia wiki.
    \n You did not add a description tag to image """ + image_title + """
    please fix this. Thank you :) """

    if not page.text:
        page.text = '{{di-no source no license}}'
        page.save()
        notify(image_title, message)

def modify_pages(url: str, last_title: str) -> None:
    """
    Retrieves a Page Generator with all old pages to be tagged

    :param url: String of the path to the API URL of the wiki
    :param last_title: String of the last title scanned
    :return: None
    """

    # Retrieving the JSON and extracting page titles
    session = requests.Session()
    request = session.get(url=url, params=get_params(last_title), verify=False)
    pages_json = request.json()

    if not ("query" in pages_json and "allimages" in pages_json["query"]):
        print("query error...  Exiting")
        return

    last_title = ""
    pages = pages_json["query"]["allimages"]
    for page in pages:
        print("Checking Image " + str(page['name']))
        check_page(page['title'])


        last_title = page["title"]


    if "continue" in pages_json:
        continue_from_title = last_title
        print("\nContinuing from:", continue_from_title, "next run.")
    else:
        continue_from_title = ""

    update_last_page(continue_from_title)


def main() -> None:
    """
    Driver. Iterates through the wiki and adds TEMPLATE where needed.
    """
    # Retrieving the wiki URL
    url = get_api_url()
    last_title = check_last_page()
    if last_title:
        print("last page found")
    else:
        print("No last page found")

    modify_pages(url, last_title)


    print("\nNo pages left to be tagged")


if __name__ == '__main__':
    pdb.run('main()')

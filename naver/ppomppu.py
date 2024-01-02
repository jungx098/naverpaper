import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

def find(base_url, visited_urls_file="visited_urls.txt"):
    # Read visited URLs from file
    try:
        with open(visited_urls_file, "r") as file:
            visited_urls = set(file.read().splitlines())
    except FileNotFoundError:
        visited_urls = set()

    # Send a request to the base URL
    response = requests.get(base_url)
    soup = BeautifulSoup(response.text, "html.parser")

    # Find all span elements with class 'list_subject' and get 'a' tags
    list_subject_links = soup.find_all('td', class_='list_vspace')

    naver_links = []
    for span in list_subject_links:
        a_tag = span.find("a", href=True)
        if a_tag and "네이버" in a_tag.text:
            naver_links.append(a_tag["href"])

    # Initialize a list to store campaign links
    campaign_links = []

    # Check each Naver link
    for link in naver_links:
        full_link = urljoin(base_url, link)

        if full_link in visited_urls:
            continue  # Skip already visited links

        res = requests.get(full_link)
        inner_soup = BeautifulSoup(res.text, "html.parser")

        # Find all links that start with the campaign URL
        for a_tag in inner_soup.find_all("a", href=True):
            campaign_link = a_tag.get_text().strip()

            if ('campaign2-api.naver.com' not in campaign_link and
                'ofw.adison.co'           not in campaign_link):
                continue

            if (campaign_link in campaign_links):
                continue

            campaign_links.append(campaign_link)

        # Add the visited link to the set
        visited_urls.add(full_link)

    # Save the updated visited URLs to the file
    with open(visited_urls_file, "w") as file:
        for url in visited_urls:
            file.write(url + "\n")

    return campaign_links

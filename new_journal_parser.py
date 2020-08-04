import sys
import json
import os
import os.path
import shutil
import time
from multiprocessing import Process, Queue

import requests
from bs4 import BeautifulSoup


def define_soup(url):
    """Defines soup object for given url and returns it"""
    header = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/61.0.3163.100 Safari/537.36'
    }
    response = requests.get(url, headers=header)
    soup = BeautifulSoup(response.text, 'html.parser')
    return soup


def extract_volume_links(request_link, path):
    """Extracts links to all volumes from response json"""
    domain = 'http://www.sciencedirect.com'
    header = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/61.0.3163.100 Safari/537.36'
    }
    response = requests.get(request_link, headers=header)
    json_string = response.text
    data = json.loads(json_string)
    data = data.get('data', {})

    results = {}
    for obj in data:
        volume_name = obj.get('volIssueSupplementText', '')
        link_to_volume = '{}/journal/{}{}'.format(domain, path, obj.get('uriLookup', ''))
        results.update({volume_name: link_to_volume})
    return results


def get_all_volumes(json_string):
    """Gets all volume links"""
    domain = 'http://www.sciencedirect.com'

    json_string = json.loads(json_string)  # I don't know why, but loads() returns str...
    json_data = json.loads(json_string)  # so that's why I'm doing this again

    path = json_data.get('titleMetadata', {}).get('title')  # journal url path-name

    data = json_data.get('issuesArchive', {}).get('data', {}).get('results', {})

    results = {}
    if not data:
        return results

    journal_id = data[0].get('firstIssue', {}).get('issn')

    for obj in data:
        year = str(obj.get('year', ''))
        request_link = '{}/journal/{}/year/{}/issues'.format(domain, journal_id, year)
        to_update = extract_volume_links(request_link, path)
        results.update(to_update)
    return results


def goto_all_issues(url):
    """Returns url to all issues from main journal page"""
    soup = define_soup(url)

    tag = soup.find('a', {'class': 'js-latest-issues-link-text'})

    domain = 'http://www.sciencedirect.com'
    link = tag.get('href')
    link_to_all_volumes = '{}{}'.format(domain, link)
    return link_to_all_volumes


def extract_json(url, is_soup=False):
    """
    Extracts json string from given url.
    If is_soup=True - extracts json string from given soup.
    """
    json_string = ''

    if is_soup:
        soup = url
    else:
        soup = define_soup(url)

    tag = soup.find('script', {'type': 'application/json'})

    if tag:
        json_string = tag.string

    return json_string


def get_journal_name(soup):
    """Gets journal name from given soup"""
    journal_name = soup.find('input', {'name': 'pub'}).get('value')
    return journal_name


def collect_urls_to_parse(urls, destination_queue):
    """Collects all urls to parse"""

    for url in urls:
        link_to_all_volumes = goto_all_issues(url)  # url to page that contain all issues
        soup = define_soup(link_to_all_volumes)
        journal_name = get_journal_name(soup).replace(':', '-')

        json_string = extract_json(soup, is_soup=True)
        volumes = get_all_volumes(json_string)  # gets urls to all volumes in journal

        destination_queue.put({
            journal_name: volumes
        })


def except_get_data(data):
    """Gets data for exception case"""
    for obj in data:  # complex json structure
        issue_sec = obj.get('issueSec', {})
        for issue in issue_sec:
            items = issue.get('includeItem', {})
            for item in items:
                authors = item.get('authors', {})
                for author in authors:
                    name = author.get('givenName')
                    surname = author.get('surname')
                    author_name = '{} {}'.format(name, surname)
                    emails = author.get('emails')
                    if emails:
                        yield {author_name: emails}


def alternative_get_data(data):
    """Tries alternative case to extract needed data"""
    for obj in data:  # complex json data structure
        if 'issueSec' in obj:
            yield except_get_data(data)
            return

        items = obj.get('includeItem', {})  # or obj.get('issueSec', {})

        for item in items:
            authors = item.get('authors')

            for author in authors:
                name = author.get('givenName')
                surname = author.get('surname')
                author_name = '{} {}'.format(name, surname)
                emails = author.get('emails')
                if emails:
                    yield {author_name: emails}


def parse_journal(url):
    """Parses given volume of journal"""
    json_string = extract_json(url)

    json_string = json.loads(json_string)
    json_data = json.loads(json_string)

    data = json_data.get('articles', {}).get('ihp', {}).get('data', {}).get('issueBody', {}).get('includeItem', [])

    if not data:
        data = json_data.get('articles', {}).get('ihp', {}).get('data', {}).get('issueBody', {}).get('issueSec', {})
        yield alternative_get_data(data)
        return

    for obj in data:  # complex json data structure
        authors = obj.get('authors')
        for obj2 in authors:
            name = obj2.get('givenName')
            surname = obj2.get('surname')
            author = '{} {}'.format(name, surname)
            emails = obj2.get('emails')
            if emails:
                yield {author: emails}


def write_results(source_queue):
    """Write results in file"""
    prev_journal = None
    current_file = None

    try:
        while True:
            data = source_queue.get()

            filename = '{}.txt'.format(data.get('journal_name'), 'not_found')
            authors = data.get('author', {})

            if prev_journal != filename:

                if current_file:
                    current_file.close()

                    shutil.move(
                        os.path.realpath(prev_journal),
                        os.path.realpath('Results/{}'.format(prev_journal))
                    )  # move result file in "Results" directory

                current_file = open(filename, 'w', encoding='utf-8')

            [(author, emails)] = authors.items()
            emails = ', '.join(emails)
            to_write = '{}; {}\n'.format(author, emails)  # writes csv-like file (.txt) to further import to excel

            current_file.write(to_write)

            prev_journal = filename

    except KeyboardInterrupt:
        current_file.close()

        shutil.move(
            os.path.realpath(prev_journal),
            os.path.realpath('Results/{}'.format(prev_journal))
        )


def parse_urls(source_queue, destination_queue):

    while True:
        [(journal_name, volumes)] = source_queue.get().items()

        print('Parsing "{}"'.format(journal_name))

        for volume_name, url in volumes.items():
            print('\t{}'.format(volume_name))
            for author in parse_journal(url):

                destination_queue.put({
                    'journal_name': journal_name,
                    'author': author
                })


def main():
    urls_from_file = sys.stdin.read().split()  # takes input
    urls_from_file = [url.strip() for url in urls_from_file]  # formatizing input

    if not os.path.exists('Results'):  # directory to save results files with authors and emails
        os.makedirs('Results')

    urls_to_parse_queue = Queue()
    data_to_write_queue = Queue()

    collect_urls_process = Process(target=collect_urls_to_parse, args=(urls_from_file, urls_to_parse_queue))
    parse_urls_process = Process(target=parse_urls, args=(urls_to_parse_queue, data_to_write_queue))
    write_to_file_process = Process(target=write_results, args=(data_to_write_queue,))

    print('Launching processes')

    collect_urls_process.start()
    parse_urls_process.start()
    write_to_file_process.start()

    collect_urls_process.join()
    parse_urls_process.join()
    write_to_file_process.join()


if __name__ == '__main__':
    t = time.time()

    print('Parsing new journals...')

    main()

    print('Done. Check nearby folder "Results" to see result.')
    print(time.time() - t)

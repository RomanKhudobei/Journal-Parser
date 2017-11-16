import sys
import json
import os
import os.path
import shutil
import time
import re
import multiprocessing as mp
from multiprocessing import Pool
from pprint import pprint

import requests
from bs4 import BeautifulSoup as BS


def define_soup(url):
    '''Defines soup object for given url and returns it'''
    header = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/61.0.3163.100 Safari/537.36'
    }
    response = requests.get(url, headers=header)
    soup = BS(response.text, 'html.parser')
    return soup

def extract_volume_links(request_link, path):
    '''Extracts links to all volumes from response json'''
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
        link_to_volume = obj.get('uriLookup', '')
        link_to_volume = '{}/journal/{}{}'.format(domain, path, link_to_volume)
        results.update({volume_name: link_to_volume})
    return results

def get_all_volumes(json_string):
    '''Gets all volume links'''
    domain = 'http://www.sciencedirect.com'
    
    json_string = json.loads(json_string)     # I don't know why, but loads() returns str...
    json_data = json.loads(json_string)       # so that's why I'm doing this again

    path = json_data.get('journalBanner', {}).get('title')      # journal url path-name

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
    '''Returns url to all issues from main journal page'''
    domain = 'http://www.sciencedirect.com'
    soup = define_soup(url)
    tag = soup.find('a', {'class': 'button-alternative js-latest-issues-link-text button-alternative-primary'})
    link = tag.get('href')
    link_to_all_volumes = '{}{}'.format(domain, link)
    return link_to_all_volumes

def extract_json(url, is_soup=False):
    '''
    Extracts json string from given url.
    If is_soup=True - extracts json string from given soup.
    '''
    if is_soup:
        soup = url
        tag = soup.find('script', {'type': 'application/json'})
    else:
        soup = define_soup(url)
        tag = soup.find('script', {'type': 'application/json'})
    if tag:
        json_string = tag.text
        return json_string
    return None

def get_journal_name(soup):
    '''Gets journal name from given soup'''
    journal_name = soup.find('input', {'name': 'pub'}).get('value')
    return journal_name

def collect_urls_to_parse(url):
    '''Collects all urls to parse'''
    urls_to_parse = {}

    link_to_all_volumes = goto_all_issues(url)      # url to page that contain all issues
    soup = define_soup(link_to_all_volumes)
    journal_name = get_journal_name(soup).replace(':', '-')
    
    json_string = extract_json(soup, is_soup=True)
    to_parse = get_all_volumes(json_string)     # gets urls to all volumes in journal

    urls_to_parse[journal_name] = to_parse
    return urls_to_parse

def collect_data(data):
    '''Collects data to single variable after Pool results'''
    results = {}
    for info in data:
        if info:
            results.update(info)
    return results

def except_get_data(data):
    '''Gets data for exception case'''
    results = {}
    for obj in data:    # complex json structure
        issue_sec = obj.get('issueSec', {})
        for obj2 in issue_sec:
            items = obj2.get('includeItem', {})
            for obj3 in items:
                authors = obj3.get('authors', {})
                for obj4 in authors:
                    name = obj4.get('givenName')
                    surname = obj4.get('surname')
                    author = '{} {}'.format(name, surname)
                    emails = obj4.get('emails')
                    if emails:
                        results[author] = emails
    return results

def alternative_get_data(data):
    '''Tries alternative case to extract needed data'''
    results = {}
    for obj in data:    # complex json data structure
        if 'issueSec' in obj:
            results = except_get_data(data)
            return results

        items = obj.get('includeItem', {}) #or obj.get('issueSec', {})

        for obj2 in items:
            authors = obj2.get('authors')

            for obj3 in authors:
                name = obj3.get('givenName')
                surname = obj3.get('surname')
                author = '{} {}'.format(name, surname)
                emails = obj3.get('emails')
                if emails:
                    results[author] = emails
    return results

def get_data(json_string):
    '''Gets data from json'''
    json_string = json.loads(json_string)
    json_data = json.loads(json_string)
    data = json_data.get('articles', {}).get('ihp', {}).get('data', {}).get('issueBody', {}).get('includeItem', [])

    if not data:
        data = json_data.get('articles', {}).get('ihp', {}).get('data', {}).get('issueBody', {}).get('issueSec', {})
        results = alternative_get_data(data)
        return results

    results = {}
    for obj in data:    # complex json data structure
        authors = obj.get('authors')
        for obj2 in authors:
            name = obj2.get('givenName')
            surname = obj2.get('surname')
            author = '{} {}'.format(name, surname)
            emails = obj2.get('emails')
            if emails:
                results[author] = emails
    return results

def parse_journal(volume_name, url):
    '''Parses given volume of journal'''
    print('Parsing {}'.format(volume_name))
    json_string = extract_json(url)
    data = get_data(json_string)
    return data

def write_results(filename, results):
    '''Write results in file'''
    with open(filename, 'w', encoding='utf-8') as file:
        for author, emails in results.items():
            emails = ', '.join(emails)
            to_write = '{}; {}\n'.format(author, emails)    # writes csv-like file (.txt) to further import to excel
            file.write(to_write)

def main():
    urls_from_file = sys.stdin.read().split()   # takes input
    urls_from_file = [url.strip() for url in urls_from_file]    # formatizing input

    if not os.path.exists('Results'):   # directory to save results files with authors and emails
        os.makedirs('Results')

    print('Collecting urls to parse...')

    with Pool() as pool:
        data = pool.map(collect_urls_to_parse, urls_from_file)

    urls_to_parse = collect_data(data)

    for journal_name, to_parse in urls_to_parse.items():
        print('Parsing {}'.format(journal_name))

        params = to_parse.items()
        with Pool() as pool:
            data = pool.starmap(parse_journal, params)

        results = collect_data(data)

        filename = '{}.txt'.format(journal_name)
        write_results(filename, results)

        source = os.path.realpath(filename)
        destination = os.path.realpath('Results/{}'.format(filename))
        shutil.move(source, destination)    # move result file in "Results" directory


if __name__ == '__main__':
    t = time.time()

    print('Parsing new journals...')

    main()

    print('Done. Check nearby folder "Results" to see result.')
    print(time.time() - t)
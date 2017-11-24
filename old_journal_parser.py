import sys
import json
import os
import os.path
import shutil
import time
import re
import multiprocessing as mp
from multiprocessing import Pool

import requests
from bs4 import BeautifulSoup as BS


def get_journal_name(soup):
    '''Gets journal name for given soup object'''
    tag = soup.find('span', {'class': 'pubTitle'})
    journal_name = tag.find('h1').text
    return journal_name

def define_soup(url):
    '''Defines soup object for given url and returns it'''
    header = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/61.0.3163.100 Safari/537.36'
    }

    try:
        response = requests.get(url, headers=header)
        soup = BS(response.text, 'html.parser')
    except:
        return None

    return soup

def get_article_links(soup):
    '''Gets all links to all articles for given soup object'''
    domain = 'http://www.sciencedirect.com'
    links = []
    a_tags = soup.find_all('a', {'class': 'cLink artTitle S_C_artTitle '})
    for tag in a_tags:
        link = '{}{}'.format(domain, tag.get('href', ''))
        links.append(link)
    return links

def extract_json(soup):
    '''Gets json string from given url'''
    tag = soup.find('script', {'type': 'application/json'})
    if tag == None:
        return None
    json_string = tag.text.replace('⁎', '')    # replacing in order to print it out
    return json_string

def alternative_extract_data(url):
    '''Extracts name and email in alternative way'''
    soup = define_soup(url)
    authors = soup.find_all('a', {'class': 'authorName svAuthor'})

    if authors == None:
        return None

    emails = soup.find_all('a', {'class': 'auth_mail'})
    result = {}     # {<author name>: <email>}
    for author, e_adress in zip(authors, emails):   # combine authors with their emails
        name = author['data-fn']
        name = name + author['data-ln']
        email = e_adress['href'].split(':')[1]  # "mailto:<email>" -> ['mailto', '<email>'] -> '<email>'
        result.update({name: email})
    return result

def extract_data_from_json(json_string):
    '''Extracts name and email from json string 
    and returns list containing name, surname, email accordinly'''
    data = json.loads(json_string)
    result = {}     # {<author name>: <email>}
    # complex data structure in json. Make some print cases, to figure out what's going on
    data = data.get('authors', [])
    data = data.get('content', [])
    for obj in data:    # complex json data structure
        for obj2 in obj.get('$$', []):
            author = ''
            email = ''
            for obj3 in obj2.get('$$', []):
                if obj3.get('#name', None) == 'given-name':
                    author = obj3.get('_')
                elif obj3.get('#name', None) == 'surname':
                    author = '{} {}'.format(author, obj3.get('_'))
                elif obj3.get('#name', None) == 'e-address':
                    email = obj3.get('_')
            if author and email:
                result.update({author: email})
    return result

def write_results(filename, results):
    '''
    Writes results in file
    Arguments:
        filename - journal name (recomend .txt)
        results - results list
    '''
    with open(filename, 'w', encoding='utf-8') as file:     # writes csv-like file (.txt) to further import to excel
        for author, email in results.items():
            file.write('{};'.format(author))
            file.write('{}\n'.format(email))

def get_volume_name(soup):
    '''Gets volume name'''
    return soup.find('span', {'aria-selected': 'true'}).text.strip()

def parse_journal(url):
    '''Parses all authors and their emails for given journal url'''
    domain = 'http://www.sciencedirect.com'
    soup = define_soup(url)

    journal_name = get_journal_name(soup).replace(':', ' -')   # because you can't write ":" in file name
    print('Parsing {}'.format(journal_name), end='\n')

    results = {}    # {<author name>: <email>}

    while soup:
        volume_header = soup.find('div', {'class': 'volumeHeader'}).text
        years = re.findall('[0-9]{4}', volume_header)
        if int(years[0]) < 2010:    # checking publication date
            print('Publication older than 2010 year, breaking...')
            break

        volume_name = get_volume_name(soup)
        print('Parsing {}'.format(volume_name)) 

        article_links = get_article_links(soup)     # links to all articles

        for link in article_links:
            article_soup = define_soup(link)

            json_string = extract_json(article_soup)

            if json_string == None:
                data = alternative_extract_data(link) 
            else:
                data = extract_data_from_json(json_string)

            if data:
                results.update(data)

        # previous because we iterating from last publication to first
        prev_vol = soup.find('a', {'title': 'Previous volume/issue'}).get('href', '')
        if prev_vol:
            soup = define_soup('{}{}'.format(domain, prev_vol))
        else:
            break
    
    filename = '{}.txt'.format(journal_name)
    write_results(filename, results)

    source = os.path.realpath(filename)
    destination = os.path.realpath('Results/{}'.format(filename))

    shutil.move(source, destination)    # move result file in "Results" directory


def main():
    urls_from_file = sys.stdin.read().split()   # takes input
    urls_from_file = [url.strip() for url in urls_from_file]    # formatizing input

    if not os.path.exists('Results'):   # directory to save results files with authors and emails
        os.makedirs('Results')

    with Pool() as pool:
        pool.map(parse_journal, urls_from_file)


if __name__ == "__main__":
    t = time.time()

    print('Parsing old journals...')

    main()

    print('Done. Check nearby folder "Results" to see result.')

    time_in_seconds = round(time.time() - t, 2)
    time_in_mins = round(time_in_seconds / 60, 2)

    print('total time: {} mins or {} seconds'.format(time_in_mins, time_in_seconds))

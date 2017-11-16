import subprocess
import re

import requests


def is_new_journal(url):
    '''Checks wether journal is new (UI)'''
    header = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/61.0.3163.100 Safari/537.36'
    }
    response = requests.get(url, headers=header)
    content = response.text
    is_new_journal = re.findall('Find out more', content)   # the criterion of old/new journal. unique to new journals
    if is_new_journal:
        return True
    return False

def main():
    print('Preparing...')
    with open('input.txt', 'r', encoding='utf-8') as file:  # takes input urls
        urls = file.readlines()
        urls = [url.strip() for url in urls]

    new_journals = []   # holds new journals
    old_journals = []   # holds old journals

    for url in urls:    # divide journals to according group
        if is_new_journal(url):
            new_journals.append(url)
        else:
            old_journals.append(url)

    new_journals = '\n'.join(new_journals)  # formatize stdin
    old_journals = '\n'.join(old_journals)  # formatize stdin

    if new_journals:
        new_journal_parser = subprocess.run(['python', 'new_journal_parser.py'], input=new_journals, encoding='utf-8')

    if old_journals:
        old_journal_parser = subprocess.run(['python', 'old_journal_parser.py'], input=old_journals, encoding='utf-8')


if __name__ == '__main__':
    main()
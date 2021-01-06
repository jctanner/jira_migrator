#!/usr/bin/env python

import json
import os
import random
import requests
import requests_cache
import time

import timeout_decorator
from logzero import logger
from pprint import pprint

from github import Github


def get_headers(token):
    return {
        'Authorization': f'token {token}',
        'User-Agent': 'Awesome Octocat-App'
    }


def main():

    token = os.environ.get('GITHUB_TOKEN')
    g = Github(token)

    with open('jira_tickets.json', 'r') as f:
        jtickets = json.loads(f.read())

    for jticket in jtickets:
        if not jticket.get('github_link'):
            continue
        pprint(jticket)

        reponame = '/'.join(jticket['github_link'].split('/')[3:5])
        number = int(jticket['github_link'].split('/')[-1])
        gurl = jticket['github_link']
        gurl = gurl.replace('github.com/', 'api.github.com/repos/')

        logger.info(gurl)
        rr = requests.get(gurl, headers=get_headers(token))
        idata = rr.json()
        if idata['state'] == 'closed':
            continue

        repo = g.get_repo(reponame)
        issue = repo.get_issue(number)
        issue.create_comment(f"migrated to {jticket['url']}")
        time.sleep(1)
        issue.edit(state='closed')
        #import epdb; epdb.st()
        time.sleep(2)



if __name__ == "__main__":
    main()

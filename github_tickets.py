#!/usr/bin/env python

import json
import os
import random
import requests
import requests_cache

import timeout_decorator
from logzero import logger


requests_cache.install_cache('.github_cache')


class GHCrawler(object):

    def __init__(self, tokens, dedupe=False):
        self.tokens = tokens


    @staticmethod
    def cleanlinks(links):
        linkmap = {}
        links = links.split(',')
        for idl, link in enumerate(links):
            parts = link.split(';')
            parts = [x.strip() for x in parts if x.strip()]
            parts[0] = parts[0].replace('<', '').replace('>', '')
            rel = parts[1].split('"')[1]
            linkmap[rel] = parts[0]
        return linkmap

    @timeout_decorator.timeout(5)
    def call_requests(self, url, headers):
        return requests.get(url, headers=headers)

    def _geturl(self, url, parent_url=None, since=None, conditional=True, follow=True):

        if since:
            _url = url + '?since=%s' % since
        else:
            _url = url

        token = random.choice(self.tokens)
        accepts = [
            'application/vnd.github.squirrel-girl-preview',
            'application/vnd.github.mockingbird-preview',
            'application/vnd.github.inertia-preview+json'
        ]
        headers = {
            'Authorization': 'token {}'.format(token),
            'User-Agent': 'Awesome Octocat-App',
            'Accept': ','.join(accepts)
        }
        logger.debug(headers)

        rr = None
        success = False
        errors = {
            'connection': 0,
            'timeout': 0
        }
        while not success:
            try:
                #rr = requests.get(_url, headers=headers)
                rr = self.call_requests(_url, headers)
            except requests.exceptions.ConnectionError:
                errors['connection'] += 1
                if errors['connection'] >= 10:
                    logging.error('too many connection errors for this request')
                    raise GithubConnectionThrottling(_url)
                logging.warning('sleeping {}s due to connection error'.format(60*2))
                time.sleep(60*2)
                continue
            except timeout_decorator.timeout_decorator.TimeoutError:
                errors['timeout'] += 1
                if errors['timeout'] >= 10:
                    logging.error('too many timeout errors for this request')
                    raise GithubConnectionThrottling(_url)
                logging.warning('sleeping {}s due to timeout'.format(60*2))
                time.sleep(60*2)
                continue

            # some things just can't be fetched for whatever reason
            #   /repos/ansible/ansible/pulls/27184/files
            if rr.status_code == 422 or rr.reason == 'Unprocessable Entity':
                success = False
                break

            if rr.status_code < 400:
                success = True
                break
            if rr.status_code == 404:
                # a missing issue
                success = True
                break

            if rr.status_code == 401:

                #if 'bad credentials' in jdata.get('message', '').lower():
                #    import epdb; epdb.st()

                success = False
                break

            jdata = {}
            try:
                jdata = rr.json()
            except Exception as e:
                logging.error(e)
                import epdb; epdb.st()

            if 'api rate limit exceeded' in jdata.get('message', '').lower():
                if 'X-RateLimit-Reset' in rr.headers:
                    rt = float(rr.headers['X-RateLimit-Reset']) - time.time()
                    rt += 5

                    # cap it at one hour
                    if rt > (60 * 60):
                        rt = (60 * 65)

                    logging.warning('{}'.format(jdata.get('message')))
                    logging.warning('sleeping {}s due to rate limiting'.format(rt))
                    time.sleep(rt)
                    continue

            #elif 'bad credentials' in jdata.get('message', '').lower():
            #    import epdb; epdb.st()


        logger.debug('{} {}'.format(_url, rr.status_code))

        if rr.status_code == 304:
            data = None
        else:
            data = rr.json()
            # don't forget to set your tokens kids.
            if isinstance(data, dict):
                if data.get('message', '').lower() == 'bad credentials':
                    #import epdb; epdb.st()
                    pass

        fetched = []
        if 'Link' in rr.headers and follow:
            links = GHCrawler.cleanlinks(rr.headers['Link'])
            while 'next' in links:
                logger.debug(links['next'])
                if links['next'] == _url:
                    break

                if links['next'] in fetched:
                    break

                nrr, ndata = self._geturl(links['next'], parent_url=_url, conditional=conditional, follow=False)
                fetched.append(links['next'])
                if ndata:
                    data += ndata
                if 'Link' in nrr.headers:
                    links = GHCrawler.cleanlinks(nrr.headers['Link'])
                else:
                    links = {}

        #import epdb; epdb.st()
        return (rr, data)


def main():

    data_dir = 'data'
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)

    ghc = GHCrawler(tokens=[os.environ.get('GITHUB_TOKEN')])
    #(rr, data) = ghc._geturl('https://api.github.com/repos/RedHatInsights/tower-analytics-backend')

    (irr, idata) = ghc._geturl('https://api.github.com/repos/RedHatInsights/tower-analytics-backend/issues')
    for issue in idata:
        print(issue['number'])
        fn = os.path.join(data_dir, f"aa_be_{issue['number']}_issue.json")
        with open(fn, 'w') as f:
            f.write(json.dumps(issue))

        (crr, cdata) = ghc._geturl(issue['comments_url'])
        cfn = os.path.join(data_dir, f"aa_be_{issue['number']}_comments.json")
        with open(cfn, 'w') as f:
            f.write(json.dumps(cdata))

    (irr, idata) = ghc._geturl('https://api.github.com/repos/RedHatInsights/tower-analytics-frontend/issues')
    for issue in idata:
        print(issue['number'])
        fn = os.path.join(data_dir, f"aa_fe_{issue['number']}_issue.json")
        with open(fn, 'w') as f:
            f.write(json.dumps(issue))

        (crr, cdata) = ghc._geturl(issue['comments_url'])
        cfn = os.path.join(data_dir, f"aa_fe_{issue['number']}_comments.json")
        with open(cfn, 'w') as f:
            f.write(json.dumps(cdata))



if __name__ == "__main__":
    main()
#!/usr/bin/env python

"""
jira_tickets.py - idempotently copy the issue data from github_tickets.py to issues.redhat.com

The jira instance on issues.redhat.com does have an api, but it's shielded by sso and regular users
can not generate tokens nor do advanced data import. This script works around all of that by using
selenium to navigate through the pages and to input the data.
"""

import copy
import glob
import json
import os
import time

from logzero import logger
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains


def highlight(driver, element):
    """Highlights (blinks) a Selenium Webdriver element"""
    driver = element._parent
    def apply_style(s):
        driver.execute_script("arguments[0].setAttribute('style', arguments[1]);",
                              element, s)
    original_style = element.get_attribute('style')
    apply_style("border: 2px solid red;")
    time.sleep(3)
    apply_style(original_style)


'''
element = driver.find_element_by_class_name('classname')
driver.execute_script("""
var element = arguments[0];
element.parentNode.removeChild(element);
""", element)
'''
def delete_element(driver, element):
    driver.execute_script("""
var element = arguments[0];
element.parentNode.removeChild(element);
""", element)


def fill_text(driver, tag, tinput):
    driver.execute_script(f"""
document.getElementsByTagName({tag}).value = "100";
""", element)


class JiraWrapper:
    chrome_driver = os.path.abspath('./chromedriver')
    gecko_driver = os.path.abspath('./geckodriver')
    iurl = 'https://issues.redhat.com/projects/AA/issues/AA-1?filter=allopenissues'
    github_issues = None
    jira_issues = None
    imap = None

    private_repos = {
        'https://api.github.com/repos/RedHatInsights/tower-analytics-backend': True,
        'https://api.github.com/repos/RedHatInsights/tower-analytics-frontend': False
    }

    def __init__(self, url, username, password):

        if not username or not password:
            raise Exception('The username and password must be set!')

        self.url = url
        self.username = username
        self.password = password
        self.driver = None

        self.load_imap()
        self.load_github_data()

        self.connect()
        self.scrape_jira_issues()
        #self.jira_issues = []
        #self.create_test_issue()
        self.create_issues()

    def load_imap(self):
        fn = '.jiramap.json'
        if os.path.exists(fn):
            with open(fn, 'r') as f:
                self.imap = json.loads(f.read())
    
    def save_imap(self):
        fn = '.jiramap.json'
        with open(fn, 'w') as f:
            f.write(json.dumps(self.imap))

    def load_github_data(self):

        self.github_issues = []

        ddir = os.path.abspath('./data')
        ifiles = glob.glob(f"{ddir}/RedHatInsights/tower-analytics-*/*_issue.json")

        ikeys = []
        for ifile in ifiles:
            with open(ifile, 'r') as f:
                idata = json.loads(f.read())
            labels = [x['name'] for x in idata['labels']]
            if 'JIRA' not in labels:
                continue
            
            ikey = [idata['created_at'], idata['repository_url'], idata['number'], ifile]
            ikeys .append(ikey)

        ikeys = sorted(ikeys, key=lambda x: x[0])
        self.github_issues = ikeys[:]


    def connect(self):

        logger.info('open page ...')
        #self.driver = webdriver.Chrome(self.chrome_driver)
        #profile = webdriver.FirefoxProfile()
        #profile.set_preference("devtools.jsonview.enabled", False)
        options = webdriver.FirefoxOptions()
        options.set_preference("devtools.jsonview.enabled", False)
        self.driver = webdriver.Firefox(executable_path=self.gecko_driver, options=options)
        self.driver.get(self.url)

        # click login
        logger.info('click login ...')
        login_url = self.driver.find_element_by_class_name('login-link')
        login_url.click()
        #time.sleep(5)

        # enter username
        logger.info('enter username ...')
        self.wait_for_element(id='username')
        un = self.driver.find_element_by_id('username')
        un.send_keys(self.username)

        # next button
        logger.info('click next ...')
        nextb = self.driver.find_element_by_id('login-show-step2')
        nextb.click()

        # enter password
        logger.info('enter password ...')
        self.wait_for_element(id='password')
        pw = self.driver.find_element_by_id('password')
        pw.send_keys(self.password)

        # click login
        logger.info('click login ...')
        self.wait_for_element(id='kc-login')
        loginb = self.driver.find_element_by_id('kc-login')
        loginb.click()
        time.sleep(5)

        # go back to issues page
        logger.info('go back to url ...')
        self.driver.get(self.url)

        # click login (again)
        if self.check_element(classname='login-link'):
            logger.info('click login again ...')
            login_url = self.driver.find_element_by_class_name('login-link')
            login_url.click()
            time.sleep(5)

        #import epdb; epdb.st()


    def scrape_jira_issues(self, github_issue_to_find=None):

        def _scrape():
            self.jira_issues = []
            self.driver.get('https://issues.redhat.com/rest/api/2/search?jql=project=AA&maxResults=1000')
            data = self.driver.find_element_by_tag_name('pre').text
            jdata = json.loads(data)
            issues = jdata['issues']

            for ji in issues:
                idata = {
                    'number': ji['key'],
                    'url': 'https://issues.redhat.com/projects/AA/issues/' + ji['key'],
                    'description': ji['fields']['description'] or ''
                }
                self.jira_issues.append(idata)

        _scrape()
        if github_issue_to_find:
            matches = [x for x in self.jira_issues if github_issue_to_find in x]
            while not matches:
                logger.info(f'waiting for {github_issue_to_find} to appaer')
                _scrape()
                matches = [x for x in self.jira_issues if github_issue_to_find in x['description']]
                if not matches:
                    time.sleep(2)

        logger.info('opening ' + self.iurl)
        self.driver.get(self.iurl)
        self.wait_for_element(classname="simple-issue-list")

    def create_issues(self):
        logger.info('opening ' + self.iurl)
        self.driver.get(self.iurl)
        self.wait_for_element(classname="simple-issue-list")

        total = 0
        for gi in self.github_issues:

            logger.info(gi)
            with open(gi[-1], 'r') as f:
                idata = json.loads(f.read())

            lnames = [x['name'].lower() for x in idata['labels']]

            #if idata['number'] == 109:
            #    import epdb; epdb.st()

            if 'jira' not in lnames:
                continue
            #if 'epic' not in lnames:
            #    continue
            
            #if 'feature' not in lnames and 'enhanceement' not in lnames:
            #    continue

            total += 1
            if total >= 5:
                break

            itype = 'Bug'
            if 'epic' in lnames:
                itype = 'Epic'
            elif 'feature' in lnames or 'enhancement' in lnames:
                itype = 'Feature'
            
            matches = [x for x in self.jira_issues if idata['html_url'] in x['description']]
            if not matches:
                self.create_issue(idata, itype=itype, private=self.private_repos.get(idata['repository_url']))
                self.scrape_jira_issues(github_issue_to_find=idata['html_url'])
                #matches = [x for x in self.jira_issues if idata['html_url'] in x['description']]
                #import epdb; epdb.st()
                #assert matches, "The newly created issue was not found"
                matches = [x for x in self.jira_issues if idata['html_url'] in x['description']]
                assert matches, "The newly created issue was not found"
            
            cfile = gi[-1].replace('_issue', '_comments')
            with open(cfile, 'r') as f:
                cdata = json.loads(f.read())
            if cdata:
                self.create_comments(matches[0], cdata, private=self.private_repos.get(idata['repository_url']))
            
            #import epdb; epdb.st()

    def create_issue(self, issue_data, private=False, itype='Bug'):
        self.driver.get(self.iurl)
        self.wait_for_element(classname="simple-issue-list")

        # find and click the new issue button ...
        logger.info('click new issue')
        new_button = None
        buttons = self.driver.find_elements_by_tag_name('button')
        for button in buttons:
            if 'Create issue' in button.text:
                new_button = button
                break
        new_button.click()

        # open the full modal ..
        logger.info('opening full create modal ...')
        expand_button = None
        buttons = self.driver.find_elements_by_tag_name('button')
        for button in buttons:
            if 'More' in button.text:
                expand_button = button
                break
        if expand_button:
            expand_button.click()
        
        # find description box and fill it in ...
        logger.info('wait for modal ...')
        new_description = issue_data['html_url'] + '\n\n' + issue_data['body']
        self.wait_for_element(classname='description-wiki-edit')

        logger.info('brute force filling in the description ...')
        count = 0
        while True:
            '''
            try:
                highlight(self.driver, self.driver.find_element_by_id('description-wiki-edit'))
                highlight(self.driver, self.driver.find_element_by_id('description-wiki-edit').find_element_by_tag_name('textarea'))
            except Exception as e:
                logger.error(str(e))
            '''

            try:
                delete_element(self.driver, self.driver.find_element_by_class_name('rte-container'))
                ta = self.driver.find_element_by_id('description-wiki-edit').find_element_by_tag_name('textarea')
                hover = ActionChains(self.driver).move_to_element(ta)
                ta.click()
                self.driver.find_element_by_id('description-wiki-edit').find_element_by_tag_name('textarea').send_keys(new_description)
                break
            except Exception as e:
                logger.error(str(e))

            count += 1
            if count >= 5:
                break
            time.sleep(count)

        # set the issue type ...
        logger.info('set the issue type')
        self.wait_for_element(id='issuetype-single-select')
        for x in range(0, 10):
            self.driver.find_element_by_id('issuetype-single-select').find_element_by_tag_name('input').send_keys(Keys.BACKSPACE)
        self.driver.find_element_by_id('issuetype-single-select').find_element_by_tag_name('input').send_keys(itype)
        self.driver.find_element_by_id('issuetype-single-select').find_element_by_tag_name('input').send_keys(Keys.TAB)
        #time.sleep(2)
        time.sleep(1)

        # set the security level ...
        if private:
            logger.info('set security level')
            sselect = self.driver.find_element_by_id('security')
            sopts = self.driver.find_elements_by_tag_name('option')
            for sopt in sopts:
                if 'Red Hat Internal' in sopt.text:
                    sopt.click()
                    break
            #time.sleep(2)
            time.sleep(1)
        
        # set the component ...
        logger.info('set components')
        cdiv = self.driver.find_element_by_id('components-multi-select')
        for x in range(0, 10):
            cdiv.find_element_by_tag_name('textarea').send_keys(Keys.BACKSPACE)
        if 'backend' in issue_data['url']:
            cdiv.find_element_by_tag_name('textarea').send_keys('API')
        elif 'frontend' in issue_data['url']:
            cdiv.find_element_by_tag_name('textarea').send_keys('UI')
        cdiv.find_element_by_tag_name('textarea').send_keys(Keys.TAB)
        #time.sleep(5)
        time.sleep(1)
        
        # set the summary/title
        new_summary = issue_data['title']
        if 'backend' in issue_data['url']:
            new_summary = 'API-' + str(issue_data['number']) + ': ' + new_summary
        elif 'frontend' in issue_data['url']:
            new_summary = 'UI-' + str(issue_data['number']) + ': ' + new_summary
  
        logger.info('fill in summary')
        self.driver.find_element_by_id('summary').send_keys(new_summary)
        if itype == 'Epic':
            logger.info('fill in epic name')
            field_groups = self.driver.find_elements_by_class_name('field-group')
            field_groups = [x for x in field_groups if 'Epic Name' in x.text]
            epic_field = field_groups[0]
            #epic_field.send_keys(new_summary)
            epic_field.find_element_by_tag_name('input').send_keys(new_summary)

        #import epdb; epdb.st()
        logger.info('click create')
        try:
            self.driver.find_element_by_id('create-issue-submit').click()
        except Exception as e:
            logger.error(str(e))

        #import epdb; epdb.st()


    def create_comments(self, ticket, cdata, private=False):
        # open the issue ..
        # iurl = 'https://issues.redhat.com/projects/AA/issues/AA-1?filter=allopenissues'
        self.driver.get(ticket['url'])
        time.sleep(2)

        for cd in cdata:

            # check if comment alreadyt exists ...
            cblocks = self.driver.find_elements_by_class_name('activity-comment')
            bodies = [x.text for x in cblocks]
            bmatches = [x for x in bodies if cd['html_url'] in x]
            if bmatches:
                continue

            logger.info('adding comment ' + cd['html_url'])
            #import epdb; epdb.st()

            body = cd['html_url'] + '\n'
            body +=  cd['created_at'] + ' by ' + '@' + cd['user']['login'] + '\n\n'
            body += cd['body']
            
            logger.info('click new comment button ...')
            #self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

            # scroll ...
            panel = self.driver.find_element_by_class_name('detail-panel')
            self.driver.execute_script("arguments[0].scrollTo(0, 100000);", panel)
            time.sleep(1)

            try:
                self.driver.find_element_by_id('footer-comment-button').click()
            except Exception as e:
                logger.error(str(e))
                import epdb; epdb.st()
            
            # scroll ...
            panel = self.driver.find_element_by_class_name('detail-panel')
            self.driver.execute_script("arguments[0].scrollTo(0, 100000);", panel)                
            time.sleep(1)

            logger.info('fill in commment body ...')
            self.wait_for_element(id='comment-wiki-edit')

            try:
                self.driver.find_element_by_id('comment-wiki-edit').find_element_by_id('mce_0_ifr').click()
                self.driver.find_element_by_id('comment-wiki-edit').find_element_by_id('mce_0_ifr').send_keys(body)
            except Exception as e:
                logger.error(e)
                import epdb; epdb.st()

            # change the visibility ...
            if private:
                logger.info('expand security options ...')
                self.driver.find_element_by_class_name('security-level').find_element_by_id('commentLevel-multi-select').click()
                logger.info('click redhat ...')
                #self.driver.find_element_by_class_name('aui-list-item-li-red-hat-employee').click()
                #self.driver.find_element_by_class_name('security-level').find_element_by_class_name('aui-list-item-li-red-hat-employee').click()
                self.driver.find_element_by_class_name('aui-list-scroll').send_keys(Keys.DOWN * 6)
                self.driver.find_element_by_class_name('aui-list-scroll').send_keys(Keys.ENTER)
                time.sleep(1)

            # click "add"
            try:
                self.driver.find_element_by_id('issue-comment-add-submit').click()
            except Exception as e:
                logger.error(str(e))
                import epdb; epdb.st()

        #import epdb; epdb.st()

    def check_element(self, id=None, classname=None, selector=None):
        try:
            if id:
                self.driver.get_element_by_id(id)
            elif classname:
                self.driver.get_element_by_class_name(classname)
            elif selector:
                pass
            return True
        except Exception as e:
            pass
        return False


    def wait_for_element(self, id=None, classname=None, selector=None):
        count = 0
        while True:
            count += 1
            logger.info(f'poll for {id} {count} ...')
            try:
                if id:
                    self.driver.get_element_by_id(id)
                elif classname:
                    self.driver.get_element_by_class_name(classname)
                elif selector:
                    pass
            except Exception as e:
                time.sleep(2)
            break




def main():
    jw = JiraWrapper('https://issues.redhat.com', os.environ.get('JIRA_USERNAME'), os.environ.get('JIRA_PASSWORD'))


if __name__ == "__main__":
    main()

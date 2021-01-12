# ISSUE MIGRATOR

Migrate issues from github to issues.redhat.com via selenium

# HOW IT WORKS

There are multiple scripts in this repo that are expected to be run in a specific order as outlined in the instructions.

Before running these scripts, add a "jira" label to any github issue you wish to migrate.

The first phase is to fetch all the github api data for the issues in a project or a set of projects. The second phase is 
to examine the current issues in an issues.redhat.com jira project. For each issue, if the first line of the description
relates to the url for a github issue, it is -assumed- those two are linked. For any unlinked github issues, a new jira
ticket will be created along with all the relevant comments. The third phase is to close all the migrated github issues.

The scripts are idempotent and can be run multiple times to keep data in sync if any new issues are marked for migration.


# INSTRUCTIONS

1. make sure firefox is installed
2. checkout the repo
3. virtualenv venv
4. source venv/bin/activate
5. pip install -r requirements.txt
6. export GITHUB_TOKEN=<YOUR_TOKEN>
7. export JIRA_USERNAME=<YOUR_USERNAME>
8. export JIRA_PASSWORD=<YOUR_PASSWORD>
9. python github_tickets.py
10. python map_logins.py
11. vim data/github/login_map.json
12. python jira_tickets.py
13. python github_ticket_close.py

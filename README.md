# ISSUE MIGRATOR

Migrate issues from github to issues.redhat.com via selenium

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

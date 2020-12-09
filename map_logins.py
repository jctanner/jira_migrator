#!/usr/bin/env python

import json
import glob
import os


def main():

    lmap = {}
    dfn = 'login_map.json'
    if os.path.exists(dfn):
        with open(dfn, 'r') as f:
            lmap = json.loads(f.read())

    issue_fns = glob.glob('data/*/*/*_issue.json')
    issue_fs = sorted(issue_fns)

    logins = set()

    for ifn in issue_fns:
        with open(ifn, 'r') as f:
            idata = json.loads(f.read())
        logins.add(idata['user']['login'])
    
    newlmap = dict(zip(logins, [""] * len(list(logins))))
    for k,v in newlmap.items():
        if k not in lmap:
            lmap[k] = v
    
    with open(dfn, 'w') as f:
        f.write(json.dumps(lmap, indent=2))

    #import epdb; epdb.st()


if __name__ == "__main__":
    main()
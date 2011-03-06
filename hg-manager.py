#!/usr/bin/env python

"""Module hg-manager
(c) 2011 Abhishek Kulkarni

Hg Repository Manager

Replacement for htpasswd
http://trac.edgewall.org/browser/trunk/contrib/htpasswd.py
# Original author: Eli Carter

"""
import os
import sys
import ConfigParser
import random
import string
import smtplib
from argparse import ArgumentParser
from email.mime.text import MIMEText

# We need a crypt module, but Windows doesn't have one by default.  Try to find
# one, and tell the user if we can't.
try:
    import crypt
except ImportError:
    try:
        import fcrypt as crypt
    except ImportError:
        sys.stderr.write("Cannot find a crypt module.  "
                         "Possibly http://carey.geek.nz/code/python-fcrypt/\n")
        sys.exit(1)

try:
    from hashlib import md5
except ImportError:
    from md5 import md5

#
# Global Configuration
#

# Default path to the hgweb configuration file
default_config_file = 'hgweb.config'

# Default path to the users file (containing a list of users)
default_users_file = '.htdigest'

# hg-gateway version
hg_version = '0.3'

# HTTPS URL to your repository manager
repo_http_url = 'https://garkbit.osl.iu.edu/hg'

# SSH URL to your repository manager
repo_ssh_url = 'ssh://hg@garkbit.osl.iu.edu'

repo_maintainer = 'adkulkar@garkbit.osl.iu.edu'

# Any additional notice related to your repository manager
# that you would like to include in the notification emails
# sent out by your repository manager"
repo_usage = """
------------------------------------------------------------------------------
A short guide to using the Garkbit Repositories.
------------------------------------------------------------------------------

There are basically two ways to access your repositories on the
Garkbit server:

1. Using password-based authentication over HTTPS

You have been already registered for this method of repository access.
You will have to enter your login credentials for any Mercurial operation
performed with the server (like hg pull, hg push etc.)

To checkout a mercurial repository 'my_example_repo', do:
$ hg clone %s/my_example_repo

and enter the above username and password.

2. Key-based authentication over SSH

Alternatively, you can submit your shared SSH public key to the repositories
maintainer and access the repositories over SSH.

To checkout a mercurial repository 'my_example_repo', do:
$ hg clone %s/my_example_repo

Do not reply to this email. For further questions, please email the
repositories maintainer instead.

------------------------------------------------------------------------------
""" % (repo_http_url, repo_ssh_url)


#############################################################

def random_pwd(size):
    """Returns a random password of length size """
    return ''.join([random.choice(string.letters + string.digits) for i in range(size)])

class HtpasswdFile:
    """A class for manipulating htpasswd files."""

    def __init__(self, filename, create=False):
        self.entries = []
        self.filename = filename
        if not create:
            if os.path.exists(self.filename):
                self.load()
            else:
                raise Exception("%s does not exist" % self.filename)

    def load(self):
        """Read the htpasswd file into memory."""
        lines = open(self.filename, 'r').readlines()
        self.entries = []
        for line in lines:
            e = line.split(':')
            entry = map(lambda x: x.strip(), e)
            self.entries.append(entry)

    def list(self):
        """List the entries in the htpasswd file."""
        return self.entries

    def save(self):
        """Write the htpasswd file to disk"""
        open(self.filename, 'w').writelines([":".join(entry) + "\n"
                                             for entry in self.entries])

    def update(self, username, password, realm=None):
        """Replace the entry for the given user, or add it if new."""
        kd = lambda x: md5(':'.join(x)).hexdigest()
        matching_entries = [entry for entry in self.entries
                            if entry[0] == username]
        if matching_entries:
            if len(matching_entries[0]) == 2:
                pwhash = crypt.crypt(password, random_pwd(2))
                matching_entries[0][1] = pwhash
            else:
                pwhash = kd([username, realm, password])
                matching_entries[0][1] = realm
                matching_entries[0][2] = pwhash
        else:
            if not realm:
                pwhash = crypt.crypt(password, random_pwd(2))
                self.entries.append([username, pwhash])
            else:
                pwhash = kd([username, realm, password])
                self.entries.append([username, realm, pwhash])

    def delete(self, username):
        """Remove the entry for the given user."""
        self.entries = [entry for entry in self.entries
                        if entry[0] != username]

class User:
    """ A class for managing the users """
    def __init__(self, filename):
        self.htfile = HtpasswdFile(filename)

    def add(self, username, password=None, realm=None, email=False):
        if not password:
            password = random_pwd(8)
        self.htfile.update(username, password, realm)
        self.htfile.save()
        if email:
            self.notify_user(username, password, email)

    def list(self):
        return set([x[0] for x in self.htfile.list()])

    def delete(self, username):
        self.htfile.delete(username)
        self.htfile.save()

    def notify_user(self, username, password, email):
        body = """
Greetings %s,
Your account details for the Mercurial repository(s) at %s are:

    Username: %s
    Password: %s

Best Regards,
Mercurial Repository Manager

*** Please delete this email after memorizing your password. ***
%s
""" % (username, repo_http_url, username, password, repo_usage)

        msg = MIMEText(body)
        msg['Subject'] = "Your password for mercurial repository at %s" % repo_http_url
        msg['From'] = repo_maintainer
        msg['To'] = email

        # Send the email
        s = smtplib.SMTP('localhost')
        s.sendmail(repo_maintainer, email, msg.as_string())
        s.quit()

class Repository:
    """ A class for managing the repositories """
    def __init__(self, filename):
        self.available_repos = {}
        config = ConfigParser.ConfigParser()
        config.read(filename)

        if config.has_section('paths'):
            paths = config.items('paths')
            for n, p in paths:
                self.add(n, os.path.abspath(p))

        if config.has_section('collections'):
            collections = config.items('collections')
            for _, c in collections:
                dirs = os.listdir(c)
                for d in dirs:
                    path = os.path.abspath(c) + '/' + d
                    if os.path.isdir(path) and os.path.isdir(path + '/.hg'):
                        self.add(os.path.basename(d), path)

    def add(self, name, path):
        self.available_repos[name] = path

    def list(self):
        return self.available_repos.keys()

    def listbyuser(self, username):
        repos = self.list()
        myrepos = set()
        for r in repos:
            urs = self.listusers(r, [username])
            for v in urs.values():
                if username in v:
                    myrepos.add(r)

        return myrepos

    def listusers(self, name, users=[]):
        u = {}
        path = self.available_repos[name]
        config = ConfigParser.ConfigParser()
        config.read(path + "/.hg/hgrc")
        ro_users = set()
        rw_users = set()
        if config.has_section('web'):
            if config.has_option('web', 'allow_read'):
                val = config.get('web', 'allow_read')
                if val == '*':
                    ro_users = users
                else:
                    ro_users = set(val.split(','))
            else:
                ro_users = users

            if config.has_option('web', 'allow_push'):
                val = config.get('web', 'allow_push')
                if val == '*':
                    rw_users = users
                else:
                    rw_users = val.split(',')
            else:
                rw_users = set()

        u['ro'] = set(ro_users) - set(rw_users)
        u['rw'] = set(rw_users)
        return u

    def adduser(self, name, username, mode='rw'):
        path = self.available_repos[name]
        config = ConfigParser.ConfigParser()
        config.read(path + '/.hg/hgrc')
        if not config.has_section('web'):
            config.add_section('web')

        if config.has_option('web', 'allow_read'):
            val = config.get('web', 'allow_read')
            if val != '*':
                config.set('web', 'allow_read', val + ',' + username)

        if mode == 'rw':
            if config.has_option('web', 'allow_push'):
                val = config.get('web', 'allow_push')
                if val != '*':
                    config.set('web', 'allow_push', val + ',' + username)
            else:
                config.set('web', 'allow_push', username)

        with open(path + '/.hg/hgrc', 'wb') as hgrc:
            config.write(hgrc)

    def deluser(self, name, username):
        path = self.available_repos[name]
        config = ConfigParser.ConfigParser()
        config.read(path + '/.hg/hgrc')
        if config.has_section('web'):
            if config.has_option('web', 'allow_read'):
                val = config.get('web', 'allow_read')
                if val != '*':
                    newval = set(val.split(',')) - set([username])
                    config.set('web', 'allow_read', ", ".join(newval))

            if config.has_option('web', 'allow_push'):
                val = config.get('web', 'allow_push')
                if val != '*':
                    newval = set(val.split(',')) - set([username])
                    config.set('web', 'allow_push', ", ".join(newval))

            with open(path + '/.hg/hgrc', 'wb') as hgrc:
                config.write(hgrc)


def ls(args):
    if args.username:
        repos = Repository(args.config_file)
        print "User [%s]:" % args.username
        print " ", "\n  ".join(repos.listbyuser(args.username))
    else:
        users = User(args.users_file)
        print "\n".join(users.list())

def lsr(args):
    repos = Repository(args.config_file)
    if args.reponame:
        users = User(args.users_file)
        print "Repository [%s]:" % args.reponame
        rusers = repos.listusers(args.reponame, users.list())
        for ro in rusers['ro']:
            print "  %s (ro)" % ro

        for rw in rusers['rw']:
            print "  %s (rw)" % rw
    else:
        print "\n".join(repos.list())

def add(args):
    users = User(args.users_file)
    if args.username in users.list():
        print "User %s already exists." % args.username
    else:
        users.add(args.username, password=args.password, realm=args.realm,
                  email=args.email)
        print "User %s added." % args.username

def rm(args):
    users = User(args.users_file)
    if args.username in users.list():
        yes = set(['yes','y', ''])
        no = set(['no','n'])
        sys.stdout.write("Are you sure you want to delete the user ")
        sys.stdout.write(args.username)
        sys.stdout.write(" (Y/N)? ")
        choice = raw_input().lower()
        if choice in yes:
            repos = Repository(args.config_file)
            users.delete(args.username)
            for r in repos.listbyuser(args.username):
                repos.deluser(r, args.username)
            print "User %s deleted." % args.username
    else:
        print "Invalid user %s." % args.username

def adduser(args):
    if args.mode:
        if args.mode != "ro" and args.mode != "rw":
            print "Invalid mode", args.mode
            return
    else:
        args.mode = 'rw'

    users = User(args.users_file)
    repos = Repository(args.config_file)
    if args.username not in users.list():
        print "User %s does not exist." % args.username
    else:
        for repo in args.repos:
            if repo not in repos.list():
                print "Repository %s does not exist." % repo
                return
            else:
                users = repos.listusers(repo)
                if args.username in users[args.mode]:
                    print "User %s is already a member of repository %s (mode=%s)" % (args.username, repo, args.mode)
                    next
                else:
                    repos.adduser(repo, args.username, args.mode)
                    print "User %s added to repository %s (mode=%s)." % (args.username, repo, args.mode)

def deluser(args):
    users = User(args.users_file)
    repos = Repository(args.config_file)
    if args.username not in users.list():
        print "User %s does not exist." % args.username
    else:
        for repo in args.repos:
            if repo not in repos.list():
                print "Repository %s does not exist." % repo
                return
            else:
                u = repos.listusers(repo, users.list())
                if args.username not in u['ro'] and args.username not in u['rw']:
                    print "User %s is not a member of repository %s" % (args.username, repo)
                    next
                else:
                    repos.deluser(repo, args.username)
                    print "User %s deleted from repository %s." % (args.username, repo)

def main():
    """Mercurial Repository Manager (v0.3)"""

    parser = ArgumentParser(description = main.__doc__)
    parser.add_argument('-v', '--version', action='version', version=hg_version)
    parser.add_argument('-c', '--config', dest='config_file',
                        default=default_config_file,
                        help='specify a hgweb.config configuration file.')
    parser.add_argument('-u', '--users', dest='users_file',
                        default=default_users_file,
                        help='specify a users file (.htpasswd or .htdigest).')

    cmdparser = parser.add_subparsers(title='commands', help='valid commands')

    # List users
    ls_parser = cmdparser.add_parser('ls', help='list users')
    ls_parser.add_argument('username', action='store', help='list user details',
                           nargs='?')
    ls_parser.set_defaults(func=ls)

    # Add users
    add_parser = cmdparser.add_parser('add', help='add a new user')
    add_parser.add_argument('username', action='store', help='new user to add')
    add_parser.add_argument('-r', '--realm', dest='realm',
                            default='mercurial repository',
                            help='realm to add the user to')
    add_parser.add_argument('password', action='store', help='user\'s password',
                            nargs='?')
    add_parser.add_argument('-e', '--email', dest='email',
                            help='notify the user through email')
    add_parser.set_defaults(func=add)

    # Remove users
    rm_parser = cmdparser.add_parser('rm', help='remove an existing user')
    rm_parser.add_argument('username', action='store', help='user to remove')
    rm_parser.set_defaults(func=rm)

    # List repositories
    lsr_parser = cmdparser.add_parser('lsr', help='list repositories')
    lsr_parser.add_argument('reponame', action='store', help='list repositories',
                            nargs='?')
    lsr_parser.set_defaults(func=lsr)

    # Add user(s) to a repository
    adduser_parser = cmdparser.add_parser('adduser', help='add an existing user to a repository')
    adduser_parser.add_argument('username', action='store', help='username')
    adduser_parser.add_argument('-m', '--mode', dest='mode', help='mode: (ro=read-only, rw=read-write)')
    adduser_parser.add_argument('repos', action='store', help='repositories to add the user to',
                                nargs='+')
    adduser_parser.set_defaults(func=adduser)

    # Delete user(s) from a repository
    deluser_parser = cmdparser.add_parser('deluser', help='delete an existing user from a repository')
    deluser_parser.add_argument('username', action='store', help='username')
    deluser_parser.add_argument('repos', action='store', help='repositories to delete the user from',
                                nargs='+')
    deluser_parser.set_defaults(func=deluser)

    args = parser.parse_args()

    def syntax_error(msg):
        """Utility function for displaying fatal error messages with usage help."""
        sys.stderr.write("Syntax error: " + msg)
        sys.stderr.write(parser.get_usage())
        sys.exit(1)

    print main.__doc__
    print "Configuration file:", args.config_file
    print "Users file:", args.users_file

    args.func(args)

    # repos.adduser('hg-manager', 'foo')

if __name__ == '__main__':
    main()

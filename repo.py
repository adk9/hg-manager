#!/usr/bin/env python

"""Module hg-manager
(c) 2011 Abhishek Kulkarni

Hg Repository Permissions Manager

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

    def delete(self, username, repo=None):
        self.htfile.delete(username)
        self.htfile.save()
        if repo:
            for r in repo.listbyuser(username):
                repo.deluser(r, username)

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
        config = ConfigParser.RawConfigParser()
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
                    self.add(os.path.basename(d), os.path.abspath(c) + '/' + d)

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

    def listusers(self, name, users):
        u = {}
        path = self.available_repos[name]
        config = ConfigParser.RawConfigParser()
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
        with open(path + '/.hg/hgrc', 'wb') as hgrc:
            config = ConfigParser.RawConfigParser()
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

            config.write(hgrc)

    def deluser(self, name, username):
        path = self.available_repos[name]
        with open(path + '/.hg/hgrc', 'wb') as hgrc:
            config = ConfigParser.RawConfigParser()
            config.read(path + '/.hg/hgrc')
            if config.has_section('web'):
                if config.has_option('web', 'allow_read'):
                    val = config.get('web', 'allow_read')
                    if val != '*':
                        newval = set(val) - set([username])
                        print "newval is", ", ".join(newval)
                        config.set('web', 'allow_read', ", ".join(newval))
                if config.has_option('web', 'allow_push'):
                    val = config.get('web', 'allow_push')
                    if val != '*':
                        newval = set(val) - set([username])
                        print "newval is", ", ".join(newval)
                        config.set('web', 'allow_push', ", ".join(newval))
                config.write(hgrc)

def main():
    """Mercurial Repository Manager (v0.3)"""

    parser = ArgumentParser(description = main.__doc__)
    parser.add_argument('-v', '--version', action='version', version=hg_version)
    parser.add_argument('-c', '--config', dest='config_file', default=default_config_file,
                        help='specify a hgweb.config configuration file.')
    parser.add_argument('-u', '--users', dest='users_file', default=default_users_file,
                        help='specify a users file (.htpasswd or .htdigest).')

    args = parser.parse_args()

    def syntax_error(msg):
        """Utility function for displaying fatal error messages with usage help."""
        sys.stderr.write("Syntax error: " + msg)
        sys.stderr.write(parser.get_usage())
        sys.exit(1)

    print main.__doc__
    print "Configuration file:", args.config_file
    print "Users file:", args.users_file

    users = User(args.users_file)
    repos = Repository(args.config_file)

    print "Users:", ", ".join(users.list())

    for r in repos.list():
        rusers = repos.listusers(r, users.list())
        print "[%s]:" % r
        if rusers['ro']:
            print "   %s (ro)" % ", ".join(rusers['ro'])

        if rusers['rw']:
            print "   %s (rw)" % ", ".join(rusers['rw'])

    print "Adding user (foo) with password (foobar)"
    users.add('foo', realm='garkbit repository')
    print "User foo added."
    print "Users:", ", ".join(users.list())

    repos.adduser('hg-manager', 'foo')

    for r in repos.list():
        rusers = repos.listusers(r, users.list())
        print "[%s]:" % r
        if rusers['ro']:
            print "   %s (ro)" % ", ".join(rusers['ro'])

        if rusers['rw']:
            print "   %s (rw)" % ", ".join(rusers['rw'])

    print "foo: "
    print ", ".join(repos.listbyuser('foo'))

    print "adkulkar: "
    print ", ".join(repos.listbyuser('adkulkar'))

    print "garkbit: "
    print ", ".join(repos.listbyuser('garkbit'))

#    print "Deleting user (foo)"
#    users.delete('foo', repos)
#    print "Deleted user (foo)"
    print "Users:", ", ".join(users.list())

#     # Non-option arguments
#     if len(args) < 2:
#         syntax_error("Insufficient number of arguments.\n")
#     filename, username = args[:2]
#     if options.delete_user:
#         if len(args) != 2:
#             syntax_error("Incorrect number of arguments.\n")
#         password = None
#     else:
#         if len(args) != 3:
#             syntax_error("Incorrect number of arguments.\n")
#         password = args[2]

#     passwdfile = HtpasswdFile(filename, create=options.create)

#     if options.delete_user:
#         passwdfile.delete(username)
#     else:
#         passwdfile.update(username, password)

#     passwdfile.save()

if __name__ == '__main__':
    main()

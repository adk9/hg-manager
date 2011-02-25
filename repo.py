#!/usr/bin/env python

"""Module hg-manager.
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
from argparse import ArgumentParser

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

#
# Global Configuration
#

# Default path to the hgweb configuration file
default_config_file = 'hgweb.config'

# Default path to the users file (containing a list of users)
default_users_file = '.htdigest'

# hg-gateway version
hg_version = "0.2"

def random_pwd(len):
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

    def update(self, username, password, realm = None):
        """Replace the entry for the given user, or add it if new."""
        pwhash = crypt.crypt(password, random_pwd(2))
        matching_entries = [entry for entry in self.entries
                            if entry[0] == username]
        if matching_entries:
            if len(matching_entries[0]) == 2:
                matching_entries[0][1] = pwhash
            else:
                matching_entries[0][1] = realm
                matching_entries[0][2] = pwhash
        else:
            if not realm:
                self.entries.append([username, pwhash])
            else:
                self.entries.append([username, realm, pwhash])

    def delete(self, username):
        """Remove the entry for the given user."""
        self.entries = [entry for entry in self.entries
                        if entry[0] != username]

class User:
    """ A class for managing the users """
    def __init__(self, filename):
        self.htfile = HtpasswdFile(filename)

    def add(self, username, password, realm = None):
        if not password:
            password = random_pwd(8)
        self.htfile.update(username, password, realm)
        self.htfile.save()

    def list(self):
        return [x[0] for x in self.htfile.list()]

    def delete(username):
        self.htfile.delete(username)
        self.htfile.save()

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
                    self.add(os.path.basename(d), os.path.abspath(d))

    def add(self, name, path):
        self.available_repos[name] = path

    def list(self):
        return self.available_repos.keys()

    def adduser(self, username):
        self.available_repos[name] = path

def main():
    """Mercurial Repository Manager (v0.2)"""

    parser = ArgumentParser(description = main.__doc__)
    parser.add_argument('-v', '--verbose', action='version', version=hg_version)
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

    u = User(args.users_file)
    r = Repository(args.config_file)

    print "Repositories:", r.list()
    print "Users:", u.list()

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

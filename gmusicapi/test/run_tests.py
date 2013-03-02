from functools import partial, update_wrapper
from getpass import getpass
import logging
import os
import sys
from types import MethodType

from proboscis import TestProgram

# these need to be imported for proboscis test discovery
from gmusicapi import Api
from gmusicapi.test import local_tests, server_tests
from gmusicapi.test.utils import NoticeLogging

travis_id = 'E9:40:01:0E:51:7A'
travis_name = 'Travis-CI (gmusicapi)'

# pretend to use test modules to appease flake8
_, _ = local_tests, server_tests


def freeze_login_details():
    """Searches the environment for credentials, and freezes them to
    Api.login if found.

    GMUSICAPI_TEST_USER and GMUSICAPI_TEST_PASSWD are the envvars checked.

    If no auth is present in the env, the user is prompted.

    If running on Travis, the prompt will never be fired; sys.exit is called
    if the envvars are not present.
    """

    #TODO this will prompt even if we're running just --group=local

    #Attempt to get auth from environ.
    user, passwd = os.environ.get('GMUSICAPI_TEST_USER'), os.environ.get('GMUSICAPI_TEST_PASSWD')
    on_travis = os.environ.get('TRAVIS')

    login_kwargs = {}

    if not (user and passwd) and on_travis:
        print 'on Travis but could not read auth from environ; quitting.'
        sys.exit(1)

    if os.environ.get('TRAVIS'):
        #Travis runs on VMs with no "real" mac - we have to provide one.
        login_kwargs.update({'uploader_id': travis_id,
                             'uploader_name': travis_name})

    if user and passwd:
        login_kwargs.update({'email': user, 'password': passwd})
    else:
        # no travis, no credentials

        # we need to login here to verify their credentials.
        # the authenticated api is then thrown away.

        api = Api()
        valid_auth = False

        print ("These tests will never delete or modify your music."
               "\n\n"
               "If the tests fail, you *might* end up with a test"
               " song/playlist in your library, though.")

        while not valid_auth:
            print
            email = raw_input("Email: ")
            passwd = getpass()

            valid_auth = api.login(email, passwd)

        login_kwargs.update({'email': email, 'password': passwd})

    # globally freeze our params in place.
    # they can still be overridden manually; they're just the defaults now.
    Api.login = MethodType(
        update_wrapper(partial(Api.login, **login_kwargs), Api.login),
        None, Api
    )


def main():
    freeze_login_details()

    # warnings typically signal a change in protocol,
    # so fail the build if anything >= warning are sent,

    root_logger = logging.getLogger('gmusicapi')

    noticer = NoticeLogging()
    noticer.setLevel(logging.WARNING)
    root_logger.addHandler(noticer)

    # proboscis does not have an exit=False equivalent,
    # so SystemExit must be caught instead (we need
    # to check the log noticer)
    try:
        TestProgram().run_and_exit()
    except SystemExit as e:
        print
        if noticer.seen_message:
            print '(failing build due to log warnings)'
            sys.exit(1)

        if e.code is not None:
            sys.exit(e.code)

if __name__ == '__main__':
    main()

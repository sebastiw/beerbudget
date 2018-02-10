#!/usr/bin/env python

"""
Version 3.6.4 of python used when developing this program.
"""

__DOCSTRING__ = """
Maximize your beer budget when going to Systembolaget.
"""
__EXAMPLES__ = """EXAMPLES

>>> %(prog)s 1000 --beer omnipollo leon 29
34 bottles of omnipollo leon (986:-)
Total: 986:-

>>> %(prog)s 1000 --beer omnipollo leon 29 --beer vodka 200
34 bottles of omnipollo leon (986:-)
Total: 986:-

27 bottles of omnipollo leon (783:-)
1 bottle of vodka (200:-)
Total: 983:-

...

5 bottles of vodka (1000:-)
Total: 1000:-

>>> %(prog)s 1000 --systembolaget omnipollo leon
Searching for "omnipollo leon"... Found 750ml for 49.90:-

20 bottles of omnipollo leon (998:-)

"""


import argparse
import os.path
import time
import requests
import re

import xml.etree.ElementTree as ET

from unittest.mock import MagicMock

__CACHE_TIMEOUT__ = 6*24*3600
__SYSTEMBOLAGET_URI__ = 'https://www.systembolaget.se/api/assortment/products/xml'

class Beer:
    def __init__(self, name, price):
        self.name = name
        self.price = price


class Input:
    """Reading and parsing input."""

    def __init__(self):
        self.params = None
        self.cache = 'cache.xml'

        self.parser = argparse.ArgumentParser(description=__DOCSTRING__,
                                              formatter_class=argparse.RawDescriptionHelpFormatter,
                                              epilog=__EXAMPLES__)
        self.parser.add_argument('budget', metavar='SEK', type=int,
                                 help='The budget you have in SEK')
        self.parser.add_argument('--beer', dest='beers', action='append',
                                 help='Add a beer to the calculations.', nargs='+',
                                 metavar='NAME PRICE', default=[])
        self.parser.add_argument('--systembolaget', dest='search', action='append',
                                 help='Search for a beer to add from Systembolaget.',
                                 nargs='+', metavar='NAME', default=[])

    def parse_args(self, args=None):
        self.params = self.parser.parse_args(args)
        self.parse_beers()
        self.parse_search()

    def parse_search(self):
        for i in range(len(self.params.search)):
            self.params.search[i] = " ".join(self.params.search[i])

    def parse_beers(self):
        for i in range(len(self.params.beers)):
            name = " ".join(self.params.beers[i][0:-1])
            price = int(self.params.beers[i][-1])
            self.params.beers[i] = Beer(name, price)

    def search(self):
        if len(self.params.search):
            self.check_cache()
            print("SEARCH...")
            # build a tree structure
            with open(self.cache, "r") as file:
                tree = ET.parse(file)
                artiklar = tree.getroot().findall('artikel')
                for artikel in artiklar:
                    for search in self.params.search:
                        p = re.compile(search, re.IGNORECASE)
                        name = "%s %s" % (artikel.find('Namn').text,
                                          artikel.find('Namn2').text)
                        if p.match(name):
                            print(name,
                                  artikel.find('Volymiml').text,
                                  artikel.find('Prisinklmoms').text,
                                  artikel.find('Saljstart').text,
                                  artikel.find('Forpackning').text,
                                  artikel.find('Alkoholhalt').text)


    def check_cache(self):
        if (not os.path.isfile(self.cache) or
            (time.time()-os.path.getmtime(self.cache)) > __CACHE_TIMEOUT__):
            self.download_systembolaget()
            return 1
        else:
            print("Cache ok.")
            return 0

    def download_systembolaget(self):
        print("Downloading cache")
        r = requests.get(__SYSTEMBOLAGET_URI__)
        if r.status_code == 200:
            self.save_cache(r.text)
        else:
            print("Error: %s %s" % (r.status, r.text))
            exit(1)

    def save_cache(self, content):
        with open(self.cache, 'w') as file:
            file.write(content)


class Test:
    def __init__(self):
        self.parse_arguments_test()
        self.download_test()
        self.check_cache_test()

    def parse_arguments_test(self):
        """Testing reading input"""
        x = Input()
        x.parse_args('30 --beer omnipollo 29 --beer svensk kronvodka 200 --systembolaget omnipollo leon'.split())

        assert x.params.budget == 30
        assert x.params.beers[0].name == "omnipollo"
        assert x.params.beers[0].price == 29
        assert x.params.beers[1].name == "svensk kronvodka"
        assert x.params.beers[1].price == 200
        assert x.params.search[0] == "omnipollo leon"

        pass

    def download_test(self):
        global __SYSTEMBOLAGET_URI__
        uri = __SYSTEMBOLAGET_URI__
        __SYSTEMBOLAGET_URI__ = 'http://dummyurl'
        x = Input()
        try:
            x.download_systembolaget()
        except requests.exceptions.ConnectionError as e:
            prefix = ("HTTPConnectionPool(host='dummyurl', port=80): Max "
                      "retries exceeded with url: / (Caused by "
                      "NewConnectionError(")
            suffix = ("Failed to establish a new connection: [Errno -2] Name "
                      "or service not known',))")
            assert str(e).startswith(prefix)
            assert str(e).endswith(suffix)

            pass
        else:
            assert False

    def check_cache_test(self):
        x = Input()
        x.download_systembolaget = MagicMock(return_value=0)
        x.cache = "__TEST_CACHE_FILE__.test.tmp"

        assert not os.path.isfile(x.cache)
        assert 1 == x.check_cache()
        # Create cache file
        x.save_cache("TEST")
        assert 0 == x.check_cache()
        # Check mtime
        os.utime(x.cache, (time.time()-__CACHE_TIMEOUT__, time.time()-__CACHE_TIMEOUT__))
        assert 1 == x.check_cache()
        # Cleanup
        os.remove(x.cache)

if __name__=='__main__':
    Test()

    x = Input()
    x.parse_args()
    x.search()

#!/usr/bin/env python

"""
Version 3.6.4 of python used when developing this program.
"""

__DOCSTRING__ = """
Maximize your beer budget when going to Systembolaget.
"""
__EXAMPLES__="""EXAMPLES

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


class Input:
    """Reading and parsing input."""

    def __init__(self):
        self.params = None
        self.parser = argparse.ArgumentParser(description=__DOCSTRING__,
                                              formatter_class=argparse.RawDescriptionHelpFormatter,
                                              epilog=__EXAMPLES__)
        self.parser.add_argument('budget', metavar='SEK', type=int,
                                 help='The budget you have in SEK')
        self.parser.add_argument('--beer', dest='beers', action='append',
                                 help='Add a beer to the calculations.', nargs='+',
                                 metavar='NAME PRICE')
        self.parser.add_argument('--systembolaget', dest='search', action='append',
                                 help='Search for a beer to add from Systembolaget.',
                                 nargs='+', metavar='NAME')

    def parse_args(self, args=None):
        self.params = self.parser.parse_args(args)


class Test:
    def __init__(self):
        self.parse_arguments_test()

    def parse_arguments_test(self):
        """Testing reading input"""
        x = Input()
        x.parse_args('30 --beer omnipollo 29 --beer svensk kronvodka 200 --systembolaget omnipollo leon'.split())

        assert x.params.budget == 30
        assert x.params.beers[0][0] == "omnipollo"
        assert x.params.beers[0][-1] == "29"
        assert x.params.beers[1][0] == "svensk"
        assert x.params.beers[1][1] == "kronvodka"
        assert x.params.beers[1][-1] == "200"
        assert x.params.search[0][0] == "omnipollo"
        assert x.params.search[0][1] == "leon"

        pass


if __name__=='__main__':
    Test()

#    x = Input()
#    x.parse_args(['--help'])


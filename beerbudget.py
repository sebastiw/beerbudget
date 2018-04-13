#!/usr/bin/env python

"""
Version 3.6.4 of python used when developing this program.
"""

__DOCSTRING__ = """
Maximize your beer budget when going to Systembolaget.
"""
__EXAMPLES__ = """EXAMPLES
>>> %(prog)s 1000 --beer omnipollo leon 29 --beer vodka 200
34 omnipollo leon (29.00) 986.00
Total: 986.00 SEK

>>> %(prog)s 1000 --search gambrinus --search lagunitas ipa\
                  --beer Omnipollo Leon 49.9 --systembolag hötorg
Choosed beers:
11 Omnipollo Leon (49.90) 548.90 SEK
11 Gambrinus (16.90) 185.90 SEK
11 Lagunitas IPA (23.90) 262.90 SEK
Total: 997.70 SEK

>>> %(prog)s 1000 --search gambrinus --search lagunitas ipa\
                  --beer Omnipollo Leon 49.9 --systembolag hötorg\
                  --algorithm knapsack
Choosed beers:
3 Omnipollo Leon (49.90) 149.70
39 Gambrinus (16.90) 659.10
8 Lagunitas IPA (23.90) 191.20
Total: 1000.00 SEK
"""


import argparse
import os.path
import time
import requests
import re
import sys

import xml.etree.ElementTree as ET
from decimal import Decimal

from unittest.mock import MagicMock

import knapsack

__CACHE_TIMEOUT__ = 1*24*3600
__SYSTEMBOLAGET_ASSORTMENT_URI__ = 'https://www.systembolaget.se/api/assortment/products/xml'
__SYSTEMBOLAGET_STORES_URI__ = 'https://www.systembolaget.se/api/assortment/stores/xml'
__SYSTEMBOLAGET_MAPPING_URI__ = 'https://www.systembolaget.se/api/assortment/stock/xml'

class Beer:
    def __init__(self, name, price, nr=None):
        self.name = name
        self.price = Decimal(price)
        self.nr = nr


class Store:
    def __init__(self, name, store_id):
        self.name = name
        self.store_id = store_id


class Input:
    """Reading and parsing input."""

    @staticmethod
    def choose_multiple_matches(search_patterns, choices):
        """If there are multiple matches"""
        choosed = []
        for search in search_patterns:
            p = re.compile(".*%s.*" % search, re.IGNORECASE)
            matches = []
            for c in choices:
                if p.match(c.name):
                    matches.append(c)
            if len(matches) > 1:
                print("Multiple matches! Choose one of")
                for i,m in enumerate(matches):
                    if hasattr(m, 'price'):
                        print(i, m.name, m.price)
                    else:
                        print(i, m.name)
                no = int(input('Choose an index: '))
                if no >= 0 and no < len(matches):
                    choosed.append(matches[no])
                else:
                    print("None selected. Skipping.")
            elif len(matches) == 1:
                choosed.append(matches[0])
            else:
                print("No matches. Skipping %s." % search)
        return choosed

    @staticmethod
    def compile_patterns(searches):
        patterns = []
        for search in searches:
            p = re.compile(".*%s.*" % search, re.IGNORECASE)
            patterns.append(p)
        return patterns

    @staticmethod
    def save_cache(cache_file, content):
        with open(cache_file, 'w') as file:
            file.write(content)

    def __init__(self):
        self.params = None
        self.assortment_cache = 'assortment.xml'
        self.stores_cache = 'stores.xml'
        self.store_assortment_cache = 'store_assortment.xml'
        self.beers = []
        self.store = None
        self.assortment = []
        self.searched_beers = []
        self.searched_stores = []
        self.beer_patterns = []
        self.store_patterns = []

        self.parser = argparse.ArgumentParser(description=__DOCSTRING__,
                                              formatter_class=argparse.RawDescriptionHelpFormatter,
                                              epilog=__EXAMPLES__)
        self.parser.add_argument('budget', metavar='SEK', type=Decimal,
                                 help='The budget you have in SEK')
        self.parser.add_argument('--beer', dest='beers', action='append',
                                 help='Add a beer to the calculations.', nargs='+',
                                 metavar='NAME PRICE', default=[])
        self.parser.add_argument('--search', dest='search_beer', action='append',
                                 help='Search for a beer to add from Systembolaget.',
                                 nargs='+', metavar='NAME', default=[])
        self.parser.add_argument('--systembolag', dest='search_store', action='append',
                                 help='Search for beers on a specific Systembolaget.',
                                 nargs='+', metavar='NAME', default=[])
        self.parser.add_argument('--algorithm', dest='algorithm', action='store',
                                 default='roundrobin', type=str,
                                 help="""How to perform the calculations,
                                 either with roundrobin or knapsack""")


    def parse_args(self, args=None):
        self.params = self.parser.parse_args(args)
        self.parse_beers()
        self.parse_search()

    def parse_search(self):
        for i in range(len(self.params.search_beer)):
            self.params.search_beer[i] = " ".join(self.params.search_beer[i])

        for i in range(len(self.params.search_store)):
            self.params.search_store[i] = " ".join(self.params.search_store[i])

    def parse_beers(self):
        for i in range(len(self.params.beers)):
            name = " ".join(self.params.beers[i][0:-1])
            price = Decimal(self.params.beers[i][-1])
            self.beers.append(Beer(name, price))

    def search_beer(self):
        if len(self.params.search_beer):
            self.beer_patterns = self.compile_patterns(self.params.search_beer)
            self.check_cache(self.assortment_cache, __SYSTEMBOLAGET_ASSORTMENT_URI__)
            self.find_beers()
            beers = self.choose_multiple_matches(self.params.search_beer,
                                                 self.searched_beers)
            self.beers += beers


    def search_store(self):
        if self.params.search_store:
            self.store_patterns = self.compile_patterns(self.params.search_store)
            self.check_cache(self.stores_cache, __SYSTEMBOLAGET_STORES_URI__)
            self.find_store()
            stores = self.choose_multiple_matches([self.params.search_store],
                                                  self.searched_stores)
            if stores:
                self.store = stores[0]
                print("Choosed %s" % self.store.name)
            else:
                print("No systembolaget found.")

    def check_cache(self, cache_file, download_uri):
        if (not os.path.isfile(cache_file) or
            (time.time()-os.path.getmtime(cache_file)) > __CACHE_TIMEOUT__):
            self.download_cache(cache_file, download_uri)
            return 1
        else:
            return 0

    def download_cache(self, cache_file, url):
        r = requests.get(url)
        if r.status_code == 200:
            self.save_cache(cache_file, r.text)
        else:
            print("Error: %s %s" % (r.status, r.text))
            exit(1)

    def find_beers(self):
        """Parse cache and search for beers"""
        with open(self.assortment_cache, "r") as file:
            tree = ET.parse(file)
            artiklar = tree.getroot().findall('artikel')

            for artikel in artiklar:
                if artikel.find('Namn2').text:
                    name = "%s %s" % (artikel.find('Namn').text,
                                      artikel.find('Namn2').text)
                else:
                    name = artikel.find('Namn').text

                for p in self.beer_patterns:
                    name_match = p.match(name)
                    not_discontinued = artikel.find('Utgått').text == "0"
                    nr = artikel.find('nr').text
                    available = self.is_available(nr)
                    if name_match and not_discontinued and available:
                        pris = artikel.find('Prisinklmoms').text
                        self.searched_beers.append(Beer(name, pris, nr))

    def is_available(self, beer_nr):
        return (not self.store) or beer_nr in self.assortment

    def populate_store_assortment(self):
        if self.store and self.store.store_id:
            self.check_cache(self.store_assortment_cache,
                             __SYSTEMBOLAGET_MAPPING_URI__)
            with open(self.store_assortment_cache, "r") as file:
                tree = ET.parse(file)
                butik = tree.getroot().findall("./Butik[@ButikNr='%s']" % self.store.store_id)
                if butik:
                    print("Found store")
                    for a in butik[0].findall('ArtikelNr'):
                        self.assortment.append(a.text)
                else:
                    print("No store match in assortment file.")
        else:
            print("No store assigned.")


    def find_store(self):
        """parse cache and search for store"""
        with open(self.stores_cache, "r") as file:
            tree = ET.parse(file)
            butiker = tree.getroot().findall('ButikOmbud')
            for butik in butiker:
                name = butik.find('Namn').text
                address = butik.find('Address1').text
                if not name:
                    name = address
                elif address:
                    name = "%s %s" % (name, address)

                for p in self.store_patterns:
                    if p.match(name):
                        store_id = butik.find('Nr').text
                        self.searched_stores.append(Store(name, store_id))


class Solve:
    def __init__(self, algorithm):
        if "roundrobin" == algorithm or "rr" == algorithm:
            self.algo = self.round_robin
        elif "knapsack" == algorithm or "ks" == algorithm:
            self.algo = self.knapsack
        elif "naive" == algorithm or "nks" == algorithm:
            self.algo = self.naive_knapsack
        else:
            self.algo = self.round_robin

    def solve(self, budget, beers):
        total, choosen = self.algo(budget, beers)
        for num,beer in choosen:
            print("%s %s (%s) %s SEK" % (num, beer.name, beer.price,
                                         num*beer.price))
        print("Total: %s SEK" % total)

    @staticmethod
    def round_robin(budget, beers):
        bag = []
        price = 1
        price0 = 0
        while price != price0 and price <= budget:
            price = price0
            for beer in beers:
                if (price0+beer.price) <= budget:
                    bag.append(beer)
                    price0 += beer.price

        total = 0
        num_beers = []
        for beer in beers:
            num = sum(b.name == beer.name for b in bag)
            total += num*beer.price
            num_beers.append((num, beer))
        return total, num_beers

    @staticmethod
    def knapsack(budget, beers):
        reverse_lookup = dict()
        for b in beers:
            if b.price in reverse_lookup:
                reverse_lookup[b.price].append(b)
            else:
                reverse_lookup[b.price] = [b]

        prices = []
        for price in reverse_lookup.keys():
            prices += int(budget//price)*[price]
        total, items = knapsack.knapsack(prices, prices).solve(budget)

        item_prices = list(map((lambda i: prices[i]), items))
        choosen = []
        for price in set(item_prices):
            num = item_prices.count(price)
            beers = reverse_lookup[price]
            for i,b in enumerate(beers):
                num_i = num // len(beers) + (1 if (num % len(beers) > i) else 0)
                choosen.append((num_i, b))
        return total, choosen

    @staticmethod
    def naive_knapsack(budget, beers, total=0, choosen=[], depth=100):
        if 0 == budget:
            print("No budget given")
            return total, choosen

        if 0 == total:
            total, choosen = Solve.round_robin(budget, beers)

        if budget == total:
            print("Optimal already found")
            return total, choosen

        new_total = total
        new_choosen = choosen[:]
        best_bags = []
        while depth:
            bags = []
            rest_budget = budget - new_total
            for n,b in new_choosen:
                bs = beers[:]
                bs.remove(b)
                bags.append((b, Solve.round_robin(rest_budget+b.price, bs)))

            max_total, new_beers = Solve.take_max_bag(bags)

            new_choosen = Solve.merge_beers(new_choosen, new_beers)
            new_total += max_total
            is_valid = True
            for n,b in new_choosen:
                if n < 0:
                    is_valid = False
                    break
            if is_valid:
                if budget == new_total:
                    print("Optimal found")
                    return new_total, new_choosen
                best_bags.append((new_total, new_choosen))

            depth -= 1

        print("Depth ran out")
        best_total = 0
        best_beers = []
        for n,bs in best_bags:
            if n > best_total:
                best_total = n
                best_beers = bs

        return best_total, best_beers

    @staticmethod
    def merge_beers(list1, list2):
        beer_dict = {b: n for n, b in list1}
        for n, b in list2:
            beer_dict[b] += n
        return [(n, b) for b,n in beer_dict.items()]

    @staticmethod
    def take_max_bag(bags):
        max_total = sys.maxsize
        max_beers = 0
        new_beers = []
        remove = None
        for b,(n,bs) in bags:
            if len(bs) > max_beers or (len(bs) == max_beers and n < max_total):
                max_total = n
                new_beers = bs
                new_beers.append((-1,b))
                remove = b
        return max_total-remove.price, new_beers


class Test:
    def __init__(self):
        self.parse_arguments_test()
        self.download_test()
        self.check_cache_test()

    @staticmethod
    def parse_arguments_test():
        """Testing reading input"""
        x = Input()
        x.parse_args('30 --beer omnipollo 29 --beer svensk kronvodka 200 --search omnipollo leon'.split())

        assert x.params.budget == 30
        assert x.beers[0].name == "omnipollo"
        assert x.beers[0].price == 29
        assert x.beers[1].name == "svensk kronvodka"
        assert x.beers[1].price == 200
        assert x.params.search_beer[0] == "omnipollo leon"

        pass

    @staticmethod
    def download_test():
        dummy_url = 'http://dummyurl'
        x = Input()
        try:
            x.download_cache("mocked.file", dummy_url)
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

    @staticmethod
    def check_cache_test():
        x = Input()
        x.download_cache = MagicMock(return_value=0)
        x.assortment_cache = "__TEST_CACHE_FILE__.test.tmp"

        assert not os.path.isfile(x.assortment_cache)
        assert 1 == x.check_cache(x.assortment_cache, "mocked.uri")
        # Create cache file
        x.save_cache(x.assortment_cache, "TEST")
        assert 0 == x.check_cache(x.assortment_cache, "mocked.uri")
        # Check mtime
        os.utime(x.assortment_cache, (time.time()-__CACHE_TIMEOUT__, time.time()-__CACHE_TIMEOUT__))
        assert 1 == x.check_cache(x.assortment_cache, "mocked.uri")
        # Cleanup
        os.remove(x.assortment_cache)

if __name__=='__main__':
    Test()

    x = Input()
    x.parse_args()
    x.search_store()
    x.populate_store_assortment()
    x.search_beer()

    print("Choosed beers:")
    for beer in x.beers:
        print(beer.name, beer.price)

    Solve(x.params.algorithm).solve(x.params.budget, x.beers)

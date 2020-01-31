"""
pdf_meta.py

funtions related to meta data

sources:
    2. doi - crossref.org
    3. pmid, pmcid - ncbi
"""

import os
import json
import requests
import pandas as pd

from urllib.parse import urlencode, quote_plus
from urllib.error import HTTPError

import bibtexparser
from bibtexparser.bparser import BibTexParser
from bibtexparser.bibdatabase import BibDatabase
from bibtexparser.bwriter import BibTexWriter
from bibtexparser.customization import convert_to_unicode

from arxiv2bib import arxiv2bib

from Levenshtein import ratio, matching_blocks, editops

from pdf_text import find_author1

EMPTY_RESULT = {
    "crossref_title": "",
    "similarity": 0,
    "doi": ""
}


def get_bib(doi, filename=None):
    """ get bib from crossref.org and arXiv.org """

    if doi is None:
        return False, None
    if not isinstance(doi, str):
        return False, None

    found = False
    bib = None

    # for arXiv:XXXX case
    if doi.lower()[:5] == "arxiv":
        doi = doi[6:]
        bib_object = arxiv2bib([doi])
        bib = bib_object[0].bibtex()
        if len(bib) > 0:
            found = True
            bib = bib_to_dict(bib)
        else:
            found = False

    # for crossref
    else:
        bare_url = "http://api.crossref.org/"
        url = "{}works/{}/transform/application/x-bibtex"
        url = url.format(bare_url, doi)

        r = requests.get(url)

        found = False if r.status_code != 200 else True

        bibtex_str = str(r.content, "utf-8")

        if bibtex_str.find("Resource not found") == -1:
            if filename is not None:
                with open(filename, "w") as f:
                    f.write(bibtex_str)

            bib = bib_to_dict(bibtex_str)
        else:
            found = False

    return found, bib


def save_bib(bib_dict, filename):
    """ save dictionay bib records into file """

    if bib_dict is None: return

    db = BibDatabase()
    for item in bib_dict:
        if isinstance(item.get('keywords'), list) and (len(item.get('keywords')) > 0):
            item['keywords'] = ','.join(item.get('keywords'))
        else:
            item['keywords'] = ''

        for k in item.keys():
            item[k] = str(item[k])

    #print(bib_dict)
    db.entries = bib_dict
    writer = BibTexWriter()

    with open(filename, 'w') as bibfile:
        bibfile.write(writer.write(db))

    print('... save to {}'.format(filename))


def read_bib(filename, cache=False, verb=True):
    """ read bibtex file and return bibtexparser object """

    fname_csv = filename.replace('.bib', '.csv')

    if (not os.path.exists(filename)) and (not os.path.exists(fname_csv)):
        if verb: print("... no bib file: {}".format(filename))
        return None

    if cache and (os.path.exists(fname_csv)):
        p = pd.read_csv(fname_csv, index_col=0)
        if verb: print('... cached from {}'.format(fname_csv))
        return p.to_dict('records')

    with open(filename) as f:
        bibtex_str = f.read()

    if verb: print('... read from {}'.format(filename))
    bib_dict = bib_to_dict(bibtex_str)

    if (bib_dict is not None) and cache:
        if verb: print('... cached to {}'.format(fname_csv))
        p = pd.DataFrame.from_dict(bib_dict)
        p.to_csv(fname_csv)

    return bib_dict


def bib_to_dict(bib_string):
    """ convert bibtex string to dictionary """

    parser = BibTexParser(common_strings=True)
    parser.ignore_nonstandard_types = False
    parser.homogenise_fields = False
    parser.customization = convert_to_unicode

    bdb = bibtexparser.loads(bib_string, parser)

    if len(bdb.entries) > 0:
        for i in range(len(bdb.entries)):
            if bdb.entries[i].get('keywords', '') != '':
                bdb.entries[i]['keywords'] = bdb.entries[i].get('keywords').split(',')

        if len(bdb.entries) == 1: return bdb.entries[0]
        else: return bdb.entries
    else:
        return None


def get_pmid(idstring, debug=False):
    """ find doi, pmid, pmcid using ncbi website """

    found = False

    tool = "py_readpaper"
    email = "sungcheol.kim78@gmail.com"
    baseurl = "https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/?tool={}&email={}".format(tool, email)
    query = "&ids={}&format=json".format(idstring)

    r = requests.get(baseurl + query)
    result = r.json()

    if "records" not in result:
        if debug: print('... not found {}'.format(idstring))
        found = False
    else:
        result = result["records"][0]
        found = True

    if found:
        return found, result
    else:
        return found, None

# modified from https://github.com/OpenAPC/openapc-de/blob/master/python/import_dois.py
def crossref_query_title(title):
    """ retrieve doi from paper title """

    api_url = "https://api.crossref.org/works?"
    params = {"rows": "5", "query.bibliographic": title}
    url = api_url + urlencode(params, quote_via=quote_plus)

    r = requests.get(url)
    try:
        data = json.loads(r.content)
        #print(data)

        items = data["message"]["items"]
        most_similar = EMPTY_RESULT
        for item in items:
            title = item["title"].pop()
            result = {
                "crossref_title": title,
                "similarity": ratio(title.lower(), params["query.bibliographic"].lower()),
                "doi": item["DOI"]
            }
            if most_similar["similarity"] < result["similarity"]:
                most_similar = result
        return {"success": True, "result": most_similar}
    except HTTPError as httpe:
        return {"success": False, "result": EMPTY_RESULT, "exception": httpe}


def find_bib(bibdb, bib, subset=['doi'], threshold=0.6, debug=False):
    """ find bib item from bib file """

    result_list = []

    for bibitem in bibdb:
        score = 0
        for by in subset:
            if bib.get(by, "1") == bibitem.get(by, "2"):
                if debug: print('... {} is same'.format(by))
                score = score + 1
                continue
            elif by != 'year':

                # add author1 check
                if by == 'author':
                    author1 = str(bib.get('author', '1')).lower()
                    author2 = str(bibitem.get('author', '2')).lower()
                    author1s = str(bib.get('author1', '1')).lower()
                    author2s = str(bibitem.get('author1', '2')).lower()
                    if author2s == '2': author2s = find_author1(author2)
                    if author1.find(author2s) > -1: score = score + 1
                    if author2.find(author1s) > -1: score = score + 1
                    if debug: print('... [{}] compare {} | {}'.format(by, author1, author2))
                    if debug: print('... [{}] compare {} | {}'.format(by, author1s, author2s))
                    continue

                # other item check
                old_text = str(bibitem.get(by, "2")).lower()
                new_text = str(bib.get(by, "1")).lower()
                if ratio(old_text, new_text) > threshold:
                    if debug: print('... [{}] {} is similar to {}'.format(by, old_text, new_text))
                    score = score + 1
                    continue

        if score == len(subset):
            result_list.append(bibitem)

    return result_list


def print_bib(bibitem, form='short'):
    """ print bib item in various form """

    if form == 'short':
        col_list = ['year', 'author', 'title', 'journal', 'doi', 'local-url']
    elif form == 'normal':
        col_list = ['local-url', 'title', 'author', 'year', 'doi', 'journal', 'keywords', 'subject', 'abstract']
    elif form == 'full':
        col_list = bibitem.keys()

    for c in col_list:
        print("[{}]: {}".format(c, bibitem.get(c)))

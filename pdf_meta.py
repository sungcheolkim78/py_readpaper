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
from urllib.parse import urlencode, quote_plus
from urllib.error import HTTPError

import bibtexparser
from bibtexparser.bparser import BibTexParser
from bibtexparser.bibdatabase import BibDatabase
from bibtexparser.bwriter import BibTexWriter

from arxiv2bib import arxiv2bib

from Levenshtein import ratio, matching_blocks, editops

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
        bib = arxiv2bib([doi])
        bib = bib[0].bibtex()
        found = True if len(bib) > 0 else False

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
    db.entries = bib_dict
    writer = BibTexWriter()

    with open(filename, 'w') as bibfile:
        bibfile.write(writer.write(db))

    print('... save to {}'.format(filename))


def read_bib(filename):
    """ read bibtex file and return bibtexparser object """

    if not os.path.exists(filename):
        print("... no bib file: {}".foramt(filename))
        return

    with open(filename) as f:
        bibtex_str = f.read()

    return bib_to_dict(bibtex_str)


def bib_to_dict(bib_string):
    """ convert bibtex string to dictionary """

    parser = BibTexParser(common_strings=True)
    parser.ignore_nonstandard_types = False
    parser.homogenise_fields = False

    bdb = bibtexparser.loads(bib_string, parser)

    if len(bdb.entries) > 0:
        return bdb.entries[0]
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
        return foudn, None


EMPTY_RESULT = {
    "crossref_title": "",
    "similarity": 0,
    "doi": ""
}

# modified from https://github.com/OpenAPC/openapc-de/blob/master/python/import_dois.py
def crossref_query_title(title):
    """ retrieve doi from paper title """

    api_url = "https://api.crossref.org/works?"
    params = {"rows": "5", "query.title": title}
    url = api_url + urlencode(params, quote_via=quote_plus)

    r = requests.get(url)
    try:
        data = json.loads(r.content)

        items = data["message"]["items"]
        most_similar = EMPTY_RESULT
        for item in items:
            title = item["title"].pop()
            result = {
                "crossref_title": title,
                "similarity": ratio(title.lower(), params["query.title"].lower()),
                "doi": item["DOI"]
            }
            if most_similar["similarity"] < result["similarity"]:
                most_similar = result
        return {"success": True, "result": most_similar}
    except HTTPError as httpe:
        return {"success": False, "result": EMPTY_RESULT, "exception": httpe}

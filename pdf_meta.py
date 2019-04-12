"""
pdf_meta.py

funtions related to meta data

sources:
    2. doi - crossref.org
    3. pmid, pmcid - ncbi
"""

import json
import requests
from urllib.parse import urlencode, quote_plus
from urllib.error import HTTPError

import bibtexparser
from bibtexparser.bparser import BibTexParser

from arxiv2bib import arxiv2bib

from Levenshtein import ratio, matching_blocks, editops

def get_bib(doi, asDict=True):
    """ get bib from crossref.org and arXiv.org """

    found = False

    if doi is None:
        return found, None
    if doi == "":
        return found, None

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
        bib = str(r.content, "utf-8")

    if not found:
        return found, None

    if asDict:
        parser = BibTexParser(common_strings=True)
        parser.ignore_nonstandard_types = False
        parser.homogenise_fields = False

        bdb = bibtexparser.loads(bib, parser)
        entry = bdb.entries[0]

        return found, entry
    else:
        return found, bib


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

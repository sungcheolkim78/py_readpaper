"""
py_readpaper.py
"""

import requests
from arxiv2bib import arxiv2bib
from pyexif import pyexif

from pdf_reader import convertPDF_pdfminer
from pdf_reader import convertPDF_xpdf
from pdf_reader import countPDFPages
from pdf_reader import openPDF

from gensim.summarization import keywords
from gensim.summarization import summarize

import bibtexparser
from bibtexparser.bparser import BibTexParser


class Paper(object):
    """ read paper pdf and extract key informations """

    def __init__(self, filename, debug=False):
        """ initialize Paper class """

        self._fname = filename
        self._debug = debug

        self._text = convertPDF_xpdf(filename, maxpages=2)
        self._pages = countPDFPages(filename)
        self._exif = pyexif.ExifEditor(filename)

        self._doi = ''
        self._bib = ''
        self._year = ''
        self._author = ''
        self._journal = ''
        self._title = ''
        self._abstract = ''
        self._keywords = []
        self._dictTags = self._exif.getDictTags()

    def open(self):
        """ open in mac """

        openPDF(self._fname)

    def keywords_gensim(self, words=10, sentenceLength=20):
        """ list keywords """

        return keywords(self.contents(sentenceLength=sentenceLength, split=False), words=words, lemmatize=True, split=True)

    def contents(self, sentenceLength=10, split=True, maxpages=-1):
        """ extract only contents or filter out short sentences """

        if maxpages > -1:
            self._text = convertPDF_xpdf(self._fname, maxpages=maxpages)

        res = []
        for t in self._text:
            if len(t) < sentenceLength:
                continue
            res.append(t)

        if split:
            return res
        else:
            return ''.join(res)

    def head(self, n=10, linenumber=True):
        """ show head of texts from paper """

        for i in range(n):
            print("{} {}".format(i, self._text[i]))

    def doi(self):
        """ find doi from text """

        # check self value
        if len(self._doi) > 0:
            if self._debug: print('... read from self._doi')
            return self._doi

        # check exif
        doi = self._exif.getTag('DOI')
        if doi is not None:
            self._doi = doi
            if self._debug: print('... read from exif')
            return doi

        # check pdf text - read through all lines
        doi = ''
        for t in self._text:
            t = t.strip('\n\r')

            # check doi
            doi_pos = t.lower().find("doi")
            if doi_pos > -1:
                if t[doi_pos:doi_pos+4].lower() == "doi:":
                    doi = t[doi_pos+4:].lstrip()
                    if doi[:3] == "10.": break
                elif t[doi_pos:doi_pos+4].lower() == "doi ":
                    doi = t[doi_pos+4:].lstrip()
                    if doi[:3] == "10.": break
                elif t.find("/", doi_pos) > -1:
                    doi = t[t.find("/", doi_pos)+1:]
                    if doi[:3] == "10.": break

            # check arXiv
            arxiv_pos = t.lower().find("arxiv:")
            if arxiv_pos > -1:
                end_pos = t.find(" ", arxiv_pos)
                doi = t[arxiv_pos:end_pos]
                break

            # 10.XXXX
            if t[:3].lower() == "10.":
                doi = t[0:t.find(" ")]
                break

        if doi.find(" ") > -1:
            doi = doi.split(' ')[0]

        if doi != "": self._doi = doi

        return doi


    def bibtex(self, doi=""):
        """ find bibtex information based on doi """

        if (doi == "") and (self._doi == ""):
            if self.doi() == "":
                print('... not found doi')
                return ""
        if (doi != "") and (self._doi == ""):
            self._doi = doi
        if (doi != "") and (self._doi != ""):
            print("... select internal doi: {}".format(self._doi))

        found, bib = get_bib(self._doi, asDict=True)

        # update information
        if found:
            self._bib = bib
            self._year = bib['year']
            self._author = bib['author']
            self._title = bib['title']
            if 'journal' in bib:
                self._journal = bib['journal']
            if 'archiveprefix' in bib:
                self._journal = bib['archiveprefix']
            if 'abstract' in bib:
                self._abstract = bib['abstract']
            if 'keywords' in bib:
                self._keywords = bib['keywords']
        else:
            print('... not found bib information')

        return self._bib

    def keywords(self):
        """ find keywords from text """

        # check self value
        res = self._keywords
        if self._debug: print('self: {}'.format(res))

        # check exif values
        kws = self._exif.getTag('Keywords')
        if kws is not None: res.extend(kws)
        if self._debug: print('exif: {}'.format(res))

        # check file text
        find_words = ["keywords:", "keywords.", "key words", "keywortlf", "keywords"]
        end_words = ["PACS", "DOI"]
        sep_words = [",", ";", ".", "/"]
        ban_words = [""]

        for t in self._text:
            # remove non-text characters
            t = t.strip('\n\r').replace("·", "").replace("Æ", "").replace("Á", "")

            # find keyword
            kw_pos = -1; max_pos = 0
            for i, fw in enumerate(find_words):
                tmp = t.lower().find(fw)
                (kw_pos, max_pos) = (kw_pos, i) if kw_pos > tmp else (tmp, max_pos)
                break

            # find end words such as PACS, DOI
            end_pos = len(t)
            for ew in end_words:
                tmp = t.find(ew)
                if (tmp > -1):
                    end_pos = tmp

            if kw_pos > -1:
                fw_len = len(find_words[max_pos])
                if self._debug: print('... source: {}'.format(t[kw_pos+fw_len:]))

                sep = ' '
                sep_pos = 100
                for s in sep_words:
                    tmp = t[kw_pos+fw_len:end_pos].find(s)
                    if (tmp > -1) and (tmp < sep_pos):
                        sep_pos = tmp
                        sep = s

                kws = t[kw_pos+fw_len:end_pos].split(sep)
                kws = [x.strip() for x in kws]

                kws = set(kws) - set(ban_words)
                if self._debug: print('... text: {} sep: {} kw_pos: {} end_pos: {}'.format(kws, sep, kw_pos, end_pos))

                res.extend(list(kws))

                break

        self._keywords = list(set(res))
        return self._keywords

    def update_metadata(self):
        """ update meta data using exiftool """

        self._set_meta('Author', self._author)
        self._set_meta('DOI', self._doi)
        self._set_meta('Title', self._title)
        self._set_meta('Keywords', self._keywords)

    def _set_meta(self, tagname, value):
        if (self._exif.getTag(tagname) is None) and (value != ''):
            self._exif.setTag(tagname, value)


def get_bib(doi, asDict=True):
    """ get bib from crossref.org and arXiv.org """

    found = False

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
        bib = r.content
        bib = str(bib, "utf-8")

    if not found:
        return found, ""

    if asDict:
        parser = BibTexParser(common_strings=True)
        parser.ignore_nonstandard_types = False
        parser.homogenise_fields = False

        bdb = bibtexparser.loads(bib, parser)
        entry = bdb.entries[0]

        return found, entry
    else:
        return found, bib

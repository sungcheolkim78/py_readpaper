"""
py_readpaper.py
"""

import os
import requests

from arxiv2bib import arxiv2bib
from pyexif import pyexif

# pdf text reader
from pdf_reader import convertPDF_pdfminer
from pdf_reader import convertPDF_xpdf
from pdf_reader import countPDFPages
from pdf_reader import openPDF

# summary or keyword generator
from gensim.summarization import keywords
from gensim.summarization import summarize
from rake_nltk import Rake

# bibtex parser
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
        self._dictTags = self._exif.getDictTags()

        self._doi = ''
        self._bib = None
        self._year = None
        self._author = ''
        self._journal = ''
        self._title = ''
        self._abstract = None
        self._keywords = None

        # automatic extraction
        self._doi = self.doi()
        self._bib = self.bibtex()
        self._keywords = self.keywords()
        if ("Description" in self._dictTags) and (self._abstract is None):
            self._abstract = self._dictTags["Description"]

    def __repr__(self):
        """ print out basic informations """

        msg = "- Filename: {}\n".format(self._fname)
        msg = msg + "- Title: {}\n".format(self._title)
        msg = msg + "- Author: {}\n".format(self._author)
        msg = msg + "- Year: {}\n".format(self._year)
        msg = msg + "- DOI: {}\n".format(self._doi)
        msg = msg + "- Journal: {}\n".format(self._journal)
        msg = msg + "- Keywords: {}\n".format(self._keywords)
        msg = msg + "- Abstract: {}\n".format(self._abstract)

        return msg

    def open(self):
        """ open in mac """

        openPDF(self._fname)

    def keywords_gensim(self, texts=None, words=10, **kwargs):
        """ extract keywords using gensim """

        if texts is None:
            texts = self.contents(split=False, **kwargs)
        if isinstance(texts, list):
            texts = [ x.strip() for x in texts ]
            texts = ' '.join(texts)

        res = keywords(texts, words=words, lemmatize=True, split=True)
        return res

    def keywords_rake_nltk(self, texts=None, words=10, **kwargs):
        """ extract keywords using rake_nltk """

        r = Rake()
        if texts is None:
            texts = self.contents(**kwargs)

        if isinstance(texts, list):
            r.extract_keywords_from_sentences(texts)
        else:
            r.extract_keywords_from_text(texts)

        res = r.get_ranked_phrases()
        return res[:words]

    def contents(self, sentenceLength=10, split=True, maxpages=-1, clean=False, method='xpdf'):
        """ extract only contents or filter out short sentences """

        if maxpages > -1:
            if method == 'xpdf':
                self._text = convertPDF_xpdf(self._fname, maxpages=maxpages, update=True)
            else:
                self._text = convertPDF_pdfminer(self._fname, maxpages=maxpages)

        if clean:
            cleanlist = list("()\.,?!@#$%^&")
        else:
            cleanlist = ['']

        res = []
        for t in self._text:
            if len(t) < sentenceLength:
                continue

            # clean characters
            for c in cleanlist:
                t = t.replace(c, '')

            res.append(t)

        if split:
            return res
        else:
            return ''.join(res)

    def head(self, n=10, linenumber=True):
        """ show head of texts from paper """

        for i in range(n):
            print("{} {}".format(i, self._text[i]))

    def abstract(self, text=None):
        """ extract or set abstract information """

        if text is None:
            return self._abstract

        if self._abstract is None:
            self._abstract = text
            return self._abstract
        else:
            yesno = input("Will you change [Abstract] from\n\n{}\n\nto\n\n{}\n\n(Yes/No)?".format(self._abstract, text))
            if yesno in ['Yes', 'yes', 'Y', 'y']:
                self._abstract = text

            return self._abstract

    def doi(self, doi=""):
        """ find doi from text or set doi """

        # check self value
        if len(self._doi) > 0:
            if self._debug: print('... read from self._doi')
            return self._doi

        # check exif
        exif_doi = self._exif.getTag('DOI')
        if exif_doi is not None:
            self._doi = exif_doi
            if self._debug: print('... read from exif doi')
            return exif_doi

        # check pdf text - read through all lines
        text_doi = ""
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
                text_doi = t[arxiv_pos:end_pos]
                break

            # 10.XXXX
            if t[:3].lower() == "10.":
                text_doi = t[0:t.find(" ")]
                break

        if text_doi.find(" ") > -1:
            text_doi = text_doi.split(' ')[0]

        if text_doi != "":
            if self._debug: print('... read from text doi')
            self._doi = text_doi

        if (self._doi == "") and (doi != ""): self._doi = doi

        return self._doi

    def bibtex(self, doi=""):
        """ find bibtex information based on doi """

        if self._bib is not None:
            return self._bib

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
            if 'booktitle' in bib:
                self._journal = bib['booktitle']
            if 'abstract' in bib:
                self._abstract = bib['abstract'].replace('\n', ' ')
                self._bib['abstract'] = self._abstract
            if 'keywords' in bib:
                self._keywords = bib['keywords']
        else:
            print('... not found bib information')

        return self._bib

    def keywords(self, kws=None, keywordlist=None):
        """ find keywords from text """

        userkws = False
        if kws is not None:
            if not isinstance(kws, list):
                print('... keywords should be list. {}'.format(kws))
                return []
            else:
                userkws = True

        res = []

        # check self value
        self_kws = self._keywords

        # check exif values
        exif_kws = self._exif.getTag('Keywords')

        # check file text
        if keywordlist is None:
            find_words = ["keywords--", "keywords-", "keywords:", "keywords.", "key words", "keywortlf", "keywords"]
        else:
            find_words = keywordlist

        end_words = ["PACS", "DOI"]
        sep_words = [",", ";", ".", "/"]
        ban_words = [""]
        text_kws = None

        for t in self._text:
            # remove non-text characters
            t = t.strip('\n\r').replace("·", "").replace("Æ", "").replace("Á", "")

            # find keyword
            kw_pos = -1; max_pos = 0

            for i, fw in enumerate(find_words):
                tmp = t.lower().find(fw)
                (kw_pos, max_pos) = (kw_pos, i) if kw_pos > tmp else (tmp, max_pos)
                if tmp > -1: break

            # find end words such as PACS, DOI
            end_pos = len(t)

            for ew in end_words:
                tmp = t.find(ew)

                if (tmp > -1):
                    end_pos = tmp

            # extract keywords
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

                text_kws = t[kw_pos+fw_len:end_pos].split(sep)
                text_kws = [x.strip() for x in text_kws]

                text_kws = set(text_kws) - set(ban_words)
                if self._debug: print('... text: {} sep: {} kw_pos: {} end_pos: {}'.format(kws, sep, kw_pos, end_pos))

                break

        if self._debug: print('self: {}'.format(self_kws))
        if self._debug: print('exif: {}'.format(exif_kws))
        if self._debug: print('text: {}'.format(text_kws))

        if self_kws is not None: res.extend(self_kws)
        if exif_kws is not None: res.extend(exif_kws)
        if text_kws is not None: res.extend(text_kws)
        if userkws: res.extend(kws)

        self._keywords = sorted(list(set(res)))

        return self._keywords

    def update_metadata(self, force=False):
        """ update meta data using exiftool """

        self.set_meta('Author', self._author, force=force)
        self.set_meta('DOI', self._doi, force=force)
        self.set_meta('Title', self._title, force=force)
        self.set_meta('Description', self._abstract, force=force)
        self.set_meta('Keywords', self._keywords, force=force)

    def set_meta(self, tagname, value, force=False):
        """ set meta data using exiftool and check previous values """

        # check existance of tag and new values
        tag_value = self._exif.getTag(tagname)
        tag_exist = tag_value is not None
        if isinstance(value, list):
            value_exist = len(value) > 0
        else:
            value_exist = value != ""

        # check similarity between tag and new value
        yesno = 'y'
        if tag_exist and value_exist:
            if tag_value != value:
                yesno = input("Will you change [{}] from \n\n{} to \n\n{}\n\n? (Yes/No)".format(tagname, tag_value, value))
            else:
                if self._debug: print('... set_meta tag {}: values are same'.format(tagname))
                yesno = 'n'

        # set new tag value
        if (yesno in ["Yes", "yes", "y", "Y"]) and value_exist:
            if force or (not tag_exist):
                print('Set [{}] as [{}]'.format(tagname, value))
                self._exif.setTag(tagname, value)

    def rename(self, force=False):
        """ rename pdf file as specific format YEAR-AUTHOR1LASTNAME-JOURNAL """

        ready = 0

        if self._year is not None:
            year = self._year
            ready = ready + 1

        if self._author is not None:
            author = find_author1(self._author)
            ready = ready + 1

        if self._journal is not None:
            journal = self._journal
            ready = ready + 1

        base, fname = os.path.split(os.path.abspath(self._fname))
        new_fname = base + "/{}-{}-{}.pdf".format(year, author.replace('-', '_'), journal.replace(' ', '_'))

        print('... name: {} \nnew name: {}'.format(self._fname, new_fname))
        if ready < 3:
            print('... not ready! check bibtex(), doi() function first.')
            os.exit(1)

        if force:
            yesnno = 'y'
        else:
            yesno = input("Do you really want to change? (Yes/No)")

        if yesno in ["Yes", "y", "Y", "yes"]:
            os.rename(self._fname, new_fname)
            self._fname = new_fname

    def searchtext(self, sstr=None):
        """ search text by search word """

        if sstr is None:
            print('... put search word')
            os.exit(1)

        found = False
        for i, t in enumerate(self._text):
            pos = t.lower().find(sstr.lower())
            if pos > -1:
                print('... [{}] {}'.format(i, t))
                found = True

        return found


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


def find_author1(authors, options='last'):
    """ find first author's name """

    names = authors.split(' and ')

    n1 = names[0]

    if n1.find(',') > -1:
        firstname = ' '.join(n1.split(',')[1:])
        lastname = n1.split(',')[0]
    else:
        firstname = ' '.join(n1.split(' ')[:-1])
        lastname = n1.split(' ')[-1]

    if options == 'last':
        return lastname
    elif options == 'first':
        return firstname
    else:
        return firstname + ', ' + lastname


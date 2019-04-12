"""
py_readpaper.py


TODO: 2019/04/11 - make it fast!
"""

import os
import string
import subprocess

# pdf text reader
from pdf_text import convertPDF_pdfminer
from pdf_text import convertPDF_xpdf
from pdf_text import cleanup_str
from pdf_text import find_author1
from pdf_text import find_keywords
from pdf_text import find_doi

from pdf_meta import get_bib
from pdf_meta import get_pmid
from pdf_meta import crossref_query_title
from pdf_meta import read_bib
from pdf_meta import save_bib

# summary or keyword generator
from gensim.summarization import keywords
from gensim.summarization import summarize
from rake_nltk import Rake

from pyexif import pyexif


class Paper(object):
    """ read paper pdf and extract key informations """

    def __init__(self, filename, debug=False):
        """ initialize Paper class """

        base, fname = os.path.split(os.path.abspath(filename))
        self._fname = fname
        self._base = base
        self._debug = debug

        self._text = None
        self._exif = pyexif.ExifEditor(filename)
        self._dictTags = self._exif.getDictTags()
        self._pages = self._dictTags.get("Page Counts", 0)

        self._doi = self._dictTags['DOI'] if 'DOI' in self._dictTags else None
        self._author = self._dictTags['Author'] if 'Author' in self._dictTags else None
        self._title = self._dictTags['Title'] if 'Title' in self._dictTags else None
        self._keywords = self._dictTags.get('Keywords', [])
        self._abstract = self._dictTags['Description'] if 'Description' in self._dictTags else None
        self._subject = self._dictTags['Subject'] if 'Subject' in self._dictTags else None
        self._pmid = None
        self._pmcid = None
        self._bib = None

        self._year = fname.split('-')[0]
        self._author1 = fname.split('-')[1].replace('_', '-')
        self._journal = ''.join(fname.replace('.pdf', '').split('-')[2:]).replace('_', ' ')

        # automatic extraction
        if self._doi is None:
            self._doi = self.doi()
            self._bib = self.bibtex()
        if len(self._keywords) == 0:
            self._keywords = self.keywords()

    def __repr__(self):
        """ print out basic informations """

        msg = "- Filename: {}\n".format(self._fname)
        msg = msg + "- Title: {}\n".format(self._title)
        msg = msg + "- Author: {}\n".format(self._author)
        msg = msg + "- Year: {}\n".format(self._year)
        msg = msg + "- DOI: {}\n".format(self._doi)
        msg = msg + "- Journal: {}\n".format(self._journal)
        msg = msg + "- Keywords: {}\n".format(self._keywords)
        msg = msg + "- Subject: {}\n".format(self._subject)
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

        if (self._text is None) or (maxpages > -1):
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

        for i, t in enumerate(self.contents()):
            if linenumber:
                print("{} {}".format(i, t))
            else:
                print("{}".format(t))

    def title(self, text=None, update=True):
        """ set / get title """

        if text is None:
            if self._title is not None: return self._title

        if text is not None:
            if self._title == text: return text
            if self._title is None: self._title = text
            if update: self._title = text

    def abstract(self, text=None, update=False):
        """ extract or set abstract information """

        if (text is None) and (self._abstract is not None):
            return self._abstract

        if (text is not None) and (self._abstract is None):
            self._abstract = text
            return self._abstract

        if (text is not None) and (self._abstract is not None):
            if text == self._abstract:
                print('... [Abstract]: same value')
                return self._abstract

            yesno = input("[Abstract] 1 -> 2 \n[1] {}\n[2] {}\nChoose (Yes/No): ".format(self._abstract, text))
            if yesno in ['Yes', 'yes', 'Y', 'y']:
                self._abstract = text

            return self._abstract

    def pmid(self, idstring):
        """ find doi from pmid, pmcid """

        found, result = get_pmid(idstring, debug=self._debug)

        if not found:
            return

        doi = result.get("doi", None)
        pmid = result.get("pmid", None)
        pmcid = result.get("pmcid", None)

        if self._debug: print("doi: {}\npmid: {}\npmcid: {}\n".format(doi, pmid, pmcid))

        if self._doi is not None: self._doi = doi
        if self._pmid is not None: self._doi = pmid
        if self._pmcid is not None: self._doi = pmcid

        return doi, pmid, pmcid

    def doi(self, doi=None):
        """ find doi from text or set doi """

        # check argument
        if doi is not None:
            self._doi = doi
            return self._doi

        # check self value
        if self._doi is not None:
            if self._debug: print('... read from self._doi')
            return self._doi

        # check exif
        exif_doi = self._dictTags.get('DOI', None)
        if exif_doi is not None:
            self._doi = exif_doi
            if self._debug: print('... read from exif doi')
            return self._doi

        # check text
        text_doi = find_doi(self.contents())
        if text_doi is not None:
            self._doi = text_doi
            if self._debug: print('... read from text doi')
            return self._doi

        return self._doi

    def doi_by_title(self, title=None):
        """ set doi by title search """

        if title is None:
            if self._title is None: return
            else: title = self._title

        res = crossref_query_title(title)

        if res['success']:
            if self._debug: print('... found doi by title')

            item = res['result']
            if item['similarity'] > 0.9:
                self._title = item['crossref_title']
                self._doi = item['doi']
                return self._doi

        return None

    def bibtex(self, doi=None, cache=True):
        """ find bibtex information based on doi """

        if self._bib is not None:
            return self._bib

        if self._doi is None:
            self.doi(doi=doi)
        if self._doi is None:
            return self._bib

        # check bib file
        bibfname = self._base + '/.' + self._fname.replace('.pdf', '.bib')
        if cache and os.path.exists(bibfname):
            bib = read_bib(bibfname)
            found = True
        else:
            found, bib = get_bib(self._doi, filename=bibfname)

        # update information
        if found and isinstance(bib, dict):
            self._bib = bib

            self._author = bib.get('author', None)
            self._title = cleanup_str(bib.get('title', None))
            self._year = bib.get('year', None)
            self._keywords = bib.get('keywords', [])
            if 'journal' in bib:
                self._journal = cleanup_str(bib['journal'])
            elif 'archiveprefix' in bib:
                self._journal = bib['archiveprefix']
            elif 'booktitle' in bib:
                self._journal = bib['booktitle']

            if 'abstract' in bib:
                self._abstract = bib['abstract'].replace('\n', ' ')
                self._bib['abstract'] = self._abstract

            self._subject = '{}, ({}), doi: {}'.format(self._journal, self._year, self._doi)

        else:
            if self._debug: print('... not found bib information')
            self._bib = None

        return self._bib

    def keywords(self, kws=None, keywordlist=None, update=False):
        """ find keywords from text """

        # check argument values
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
        exif_kws = self._dictTags.get('Keywords', [])

        # check file text
        text_kws = find_keywords(self.contents(), keywordlist=keywordlist, debug=self._debug)

        if self._debug: print('self: {}'.format(self_kws))
        if self._debug: print('exif: {}'.format(exif_kws))
        if self._debug: print('text: {}'.format(text_kws))

        if not update:
            if len(self_kws) > 0: res.extend(self_kws)
            if len(exif_kws) > 0: res.extend(exif_kws)
        if len(text_kws) > 0: res.extend(text_kws)
        if userkws: res = kws

        self._keywords = sorted(list(set([cleanup_str(w) for w in res])))
        return self._keywords

    def update_metadata(self, force=False):
        """ update meta data using exiftool """

        self.set_meta('Author', self._author, force=force)
        self.set_meta('DOI', self._doi, force=force)
        self.set_meta('Title', self._title, force=force)
        summary = '{}, ({}), doi: {}'.format(self._journal, self._year, self._doi)
        self.set_meta('Subject', summary, force=force)
        self.set_meta('Description', self._abstract, force=force)
        self.set_meta('Keywords', self._keywords, force=force)

    def update(self, force=False):
        """ clean up all information on pdf file """

        if self._doi is None:
            print('[Filename] {}\n[Title] {}\n[Author] {}\n[Year] {}\n[Journal] {}\n'.format(self._fname, self._title, self._author, self._year, self._journal))

            if not force:
                # ask title
                user_title = input('input title: (skip) ')
                if user_title not in ["s", "S", "skip", "Skip"]:
                    self._title = user_title

                search_result = crossref_query_title(self._title)
                print('... crossref search found: {}'.format(search_result['success']))

                if search_result['result']['similarity'] > 0.9:
                    self._doi = search_result['result']['doi']
                    self._title = search_result['result']['crossref_title']

            if self._doi is not None: self.bibtex()

            # if bib information is not found
            if self._bib is None: return

        self.update_metadata(force=force)
        self.rename(force=force)

    def set_meta(self, tagname, value, force=False, cleanup=True):
        """ set meta data using exiftool and check previous values """

        # check existance of tag and new values
        tag_value = self._dictTags.get(tagname)
        tag_exist = tag_value is not None
        if isinstance(value, list):
            value_exist = len(value) > 0
            value = set([cleanup_str(v) for v in value]) if cleanup else set(value)
            tag_value = set(tag_value) if isinstance(tag_value, list) else tag_value
        else:
            value_exist = value != ""

        if isinstance(value, str):
            value_exist = value != ''
            value = cleanup_str(value) if cleanup else value

        # check similarity between tag and new value
        yesno = 'y'
        if tag_exist and value_exist:
            if tag_value != value:
                if force:
                    yesno = 'y'
                else:
                    yesno = input("[{}] 1 -> 2 \n[1] {} \n[2] {}\nChoose (Yes/No) ".format(tagname, tag_value, value))
            else:
                if self._debug: print('... update tag [{}]: same values'.format(tagname))
                yesno = 'n'

        # set new tag value
        if (yesno in ["Yes", "yes", "y", "Y"]) and value_exist:
            if self._debug: print('Set [{}] as [{}]'.format(tagname, value))
            try:
                value = list(value) if isinstance(value, set) else value
                self._exif.setTag(tagname, value)
            except:
                print('... exiftool error')

        self._exif = pyexif.ExifEditor(self._fname)
        self._dictTags = self._exif.getDictTags()

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

        if ready < 3:
            print('... not ready! check bibtex(), doi() function first.')
            return

        base, fname = os.path.split(os.path.abspath(self._fname))
        new_fname = "{}-{}-{}.pdf".format(year, author.replace('-', '_'), journal.replace(' ', '_'))

        if fname == new_fname:
            if self._debug: print('... same name: {}'.format(fname))
            return

        print('... name: {} \nnew name: {}'.format(fname, new_fname))

        if force:
            yesno = 'y'
        else:
            yesno = input("Do you really want to change? (Yes/No)")

        if yesno in ["Yes", "y", "Y", "yes"]:
            os.rename(self._fname, base + '/' + new_fname)
            self._fname = base + '/' + new_fname

    def searchtext(self, sstr):
        """ search text by search word """

        found = False
        for i, t in enumerate(self.contents()):
            pos = t.lower().find(sstr.lower())
            if pos > -1:
                print('... [{}] {}'.format(i, t))
                found = True

        return found


def openPDF(filename):
    """ open pdf file in macos """

    # Determines location of file
    if os.path.isabs(filename):
        abs_loc = filename
    else:
        cd = os.getcwd()
        abs_loc = os.path.join(cd, filename)

    cmd = ['Open', abs_loc]
    output = subprocess.check_output(cmd)


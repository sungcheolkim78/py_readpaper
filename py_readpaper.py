"""
py_readpaper.py

holder for Paper object and related functions

TODO: 2019/04/11 - make it fast!
TODO: 2019/04/14 - make clear concept layer
"""

import os
import glob
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
from pdf_meta import find_bib
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
        self._exif = pyexif.ExifEditor(os.path.join(base, fname))
        self._dictTags = self._exif.getDictTags()
        self._bib = self.exif_to_bib()

        year = fname.split('-')[0]
        self._update_bibitem('year', new_value=int(year))

        journal = ''.join(fname.replace('.pdf', '').split('-')[2:]).replace('_', ' ')
        self._update_bibitem('journal', new_value=journal)

        self._bib['fauthor1'] = fname.split('-')[1].replace('_', '-')

    def __repr__(self):
        """ print out basic informations """

        msg = "- Filename: {}\n".format(self._fname)
        msg = msg + "- Title: {}\n".format(self._bib.get('title'))
        msg = msg + "- Author: {}\n".format(self._bib.get('author'))
        msg = msg + "- Year: {}\n".format(self._bib.get('year'))
        msg = msg + "- DOI: {}\n".format(self._bib.get('doi'))
        msg = msg + "- Journal: {}\n".format(self._bib.get('journal'))
        msg = msg + "- Keywords: {}\n".format(self._bib.get('keywords'))
        msg = msg + "- Subject: {}\n".format(self._bib.get('subject'))
        msg = msg + "- Abstract: {}\n".format(self._bib.get('abstract'))

        return msg

    def open(self):
        """ open in mac """

        openPDF(os.path.join(self._base, self._fname))

    # metadata related functions

    def exif_to_bib(self):
        """ create bib file from current exif paper info """

        # check Subject item (journal, year, doi)
        subject = self._dictTags.get('Subject', '')
        try:
            journal, year, _ = subject.split(', ')
            year = int(year[1:-1])
        except:
            journal = ''
            year = 0

        # check publicationDate
        publicationDate = self._dictTags.get('PublicationDate', '')
        # TODO - convert to year and month

        # check doi
        dois = self._dictTags.get('DOI', '')
        dois = str(dois)
        doi = dois[4:] if dois[:4] == 'doi:' else dois
        if dois[:6] == 'arxiv:':  doi = dois[6:]
        pmid = dois[5:] if dois[:5] == 'pmid:' else ''
        pmcid = dois[6:] if dois[:6] == 'pmcid:' else ''

        # check author
        author1 = find_author1(self._dictTags.get('Author')) if self._dictTags.get('Author', '') != '' else ''

        bib_dict = {'author': self._dictTags.get('Author', ''),
                'author1': author1,
                'local-url': "./"+self._dictTags.get('FileName', ''),
                'url': self._dictTags.get('URL', ''),
                'title': self._dictTags.get('Title', ''),
                'abstract': self._dictTags.get('Description', ''),
                'keywords': self._dictTags.get('Keywords', []),
                'publisher': self._dictTags.get('Publisher', ''),
                'journal': journal,
                'year': year,
                'doi': doi,
                'pmid': pmid,
                'pmcid': pmcid,
                'ID': '{}_{}'.format(author1, year),
                'ENTRYTYPE': 'article'
                }

        for k, i in bib_dict.items():
            if i == 'None': bib_dict[k] = ''

        return bib_dict

    def bib_to_exif(self, bibdict, force=False):
        """ update meta data using exiftool """

        doi = ''
        if bibdict.get('pmid', '') != '': doi = 'pmid:{}'.format(bibdict.get('pmid'))
        if bibdict.get('pmcid', '') != '': doi = 'pmcid:{}'.format(bibdict.get('pmcid'))
        if bibdict.get('doi', '') != '': doi = 'doi:{}'.format(bibdict.get('doi'))

        if doi != '': self._set_meta('DOI', doi, force=force)

        self._set_meta('Author', bibdict.get('author', ''), force=force)
        self._set_meta('URL', bibdict.get('url', ''), force=force)
        self._set_meta('Title', bibdict.get('title', ''), force=force)
        self._set_meta('Description', bibdict.get('abstract', ''), force=force)
        self._set_meta('Keywords', bibdict.get('keywords', []), force=force)
        self._set_meta('Publisher', bibdict.get('publisher', ''), force=force)

        summary = '{}, ({}), doi: {}'.format(bibdict.get('journal',''), bibdict.get('year',0), bibdict.get('doi',''))
        self._set_meta('Subject', summary, force=force)

    def title(self, text=None):
        """ set / get title """

        if isinstance(text, int):
            text = self.contents()[text]
            text = text.strip('\n\r')

        return self._update_bibitem('title', new_value=text)

    def abstract(self, text=None):
        """ extract or set abstract information """

        if isinstance(text, int):
            text = self.contents()[text]
            text = text.replace("ABSTRACT", "").strip()

        return self._update_bibitem('abstract', new_value=text)

    def author(self, text=None):
        """ set / get author """

        if isinstance(text, int):
            text = self.contents()[text]

        return self._update_bibitem('author', new_value=text)

    def bib(self, bib=None):
        """ set / get bibtex item """

        if bib is None:
            return self._bib
        else:
            for k, i in bib.items():
                self._update_bibitem(k, new_value=i)
            return self._bib

    def doi(self, doi=None, checktitle=False):
        """ find doi from text or set doi """

        # check argument
        if doi is not None:
            self._update_bibitem('doi', new_value=doi)
            return doi

        # search by text
        if checktitle:
            res = self.download_doi()
            if res != '':
                if self._debug: print('... download by title')
                self._update_bibitem('doi', new_value=res)
                return res

        # check self value
        if self._bib.get('doi', '') != '':
            if self._debug: print('... read from self._bib')
            return self._bib.get('doi')

        # check text
        text_doi = find_doi(self.contents())
        if text_doi is not None:
            self._update_bibitem('doi', new_value=text_doi)
            if self._debug: print('... read from text doi')
            return text_doi

        return self._bib.get('doi', '')

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
        self_kws = self._bib.get('keywords', [])

        # check file text
        text_kws = find_keywords(self.contents(), keywordlist=keywordlist, debug=self._debug)

        if self._debug: print('self: {}'.format(self_kws))
        if self._debug: print('text: {}'.format(text_kws))

        if not update:
            if len(self_kws) > 0: res.extend(self_kws)
        if len(text_kws) > 0: res.extend(text_kws)
        if userkws: res = kws

        self._update_bibitem('keywords', new_value=(list(set([cleanup_str(w) for w in res]))))
        return self._bib.get('keywords', [])

    def download_bib(self, doi=None, cache=True):
        """ find bibtex information based on doi """

        if self._bib.get('doi', '') == '':
            doi = self.doi(doi=doi)
        if self._bib.get('doi', '') == '':
            print('... no doi')
            return self._bib

        # check bib file
        bibfname = self._base + '/.' + self._fname.replace('.pdf', '.bib')
        if cache and os.path.exists(bibfname):
            bib = read_bib(bibfname)
            found = True
        else:
            found, bib = get_bib(self.doi(), filename=bibfname)

        # update information
        if found and isinstance(bib, dict):
            for k, i in bib.items():
                self._update_bibitem(k, new_value=i)

            #self.bib_to_exif(bib)
            save_bib([self._bib], bibfname)
        else:
            if self._debug:
                print('... not found bib information')

        return self._bib

    def download_pmid(self, idstring):
        """ find doi from pmid, pmcid """

        found, result = get_pmid(idstring, debug=self._debug)

        if not found:
            return

        if result.get('doi', '') != '': self._update_bibitem('doi', new_value=result.get('doi'))
        if result.get('pmid', '') != '': self._update_bibitem('pmid', new_value=result.get('pmid'))
        if result.get('pmcid', '') != '': self._update_bibitem('pmcid', new_value=result.get('pmcid'))

        if self._debug: print("doi: {}\npmid: {}\npmcid: {}\n".format(doi, pmid, pmcid))

        return doi, pmid, pmcid

    def download_doi(self, title=None):
        """ set doi by title search """

        if title is None:
            if self._bib.get('title', '') == '': return ''
            else: title = self._bib.get('title')

        res = crossref_query_title(title)

        if res['success']:
            if self._debug: print('... found doi by title')

            item = res['result']
            if item['similarity'] > 0.9:
                self._update_bibitem('title', new_value=item['crossref_title'])
                self._update_bibitem('doi', new_value=item['doi'])
                return item['doi']

        return ''

    def search_bib(self, bibdb=None, subset=['year', 'journal']):
        """ using bib item list find bib information """

        if bibdb is None:
            bibdb = []
            biblist = glob.glob('*.bib')
            for f in biblist:
                a = read_bib(f)
                if isinstance(a, list):
                    bibdb = bibdb.extend(a)
                else:
                    bibdb = bibdb.append(a)

        if bibdb is not None:
            res = find_bib(bibdb, self.bib(), subset=subset)
            if len(res) == 0:
                print('... not found')
            if len(res) == 1:
                print('... set by found')
                self.bib(bib=res[0])
            if len(res) > 1:
                print('... multiple found: {}'.format(len(res))
                for i, item in enumerate(res):
                    print("[{}] {}\n".format(i, item))

                number = input("Choose number (or quit): ")
                if number in ['quit', 'q', 'Q']:
                    return
                self.bib(bib=res[int(number)])

    # text analysis

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
                self._text = convertPDF_xpdf(os.path.join(self._base, self._fname), maxpages=maxpages, update=True)
            else:
                self._text = convertPDF_pdfminer(os.path.join(self._base, self._fname), maxpages=maxpages)

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

    def searchtext(self, sstr):
        """ search text by search word """

        found = False
        for i, t in enumerate(self.contents()):
            pos = t.lower().find(sstr.lower())
            if pos > -1:
                print('... [{}] {}'.format(i, t))
                found = True

        return found

    # clean up metadata

    def update(self, force=False):
        """ clean up all information on pdf file """

        if self.doi() == '':
            self.doi(checktitle=True)

        if self._bib.get('pmid','') != '': self.download_pmid(self._bib.get('pmid'))
        if self._bib.get('pmcid','') != '': self.download_pmid(self._bib.get('pmcid'))

        if self._bib.get('doi', '') != '':
            self.download_bib()

        self.bib_to_exif(self._bib, force=force)
        self.rename()

    def rename(self):
        """ rename pdf file as specific format YEAR-AUTHOR1LASTNAME-JOURNAL """

        ready = 0

        try:
            year = self._bib.get('year')
            author = find_author1(self._bib.get('author'))
            journal = self._bib.get('journal')
        except:
            print('... either year, author1, journal information is missing!')
            return

        new_fname = "{}-{}-{}.pdf".format(year, author.replace('-', '_'), journal.replace(' ', '_'))

        if self._fname == new_fname:
            if self._debug: print('... same name: {}'.format(self._fname))
            return

        print('... name: {} \nnew name: {}'.format(self._fname, new_fname))

        yesno = input("Do you really want to change? (Yes/No)")

        if yesno in ["Yes", "y", "Y", "yes"]:
            os.rename(os.path.join(self._base, self._fname), os.path.join(self._base, new_fname))
            self._fname = new_fname
            self._update_bibitem("local-url", new_value="./" + new_fname)

    def _set_meta(self, tagname, value, force=False, cleanup=True):
        """ set meta data using exiftool and check previous values """

        # check existance of tag and new values
        tag_value = self._dictTags.get(tagname, '')
        tag_exist = tag_value != ''

        # check keywords
        if isinstance(value, list):
            value_exist = len(value) > 0
            value = set([cleanup_str(v) for v in value]) if cleanup else set(value)
            tag_value = set(tag_value) if isinstance(tag_value, list) else tag_value
        else:
            value_exist = value != ''

        if isinstance(value, str):
            value_exist = value != ''
            value = cleanup_str(value) if cleanup else value

        # check similarity between tag and new value
        yesno = 'y'
        if value_exist:
            if tag_value == '': yesno = 'y'
            elif tag_value != value:
                if force: yesno = 'y'
                else:
                    yesno = input("[{}] 1 -> 2 \n[1] {} \n[2] {}\nChoose (Yes/No) ".format(tagname, tag_value, value))
            else:
                if self._debug: print('... update tag [{}]: same values'.format(tagname))
                yesno = 'n'

        # set new tag value
        if (yesno in ["Yes", "yes", "y", "Y"]) and value_exist:
            try:
                value = list(value) if isinstance(value, set) else value
                self._exif.setTag(tagname, value)
                print('... save exif tag [{}] to {}'.format(tagname, self._fname))
            except:
                print('... exiftool error')

        self._exif = pyexif.ExifEditor(os.path.join(self._base, self._fname))
        self._dictTags = self._exif.getDictTags()

    def _update_bibitem(self, colname, new_value=None):
        """ set / get bib item """

        #if colname == "ID": return self._bib.get(colname, '')

        if (new_value is not None):
            old_value = self._bib.get(colname, '')
            if colname == 'year':
                old_value = int(old_value)
                new_value = int(new_value)

            if old_value == new_value:
                if self._debug: print('... [{}]: same value {}'.format(colname, new_value))
                return new_value

            if (old_value == 'None') or (old_value == ''):
                self._bib[colname] = new_value
                return new_value

            if (new_value == 'None') or (new_value == ''):
                return old_value

            yesno = input("[{}] 1 -> 2 \n[1] {}\n[2] {}\nChoose (Yes/No): ".format(colname, old_value, new_value))
            if yesno in ['Yes', 'yes', 'Y', 'y']:
                self._bib[colname] = new_value

        return self._bib.get(colname, '')


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


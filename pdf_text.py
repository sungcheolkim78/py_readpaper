"""
Functions for PDF parsing tools and utils
"""

import io
import re
import os
import urllib
import subprocess
import string

from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.converter import TextConverter
from pdfminer.layout import LAParams
from pdfminer.pdfpage import PDFPage


def convertPDF_pdfminer(pdf_path, codec='utf-8', maxpages=0):
    """
    Takes path to a PDF and returns the text inside it as string

    pdf_path: string indicating path to a .pdf file. Can also be a URL starting
              with 'http'
    codec: can be 'ascii', 'utf-8', ...
    returns string of the pdf, as it comes out raw from PDFMiner
    """

    if pdf_path[:4] == 'http':
        print('first downloading %s ...' % (pdf_path,))
        urllib.urlretrieve(pdf_path, 'temp.pdf')
        pdf_path = 'temp.pdf'

    rsrcmgr = PDFResourceManager()
    retstr = io.StringIO()
    laparams = LAParams()
    device = TextConverter(rsrcmgr, retstr, codec=codec, laparams=laparams)

    fp = open(pdf_path, 'rb')
    interpreter = PDFPageInterpreter(rsrcmgr, device)
    password = ""
    caching = True
    pagenos = set()

    for page in PDFPage.get_pages(fp, pagenos, maxpages=maxpages, password=password, caching=caching, check_extractable=True):
        interpreter.process_page(page)

    text = retstr.getvalue()

    fp.close()
    device.close()
    retstr.close()

    text = text.split('\n')
    text = [ t+'\n' for t in text ]
    return text


def convertPDF_xpdf(pdf_path, codec='utf-8', maxpages=0, update=False):
    """ convert PDF to text using pdftotext """

    base, fname = os.path.split(os.path.abspath(pdf_path))
    txt_path = base + '/.' + fname.replace('.pdf', '.txt')
    #print('... save to {}'.format(txt_path))

    if (not update) and os.path.exists(txt_path):
        text = open(txt_path, 'r').readlines()
        return text

    try:
        # use pdftotext to extract text from pdf
        # -clip : separate clipped text
        #subprocess.call(['pdftotext', '-l', str(maxpages), '-clip', '-enc', codec.upper(), pdf_path, txt_path])
        subprocess.call(['pdftotext', '-l', str(maxpages), '-enc', codec.upper(), pdf_path, txt_path])
        text = open(txt_path, 'r').readlines()
        return text

    except:
        if os.path.exists(txt_path): os.remove(txt_path)
        return convertPDF_pdfminer(pdf_path, codec=codec, maxpages=maxpages)


def countPDFPages(filename):
    ''' Counts number of pages in PDF '''

    # NOTE: Currently does not work 100% of the time
    rxcountpages = re.compile(r"/Type\s*/Page([^s]|$)", re.MULTILINE|re.DOTALL)
    data = open(filename,"r", encoding = "ISO-8859-1").read()
    return len(rxcountpages.findall(data))


def cleanup_str(value):
    """ choose only selected characters """

    SPECIAL_CHARS = '_- /.,():{}'
    PERMITTED_CHARS = string.digits + string.ascii_letters + SPECIAL_CHARS

    if isinstance(value, str):
        res = "".join(c for c in value if c in PERMITTED_CHARS)
        return res
    else:
        return str(value)


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


def find_doi(lines):
    """ find doi in pdf text lines """

    # check pdf text - read through all lines
    text_doi = ""

    for t in lines:
        t = t.strip('\n\r')

        # check doi
        doi_pos = t.lower().find("doi")
        if doi_pos > -1:
            if t[doi_pos:doi_pos+4].lower() == "doi:":
                text_doi = t[doi_pos+4:].lstrip()
                if text_doi[:3] == "10.": break
            elif t[doi_pos:doi_pos+4].lower() == "doi ":
                text_doi = t[doi_pos+4:].lstrip()
                if text_doi[:3] == "10.": break
            elif t.find("/", doi_pos) > -1:
                text_doi = t[t.find("/", doi_pos)+1:]
                if text_doi[:3] == "10.": break

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

    # check trailing words
    if text_doi.find(" ") > -1:
        text_doi = text_doi.split(' ')[0]
    if text_doi.find("]") > -1:
        text_doi = text_doi.split(' ')[0]
    if (len(text_doi) > 0) and (text_doi[-1] == '.'):
        text_doi = text_doi[:-1]

    if text_doi == '': return None
    return text_doi


def find_keywords(lines, keywordlist=None, debug=False):
    """ find keywords from text """

    # check file text
    if keywordlist is None:
        find_words = ["keywords--", "keywords-", "keywords:", "keywords.", "key words", "keywortlf", "keywords"]
    else:
        find_words = keywordlist

    end_words = ["PACS", "DOI"]
    sep_words = [",", ";", ".", "/"]
    ban_words = [""]

    text_kws = []
    found_idx = -1
    found_pos = -1

    for i, t in enumerate(lines):
        # remove non-text characters
        t = cleanup_str(t)

        # find keyword
        for fw in find_words:
            tmp = t.lower().find(fw)
            if tmp > -1:
                found_idx = i
                found_pos = tmp + len(fw)
                break

        if found_idx > -1:
            break

    if found_idx == -1:
        if debug: print('... keywords not found!')
        return []

    # extract keywords
    t = lines[found_idx]

    # find end words such as PACS, DOI
    end_pos = len(t)

    for ew in end_words:
        tmp = t.find(ew)
        if (tmp > -1): end_pos = tmp

    if debug: print('... line [{}]: {}'.format(found_idx, t[found_pos:end_pos]))

    sep = ' '
    sep_pos = 100
    for s in sep_words:
        tmp = t[found_pos:end_pos].find(s)

        if (tmp > -1) and (tmp < sep_pos):
            sep_pos = tmp
            sep = s

    text_kws = t[found_pos:end_pos].split(sep)
    text_kws = [x.strip() for x in text_kws]

    text_kws = set(text_kws) - set(ban_words)
    if debug: print('... sep: {} found_pos: {} end_pos: {}'.format(sep, found_pos, end_pos))

    return text_kws

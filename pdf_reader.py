"""
Functions for PDF parsing tools and utils
"""

import io
import re
import os
import urllib
import subprocess

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

    for page in PDFPage.get_pages(fp, pagenos, maxpages=maxpages,
                                  password=password,
                                  caching=caching,
                                  check_extractable=True):
        interpreter.process_page(page)

    text = retstr.getvalue()

    fp.close()
    device.close()
    retstr.close()

    return text


def convertPDF_xpdf(pdf_path, codec='utf-8', maxpages=0, update=False):
    """ convert PDF to text using pdftotext """

    txt_path = pdf_path.replace('.pdf', '.txt')
    #print('... save to {}'.format(txt_path))

    if (not update) and os.path.exists(txt_path):
        text = open(txt_path, 'r', encoding=codec).readlines()
        return text

    # use pdftotext to extract text from pdf
    # -clip : separate clipped text
    subprocess.call(['pdftotext', '-l', str(maxpages), '-clip', '-enc', codec.upper(), pdf_path, txt_path])

    try:
        text = open(txt_path, 'r', encoding=codec).readlines()
        return text
    except:
        os.remove(txt_path)
        return convertPDF_pdfminer(pdf_path, codec=codec, maxpages=maxpages)



def countPDFPages(filename):
    ''' Counts number of pages in PDF '''

    # NOTE: Currently does not work 100% of the time
    rxcountpages = re.compile(r"/Type\s*/Page([^s]|$)", re.MULTILINE|re.DOTALL)
    data = open(filename,"r", encoding = "ISO-8859-1").read()
    return len(rxcountpages.findall(data))


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


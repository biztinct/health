#!/usr/bin/env python3
"""Open the manual in LibreOffice via UNO, refresh the Table of Contents
(and all fields), then export to PDF — so the TOC arrives populated with
real page numbers.

Starts its own headless soffice on a TCP socket and connects with retries
(more deterministic than officehelper.bootstrap). Run with LibreOffice's
bundled python:

  /Applications/LibreOffice.app/Contents/Resources/python export_pdf.py
"""
import os
import subprocess
import sys
import time

import uno
from com.sun.star.beans import PropertyValue

HERE = os.path.dirname(os.path.abspath(__file__))
DOCX = os.path.join(HERE, 'VietUC_CMS_User_Manual.docx')
PDF = os.path.join(HERE, 'VietUC_CMS_User_Manual.pdf')
SOFFICE = '/Applications/LibreOffice.app/Contents/MacOS/soffice'
PORT = 2002


def pv(name, value):
    p = PropertyValue()
    p.Name = name
    p.Value = value
    return p


def url(path):
    return 'file://' + path


def connect():
    localContext = uno.getComponentContext()
    resolver = localContext.ServiceManager.createInstanceWithContext(
        'com.sun.star.bridge.UnoUrlResolver', localContext)
    conn = ('uno:socket,host=localhost,port=%d;urp;'
            'StarOffice.ComponentContext' % PORT)
    last = None
    for _ in range(60):
        try:
            return resolver.resolve(conn)
        except Exception as e:  # NoConnectException until soffice is up
            last = e
            time.sleep(1)
    raise RuntimeError('Could not connect to soffice: %s' % last)


def main():
    proc = subprocess.Popen([
        SOFFICE, '--headless', '--invisible', '--nologo', '--norestore',
        '--nofirststartwizard',
        '--accept=socket,host=localhost,port=%d;urp;' % PORT,
    ])
    try:
        ctx = connect()
        print('connected')
        smgr = ctx.ServiceManager
        desktop = smgr.createInstanceWithContext('com.sun.star.frame.Desktop', ctx)
        doc = desktop.loadComponentFromURL(url(DOCX), '_blank', 0, (pv('Hidden', True),))
        print('loaded')
        indexes = doc.getDocumentIndexes()
        for i in range(indexes.getCount()):
            indexes.getByIndex(i).update()
        try:
            doc.refresh()
            doc.getTextFields().refresh()
        except Exception:
            pass
        print('toc updated (%d indexes)' % indexes.getCount())
        doc.storeToURL(url(PDF), (pv('FilterName', 'writer_pdf_Export'),))
        doc.close(False)
        print('Exported', PDF)
        try:
            desktop.terminate()
        except Exception:
            pass
    finally:
        try:
            proc.terminate()
        except Exception:
            pass


if __name__ == '__main__':
    main()

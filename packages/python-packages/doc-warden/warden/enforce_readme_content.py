# ------------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project 
# root for license information.
# ------------------------------------------------------------------------------
from __future__ import print_function

import os
import markdown2
import bs4
import re
from .warden_common import check_match, walk_directory_for_pattern, get_omitted_files

README_PATTERNS = ['*/readme.md', '*/README.md', '*/readme.rst']

from docutils import core
from docutils.writers.html4css1 import Writer,HTMLTranslator

class HTMLFragmentTranslator(HTMLTranslator):
    def __init__(self, document):
        HTMLTranslator.__init__(self, document)
        self.head_prefix = ['','','','','']
        self.body_prefix = []
        self.body_suffix = []
        self.stylesheet = []
    def astext(self):
        return ''.join(self.body)

html_fragment_writer = Writer()
html_fragment_writer.translator_class = HTMLFragmentTranslator

def rst_to_html(input_rst):
    return core.publish_string(input_rst, writer = html_fragment_writer)

def verify_readme_content(config):
    all_readmes = walk_directory_for_pattern(config.target_directory, README_PATTERNS)
    omitted_readmes = get_omitted_files(config)

    targeted_readmes = [readme for readme in all_readmes if readme not in omitted_readmes]

    for readme in targeted_readmes:
        ext = os.path.splitext(readme)[1]
        if ext == '.rst':
            print('rst')
        else:
            verify_md_readme(readme, config)


def verify_md_readme(readme, config):
    with open(readme, 'r') as f:
        readme_content = f.read()

    # convert to html
    html_readme_content = markdown2.markdown(readme_content)

    # parse html to beautiful document
    html_soup = bs4.BeautifulSoup(html_readme_content, "html.parser")

    # grep out all headers
    print(html_soup)

    # check to ensure that at least one header matches each `expected`

    # expected will support regex



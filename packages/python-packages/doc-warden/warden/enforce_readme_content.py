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

    readme_results = []

    for readme in targeted_readmes:
        ext = os.path.splitext(readme)[1]
        if ext == '.rst':
            readme_results.append(verify_rst_readme(readme, config))
        else:
            readme_results.append(verify_md_readme(readme, config))

    results([readme_tuple for readme_tuple in readme_results if readme_tuple[1]], config)

def results(readmes_with_issues, config):
    if len(readmes_with_issues):
        print('{} readmes have missing required sections.'.format(len(readmes_with_issues)))
        for readme_tuple in readmes_with_issues:
            print(readme_tuple[0].replace(os.path.normpath(config.target_directory), '') + ' is missing headers with pattern(s):')
            for missing_pattern in readme_tuple[1]:
                print(' * {0}'.format(missing_pattern))
        exit(1)

def verify_rst_readme(readme, config):
    with open(readme, 'r') as f:
        readme_content = f.read()
    html_readme_content = rst_to_html(readme_content)
    html_soup = bs4.BeautifulSoup(html_readme_content, "html.parser")

    missed_patterns = find_missed_sections(html_soup, config.required_readme_sections)

    return (readme, missed_patterns)

def verify_md_readme(readme, config):
    with open(readme, 'r') as f:
        readme_content = f.read()
    html_readme_content = markdown2.markdown(readme_content)
    html_soup = bs4.BeautifulSoup(html_readme_content, "html.parser")

    missed_patterns = find_missed_sections(html_soup, config.required_readme_sections)

    return (readme, missed_patterns)

def find_missed_sections(html_soup, patterns):
    headers = html_soup.find_all(re.compile('^h[1-6]$'))
    missed_patterns = []
    observed_patterns = []

    for header in headers:
        observed_patterns.extend(match_regex_set(header, patterns))

    # return what patterns were missed
    return list(set(patterns) - set(observed_patterns))

def match_regex_set(header, patterns):
    matching_patterns = []
    print(header.get_text())
    for pattern in patterns:
        print(pattern)
        result = re.search(pattern, header.get_text())
        if result:
            matching_patterns.append(pattern)
    return matching_patterns

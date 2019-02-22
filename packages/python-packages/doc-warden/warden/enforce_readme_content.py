# ------------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project 
# root for license information.
# ------------------------------------------------------------------------------
from __future__ import print_function

import os
import markdown2
import bs4
from .warden_common import check_match, walk_directory_for_pattern

README_PATTERNS = ['*/readme.md', '*/README.md', '*/readme.rst']

def verify_readme_content(target_directory):
    all_readmes = walk_directory_for_pattern(config.target_directory, README_PATTERNS)
    omitted_readmes = get_omitted_files(config)

    targeted_readmes = [readme for readme in all_readmes if readme not in omitted_readmes]


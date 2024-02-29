'''
Copyright 2024 Capgemini

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
'''
import re

# -- Project information

project = 'sostrades-core'
copyright = '2024, Capgemini'
author = 'Capgemini'

#release = '0.1'
#version = '0.1.0'

# -- General configuration

extensions = [
    'sphinx.ext.duration',
    'sphinx.ext.doctest',
    'sphinx.ext.autodoc',
    'sphinx.ext.autosummary',
    'sphinx.ext.intersphinx',
    'myst_parser',
]

intersphinx_mapping = {
    'python': ('https://docs.python.org/3/', None),
    'sphinx': ('https://www.sphinx-doc.org/en/master/', None),
}
intersphinx_disabled_domains = ['std']

templates_path = ['_templates']

# -- Options for HTML output

html_theme = 'sphinx_rtd_theme'

# -- Options for EPUB output
epub_show_urls = 'footnote'

def strip_signatures(app, what, name, obj, options, signature, return_annotation):
    """
    Replaces path to a class in annotation and return type
    """
    REGEX_MATCH_CORE_MODULE = 'sostrades_core\.([^.]|\.)*\.'
    sig = None                                                                  
    if signature is not None:                                                   
        sig = re.sub(REGEX_MATCH_CORE_MODULE, '', signature)                           
                                                                                
    ret = None                                                                  
    if return_annotation is not None:                                           
        ret = re.sub(REGEX_MATCH_CORE_MODULE, '', return_annotation)                           
                                                                                
    return sig, ret                                                             
                                                                                
                                                                                
def setup(app):                                                                 
    app.connect('autodoc-process-signature', strip_signatures)
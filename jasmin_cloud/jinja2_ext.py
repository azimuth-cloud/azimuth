"""
This module contains any custom Jinja2 extensions and filters used by the JASMIN
cloud portal.
"""

__author__ = "Matt Pryor"
__copyright__ = "Copyright 2015 UK Science and Technology Facilities Council"


import bleach, markdown, jinja2


def markdown_filter(value):
    """
    Jinja2 filter that takes a value containing markdown formatting, converts it
    to HTML, filters only allowed tags and returns a ``jinja2.Markup`` object.
    
    :param value: The value to filter
    :returns: ``jinja2.Markup``, the result of markdown conversion
    """
    # Convert markdown in the description and sanitize the result using the
    # default, conservative set of allowed tags and attributes
    print(markdown.markdown(value))
    return jinja2.Markup(bleach.clean(
        markdown.markdown(value),
        strip = True,
        tags = bleach.ALLOWED_TAGS + ['p', 'span', 'div'],
        attributes = dict(bleach.ALLOWED_ATTRIBUTES, **{ '*' : 'class' }),
    ))

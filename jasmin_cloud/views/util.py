"""
Utilities for use with views in the ``jasmin_cloud`` app.
"""

from django.utils.safestring import mark_safe
from django.utils.encoding import smart_text

from docutils import core

from rest_framework.utils import formatting


def get_view_description(view_cls, html = False):
    """
    Alternative django-rest-framework ``VIEW_DESCRIPTION_FUNCTION`` that allows
    RestructuredText to be used instead of Markdown.

    This allows docstrings to be used in the DRF-generated HTML views and in
    Sphinx-generated API views.
    """
    description = view_cls.__doc__ or ''
    description = formatting.dedent(smart_text(description))
    if html:
        # Get just the HTML parts corresponding to the docstring
        parts = core.publish_parts(source = description, writer_name = 'html')
        html = parts['body_pre_docinfo'] + parts['fragment']
        # Mark the output as safe for rendering as-is
        return mark_safe(html)
    return description

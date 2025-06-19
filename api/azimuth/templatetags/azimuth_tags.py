"""
Custom template tags for the Azimuth auth package.
"""

from azimuth_auth.settings import auth_settings
from django import template
from django.urls import reverse
from django.utils.html import escape, format_html
from django.utils.safestring import mark_safe

from ..settings import cloud_settings  # noqa: TID252

register = template.Library()


@register.simple_tag()
def azimuth_current_cloud():
    """
    Insert the name of the current cloud.
    """
    return cloud_settings.AVAILABLE_CLOUDS[cloud_settings.CURRENT_CLOUD]["label"]


@register.simple_tag(takes_context=True)
def azimuth_auth_login(context):
    """
    Include a login snippet using Azimuth auth.
    """
    login_url = reverse("azimuth_auth:login")
    snippet = "<li><a href='{href}?{param}={next}'>Sign in</a></li>"
    snippet = format_html(
        snippet,
        href=login_url,
        param=auth_settings.NEXT_URL_PARAM,
        next=escape(context["request"].path),
    )
    return mark_safe(snippet)


@register.simple_tag(takes_context=True)
def azimuth_auth_logout(context):
    """
    Include a logout snippet using Azimuth auth.
    """
    logout_url = reverse("azimuth_auth:logout")
    snippet = """<li class="dropdown">
        <a href="#" class="dropdown-toggle" data-toggle="dropdown">
            {user}
            <b class="caret"></b>
        </a>
        <ul class="dropdown-menu">
            <li><a href='{href}?{param}={next}'>Sign out</a></li>
        </ul>
    </li>"""
    snippet = format_html(
        snippet,
        user=escape(context["user"]),
        href=logout_url,
        param=auth_settings.NEXT_URL_PARAM,
        next=escape(context["request"].path),
    )
    return mark_safe(snippet)

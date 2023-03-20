"""
Custom template tags for the Azimuth auth package.
"""

from django import template
from django.urls import reverse

from ..settings import auth_settings


register = template.Library()


@register.simple_tag
def field_with_classes(field, *classes):
    """
    Adds the specified classes to the HTML element produced for the field.
    """
    return field.as_widget(attrs = { 'class': ' '.join(classes) })


@register.inclusion_tag('azimuth_auth/change_auth_button.html', takes_context = True)
def change_auth_button(context):
    """
    Renders the change auth button, but only if there are multiple authenticators.
    """
    return {
        'link_url': "{}?{}=1".format(
            reverse('azimuth_auth:login'),
            auth_settings.CHANGE_METHOD_PARAM
        ),
        'render_button': len(auth_settings.AUTHENTICATORS) > 1,
    }


@register.inclusion_tag('azimuth_auth/message.html', takes_context = True)
def auth_message(context):
    """
    Renders the message corresponding to the code in the request.
    """
    # If there is no code in the request, we are done
    code = context['request'].GET.get(auth_settings.MESSAGE_CODE_PARAM)
    if not code:
        return {}
    # If the code does not exist in the configured messages, we are done
    try:
        message = auth_settings.MESSAGES[code]
    except KeyError:
        return {}
    # Apply the default message level if required
    if isinstance(message, dict):
        return message
    else:
        return { 'message': message, 'level': auth_settings.DEFAULT_MESSAGE_LEVEL }

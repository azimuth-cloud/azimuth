"""
Module containing forms for the azimuth_auth views.
"""

from django import forms

from .settings import auth_settings


def authenticator_choices():
    """
    Generator for the authenticator selection choices.
    """
    for authenticator in auth_settings.AUTHENTICATORS:
        name = authenticator["NAME"]
        # Allow authenticators to be hidden from selection
        # They will still be available if the user knows the link
        # In particular, this is used for the appcred authenticator
        if authenticator.get("HIDDEN", False):
            continue
        options = authenticator["AUTHENTICATOR"].get_options()
        if options:
            for option, option_label in options:
                yield (f"{name}/{option}", option_label)
        else:
            yield (name, authenticator.get("LABEL", name))


class AuthenticatorSelectForm(forms.Form):
    """
    Form for selecting an authenticator.
    """

    authenticator = forms.ChoiceField(
        label="Authentication Method", choices=list(authenticator_choices())
    )
    remember = forms.BooleanField(required=False, label="Remember my choice")

"""
Module containing forms for the azimuth_auth views.
"""

from django import forms

from .settings import auth_settings


class AuthenticatorSelectForm(forms.Form):
    """
    Form for selecting an authenticator.
    """
    authenticator = forms.ChoiceField(
        label = "Authentication Method",
        choices = [
            (a["NAME"], a.get("LABEL", a["NAME"]))
            for a in auth_settings.AUTHENTICATORS
        ]
    )
    remember = forms.BooleanField(required = False, label = "Remember my choice")

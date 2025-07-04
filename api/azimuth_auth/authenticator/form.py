"""
Module containing the base form authenticator.
"""

from django import forms
from django.shortcuts import render

from .base import BaseAuthenticator


class UsernamePasswordForm(forms.Form):
    """
    Form for authenticating with a username and password.

    This is the default form for the form authenticator as it is the most
    common form of form-based authentication.
    """

    username = forms.CharField()
    password = forms.CharField(widget=forms.PasswordInput)


class FormAuthenticator(BaseAuthenticator):
    """
    Base class for an authenticator that gathers information from a form.
    """

    form_class = UsernamePasswordForm
    template = "azimuth_auth/form.html"

    def get_form(self, data=None, selected_option=None):
        """
        Return the form to use to collect authentication data.
        """
        return self.form_class(data)

    def auth_start(self, request, auth_complete_url, selected_option=None):
        # Just render an empty form
        return render(
            request,
            self.template,
            {
                "form": self.get_form(selected_option=selected_option),
                "auth_complete_url": auth_complete_url,
            },
        )

    def auth_complete(self, request, selected_option=None):
        # For a non-POST request, there is nothing to do
        if request.method != "POST":
            return
        # Process the form data
        # If the form data is not valid, we are done
        form = self.get_form(request.POST, selected_option)
        if not form.is_valid():
            return
        # If the form data is valid, attempt an authentication
        return self.auth_token(form.cleaned_data, selected_option)

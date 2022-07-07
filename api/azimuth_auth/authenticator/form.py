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
    password = forms.CharField(widget = forms.PasswordInput)


class FormAuthenticator(BaseAuthenticator):
    """
    Base class for an authenticator that gathers information from a form.
    """
    form_class = UsernamePasswordForm
    template = "azimuth_auth/form.html"

    def get_form(self, *args, **kwargs):
        """
        Return the form to use to collect authentication data.
        """
        return self.form_class(*args, **kwargs)

    def authenticate(self, form_data):
        """
        Given the data from a successful form validation, attempt an authentication.

        Should return a token if the authentication is successful, None otherwise.
        """
        raise NotImplementedError

    def auth_start(self, request):
        # Just render an empty form
        return render(request, self.template, { 'form': self.get_form() })

    def auth_complete(self, request):
        # For a non-POST request, there is nothing to do
        if request.method != "POST":
            return
        # Process the form data
        # If the form data is not valid, we are done
        form = self.get_form(request.POST)
        if not form.is_valid():
            return
        # If the form data is valid, attempt an authentication
        return self.authenticate(form.cleaned_data)

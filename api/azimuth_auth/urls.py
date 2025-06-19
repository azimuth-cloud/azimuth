"""
URL definitions for the Azimuth auth package.
"""

from django.urls import path

from . import views

app_name = 'azimuth_auth'
urlpatterns = [
    path('authenticators/', views.authenticators, name = 'authenticators'),
    path('login/', views.login, name = 'login'),
    path('<slug:authenticator>/start/', views.start, name = 'start'),
    path('<slug:authenticator>/complete/', views.complete, name = 'complete'),
    path('<slug:authenticator>/token/', views.token, name = 'token'),
    path('logout/', views.logout, name = 'logout'),
]

"""
URL definitions for the Azimuth auth package.
"""

from django.urls import path

from . import views


app_name = 'azimuth_auth'
urlpatterns = [
    path('login/', views.login, name = 'login'),
    path('complete/', views.complete, name = 'complete'),
    path('logout/', views.logout, name = 'logout'),
]

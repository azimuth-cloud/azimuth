"""
URL definitions for the cloud-auth package.
"""

from django.urls import path

from . import views


app_name = 'cloud_auth'
urlpatterns = [
    path('login/', views.login, name = 'login'),
    path('complete/', views.complete, name = 'complete'),
    path('logout/', views.logout, name = 'logout'),
]

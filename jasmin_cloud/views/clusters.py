"""
Django views for interacting with the configured cluster engine.
"""

from rest_framework import decorators, permissions


@decorators.api_view(['GET'])
@decorators.permission_classes([permissions.IsAuthenticated])
def cluster_types(request, tenant):
    """
    Returns the cluster types available to the tenancy.
    """


@decorators.api_view(['GET'])
@decorators.permission_classes([permissions.IsAuthenticated])
def cluster_type_details(request, tenant, cluster_type):
    """
    Returns the requested cluster type.
    """


@decorators.api_view(['GET', 'POST'])
@decorators.permission_classes([permissions.IsAuthenticated])
def clusters(request, tenant):
    """
    On ``GET`` requests, return a list of the deployed clusters.

    On ``POST`` requests, create a new cluster.
    """


@decorators.api_view(['GET', 'PUT', 'DELETE'])
@decorators.permission_classes([permissions.IsAuthenticated])
def cluster_details(request, tenant, cluster):
    """
    On ``GET`` requests, return the named cluster.

    On ``PUT`` requests, update the named cluster with the given paramters.

    On ``DELETE`` requests, delete the named cluster.
    """

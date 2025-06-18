from rackit import EmbeddedResource, Endpoint, RootResource

from .core import Resource, ResourceWithDetail, Service, UnmanagedResource


class ShareType(Resource):
    """
    Resource for accessing share types.
    """
    class Meta:
        endpoint = '/types'
        resource_key = "share_type"
        resource_list_key = "share_types"


class Share(ResourceWithDetail):
    """
    Resource for accessing shares.
    """
    class Meta:
        endpoint = '/shares'

    def grant_rw_access(self, username):
        self._action('action', {
            'allow_access': {
                "access_level": "rw",
                "access_type": "cephx",
                "access_to": username,
            }
        })


class ShareAccess(Resource):
    """
    Resource for share access lists.
    """
    class Meta:
        endpoint = '/share-access-rules'
        resource_key = "access"
        resource_list_key = "access_list"


class AbsoluteLimits(UnmanagedResource):
    """
    Represents the absolute limits for a project.
    """
    class Meta:
        aliases = dict(
            # TODO(johngarbutt): fill out the rest?
            total_shares_gb='maxTotalShareGigabytes',
            total_shares_gb_used='totalShareGigabytesUsed',
            total_shares='maxTotalShares',
            total_shares_used='totalSharesUsed',
        )


class ShareLimits(UnmanagedResource):
    """
    Represents the limits for a project.

    This is not a REST-ful resource, so is unmanaged.
    """
    class Meta:
        endpoint = "/limits"

    absolute = EmbeddedResource(AbsoluteLimits)


class ShareService(Service):
    """
    OpenStack service class for the compute service.
    """
    name = "share"
    catalog_type = "sharev2"
    path_prefix = '/v2/{project_id}'

    limits = Endpoint(ShareLimits)
    shares = RootResource(Share)
    types = RootResource(ShareType)
    access = RootResource(ShareAccess)

    def prepare_request(self, request):
        request.headers["X-OpenStack-Manila-API-Version"] = "2.51"
        return super().prepare_request(request)

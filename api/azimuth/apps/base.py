import typing as t

from ..cluster_api import dto as capi_dto  # noqa: TID252
from ..provider import base as cloud_base  # noqa: TID252
from . import dto


class Provider:
    """
    Base class for apps providers.
    """

    def session(self, cloud_session: cloud_base.ScopedSession) -> "Session":
        """
        Returns an apps session scoped to the given cloud provider session.
        """
        raise NotImplementedError


class Session:
    """
    Base class for a scoped apps session.
    """

    def app_templates(self) -> t.Iterable[dto.AppTemplate]:
        """
        Lists the app templates currently available to the tenancy.
        """
        raise NotImplementedError

    def find_app_template(self, id: str) -> dto.AppTemplate:  # noqa: A002
        """
        Finds an app template by id.
        """
        raise NotImplementedError

    def apps(self) -> t.Iterable[dto.App]:
        """
        Lists the apps for the tenancy.
        """
        raise NotImplementedError

    def find_app(self, id: str) -> dto.App:  # noqa: A002
        """
        Finds an app by id.
        """
        raise NotImplementedError

    def create_app(
        self,
        name: str,
        template: dto.AppTemplate,
        values: dict[str, t.Any],
        *,
        kubernetes_cluster: capi_dto.Cluster | None = None,
        zenith_identity_realm_name: str | None = None,
    ) -> dto.App:
        """
        Create a new app in the tenancy.
        """
        raise NotImplementedError

    def update_app(
        self,
        app: dto.App | str,
        template: dto.AppTemplate,
        version: dto.Version,
        values: dict[str, t.Any],
    ) -> dto.App:
        """
        Update the specified cluster with the given parameters.
        """
        raise NotImplementedError

    def delete_app(self, app: dto.App | str) -> dto.App | None:
        """
        Delete the specified app.
        """
        raise NotImplementedError

    def close(self):
        """
        Closes the session and performs any cleanup.
        """
        # NOOP by default

    def __enter__(self):
        """
        Called when entering a context manager block.
        """
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """
        Called when exiting a context manager block. Ensures that close is called.
        """
        self.close()

    def __del__(self):
        """
        Ensures that close is called when the session is garbage collected.
        """
        self.close()

import dataclasses
import typing as t


@dataclasses.dataclass(frozen=True)
class User:
    """
    Object representing a user.
    """

    #: The ID of the user
    id: str
    #: The username of the user
    username: str
    #: The email address of the user
    email: str


@dataclasses.dataclass(frozen=True)
class Tenancy:
    """
    Object representing a tenancy.
    """

    #: The ID of the tenancy
    id: str
    #: The name of the tenancy
    name: str


@dataclasses.dataclass(frozen=True)
class Credential:
    """
    Object representing a credential for deploying resources.
    """

    #: The provider that the credential is for
    provider: str
    #: The credential data, which will depend on the provider
    data: str

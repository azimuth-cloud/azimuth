"""
Module containing the Zenith provider.
"""

import dataclasses
import typing as t

import requests


@dataclasses.dataclass
class ZenithReservation:
    """
    Class representing a Zenith subdomain reservation.
    """
    #: The subdomain that was reserved
    subdomain: str
    #: The FQDN that was reserved
    fqdn: str
    #: The token that can be used to associate public keys
    token: str


@dataclasses.dataclass
class Zenith:
    """
    Class representing a Zenith installation.
    """
    #: The base domain of the target Zenith instance
    base_domain: str
    #: The external URL of the registrar of the target Zenith instance
    registrar_external_url: str
    #: The admin URL of the registrar of the target Zenith instance
    registrar_admin_url: str
    #: The address of the SSHD service of the target Zenith instance
    sshd_host: str
    #: The port for the SSHD service of the target Zenith instance
    sshd_port: int
    #: Indicates whether SSL should be verified when determining whether a service is ready
    verify_ssl: bool
    #: Indicates whether SSL should be verified by clients when associating keys with the
    #: registrar using the external endpoint
    verify_ssl_clients: bool

    def service_is_ready(self, fqdn: str, readiness_path: str = "/") -> t.Optional[str]:
        """
        Given an FQDN for a Zenith service, return the redirect URL if it is ready or
        `None` otherwise.

        Optionally, a readiness path can be given that will be used for the readiness check.
        """
        url = f"http://{fqdn}"
        # While the URL returns a 404, 503 or a certificate error (probably because cert-manager
        # is still negotiating the certificate), the service is not ready
        try:
            resp = requests.get("{}{}".format(url, readiness_path), verify = self.verify_ssl)
        except requests.exceptions.SSLError:
            return None
        else:
            return url if resp.status_code not in {404, 503} else None

    def reserve_subdomain(self) -> ZenithReservation:
        """
        Reserves a subdomain and returns a `ZenithReservation` for the subdomain.
        """
        response = requests.post(f"{self.registrar_admin_url}/admin/reserve")
        response.raise_for_status()
        response_data = response.json()
        return ZenithReservation(
            response_data["subdomain"],
            response_data["fqdn"],
            response_data["token"]
        )

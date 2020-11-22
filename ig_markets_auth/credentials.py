import datetime
import json
import typing

import attr
import httpx
from httpx import URL
from httpx._types import RawURL, URLTypes
from loguru import logger

from . import exceptions, helpers


def _parse_expiry(response_data):
    """Parses the expiry field from a response into a datetime.

    Args:
        response_data (Mapping): The JSON-parsed response data.

    Returns:
        Optional[datetime]: The expiration or ``None`` if no expiration was
            specified.
    """
    expires_in = response_data.get("expires_in", None)
    if expires_in is not None:
        return helpers.utcnow() + datetime.timedelta(seconds=int(expires_in))
    else:
        return None


def refresh_grant(
    client: httpx.Client,
    token_uri: typing.Union["URL", str, RawURL],
    refresh_token: str,
    scopes: str = None
):
    payload = {
        "refresh_token": refresh_token,
    }
    # if scopes:
    #     payload["scope"] = scopes

    logger.debug(f"HTTP Request: POST {token_uri} {client.headers} {payload}")
    response = client.post(url=token_uri, json=payload)
    response_data = response.json()

    try:
        access_token = response_data["access_token"]
    except KeyError as caught_exc:
        new_exc = exceptions.RefreshError("No access token in response.", response_data)
        raise new_exc from caught_exc

    refresh_token = response_data.get("refresh_token", refresh_token)
    expiry = _parse_expiry(response_data)

    return access_token, refresh_token, expiry, response_data


@ attr.s
class Credentials:
    token = attr.ib(type=str)
    refresh_token = attr.ib(type=str)
    scopes = attr.ib(type=str)
    token_uri = attr.ib(type=URLTypes)
    expiry = attr.ib(type=datetime.datetime, default=None)

    @ classmethod
    def from_token_response(
        cls,
        token: typing.Dict,
        token_uri: URLTypes,
    ):
        return cls(
            token=token["access_token"],
            refresh_token=token.get("refresh_token"),
            token_uri=token_uri,
            scopes=token.get("scope"),
            expiry=_parse_expiry(token)
        )

    def refresh(self, request):
        if (
            self.refresh_token is None
            or self.token_uri is None
        ):
            raise exceptions.RefreshError(
                "The credentials do not contain the necessary fields need to "
                "refresh the access token. You must specify refresh_token, "
                "and token_uri."
            )

        access_token, refresh_token, expiry, grant_response = refresh_grant(
            request,
            self.token_uri,
            self.refresh_token,
            self.scopes,
        )

        self.token = access_token
        self.expiry = expiry
        self.refresh_token = refresh_token

        if self.scopes and "scopes" in grant_response:
            requested_scopes = frozenset(self.scopes)
            granted_scopes = frozenset(grant_response["scopes"].split())
            scopes_requested_but_not_granted = requested_scopes - granted_scopes
            if scopes_requested_but_not_granted:
                raise exceptions.RefreshError(
                    "Not all requested scopes were granted by the "
                    "authorization server, missing scopes {}.".format(
                        ", ".join(scopes_requested_but_not_granted)
                    )
                )

    @property
    def expired(self) -> bool:
        """Checks if the credentials are expired.

        Note that credentials can be invalid but not expired because
        Credentials with :attr:`expiry` set to None is considered to never
        expire.
        """
        if not self.expiry:
            return False

        # Remove 5 minutes from expiry to err on the side of reporting
        # expiration early so that we avoid the 401-refresh-retry loop.
        skewed_expiry = self.expiry - helpers.CLOCK_SKEW
        return helpers.utcnow() >= skewed_expiry

    @property
    def valid(self) -> bool:
        """Checks the validity of the credentials.

        This is True if the credentials have a :attr:`token` and the token
        is not :attr:`expired`.
        """
        return self.token is not None and not self.expired

    def apply(self, headers: typing.Dict, token: str = None):
        """Apply the token to the authentication header, as well as the API Key (specific to IG Market).

        Args:
            headers (Mapping): The HTTP request headers.
            token (Optional[str]): If specified, overrides the current access
                token.
        """
        headers.update(
            {
                'Authorization': f"Bearer {helpers.from_bytes(token or self.token)}",
            }
        )

    def before_request(
        self,
        request: httpx.Client,
        method: str,
        url: typing.Union["URL", str, RawURL],
        headers: typing.Dict
    ):
        """Performs credential-specific before request logic.

        Refreshes the credentials if necessary, then calls :meth:`apply` to
        apply the token to the authentication header.

        Args:
            request (google.auth.transport.Request): The object used to make
                HTTP requests.
            method (str): The request's HTTP method or the RPC method being
                invoked.
            url (str): The request's URI or the RPC service's URI.
            headers (Mapping): The request's headers.
        """
        if not self.valid:
            self.refresh(request)
        self.apply(headers)

    def to_json(self, strip=None):
        """Utility function that creates a JSON representation of a Credentials
        object.

        Args:
            strip (Sequence[str]): Optional list of members to exclude from the
                                generated JSON.

        Returns:
            str: A JSON representation of this instance. When converted into
            a dictionary, it can be passed to from_authorized_user_info()
            to create a new credential instance.
        """
        prep = {
            "token": self.token,
            "refresh_token": self.refresh_token,
            "scopes": self.scopes,
        }

        # Remove empty entries
        prep = {k: v for k, v in prep.items() if v is not None}

        # Remove entries that explicitely need to be removed
        if strip is not None:
            prep = {k: v for k, v in prep.items() if k not in strip}

        return json.dumps(prep)

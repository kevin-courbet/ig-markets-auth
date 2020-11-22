import numbers
import time
import typing
from typing import Tuple

import httpx
from httpx._config import UNSET, UnsetType
from httpx._types import (AuthTypes, CookieTypes, HeaderTypes, QueryParamTypes,
                          RequestContent, RequestData, RequestFiles,
                          TimeoutTypes, URLTypes)
from loguru import logger

from .credentials import Credentials

DEFAULT_REFRESH_STATUS_CODES = (httpx.codes.UNAUTHORIZED,)
"""Sequence[int]:  Which HTTP status code indicate that credentials should be
refreshed and a request should be retried.
"""

DEFAULT_MAX_REFRESH_ATTEMPTS = 2
"""int: How many times to refresh the credentials and retry a request."""

DEFAULT_TIMEOUT = httpx.Timeout(timeout=60)


class TimeoutGuard(object):
    """A context manager raising an error if the suite execution took too long.

    Args:
        timeout ([Union[None, float, Tuple[float, float]]]):
            The maximum number of seconds a suite can run without the context
            manager raising a timeout exception on exit. If passed as a tuple,
            the smaller of the values is taken as a timeout. If ``None``, a
            timeout error is never raised.
        timeout_error_type (Optional[Exception]):
            The type of the error to raise on timeout. Defaults to
            :class:`requests.exceptions.Timeout`.
    """

    def __init__(self, timeout, timeout_error_type=httpx._exceptions.TimeoutException):
        self._timeout = timeout
        self.remaining_timeout = timeout
        self._timeout_error_type = timeout_error_type

    def __enter__(self):
        self._start = time.time()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_value:
            return  # let the error bubble up automatically

        if self._timeout is None:
            return  # nothing to do, the timeout was not specified

        elapsed = time.time() - self._start
        deadline_hit = False

        if isinstance(self._timeout, numbers.Number):
            self.remaining_timeout = self._timeout - elapsed
            deadline_hit = self.remaining_timeout <= 0
        else:
            self.remaining_timeout = tuple(x - elapsed for x in self._timeout)
            deadline_hit = min(self.remaining_timeout) <= 0

        if deadline_hit:
            raise self._timeout_error_type()


class AuthorizedSession(httpx.Client):

    def __init__(
        self,
        credentials: Credentials,
        refresh_status_codes: Tuple = DEFAULT_REFRESH_STATUS_CODES,
        max_refresh_attempts: int = DEFAULT_MAX_REFRESH_ATTEMPTS,
        refresh_timeout: int = None,
        auth_request: httpx.Client = None,
        **kwargs
    ):
        super().__init__(
            timeout=DEFAULT_TIMEOUT,
            **kwargs
        )
        self.credentials = credentials
        self.refresh_status_codes = refresh_status_codes
        self.max_refresh_attempts = max_refresh_attempts
        self.refresh_timeout = refresh_timeout
        if auth_request is None:
            auth_request = httpx.Client(timeout=DEFAULT_TIMEOUT)
        self.auth_request = auth_request

    def request(
        self,
        method: str,
        url: URLTypes,
        *,
        content: RequestContent = None,
        data: RequestData = None,
        files: RequestFiles = None,
        json: typing.Any = None,
        params: QueryParamTypes = None,
        headers: HeaderTypes = None,
        cookies: CookieTypes = None,
        auth: typing.Union[AuthTypes, UnsetType] = UNSET,
        allow_redirects: bool = True,
        timeout: typing.Union[TimeoutTypes, UnsetType] = UNSET,
        max_allowed_time: typing.Optional[int] = None,
        **kwargs
    ):
        """Implementation of httpx.Client's request.

            Args:
                timeout (Optional[Union[TimeoutTypes, UnsetType]]):
                    The amount of time in seconds to wait for the server response
                    with each individual request.

                    Can also be passed as a tuple (connect_timeout, read_timeout).
                    See :meth:`requests.Session.request` documentation for details.

                max_allowed_time (Optional[float]):
                    If the method runs longer than this, a ``Timeout`` exception is
                    automatically raised. Unlike the ``timeout` parameter, this
                    value applies to the total method execution time, even if
                    multiple requests are made under the hood.

                    Mind that it is not guaranteed that the timeout error is raised
                    at ``max_allowed_time`. It might take longer, for example, if
                    an underlying request takes a lot of time, but the request
                    itself does not timeout, e.g. if a large file is being
                    transmitted. The timout error will be raised after such
                    request completes.
        """
        request = self.build_request(
            method=method,
            url=url,
            content=content,
            data=data,
            files=files,
            json=json,
            params=params,
            headers=headers,
            cookies=cookies,
        )

#         'IG-ACCOUNT-ID': settings.ACCOUNT_ID,

        credential_refresh_attempt = kwargs.pop("credential_refresh_attempt", 0)
        original_headers = request.headers
        remaining_time = max_allowed_time

        auth_request = self.auth_request
        if not isinstance(timeout, UnsetType):
            auth_request.timeout = timeout

        with TimeoutGuard(remaining_time) as guard:
            self.credentials.before_request(auth_request, method, url, request.headers)
        remaining_time = guard.remaining_timeout

        with TimeoutGuard(remaining_time) as guard:
            logger.debug(f"HTTP Request: {request.method} {request.url} {request.headers}")
            response = self.send(
                request,
                timeout=timeout,
                **kwargs
            )
        remaining_time = guard.remaining_timeout

        # If the response indicated that the credentials needed to be
        # refreshed, then refresh the credentials and re-attempt the
        # request.
        # A stored token may expire between the time it is retrieved and
        # the time the request is made, so we may need to try twice.
        if (
            response.status_code in self.refresh_status_codes
            and credential_refresh_attempt < self.max_refresh_attempts
        ):

            logger.info(
                "Refreshing credentials due to a %s response. Attempt %s/%s.",
                response.status_code,
                credential_refresh_attempt + 1,
                self.max_refresh_attempts,
            )

            # Do not apply the timeout unconditionally in order to not override the
            # _auth_request's default timeout.
            auth_request = self.auth_request
            if not isinstance(timeout, UnsetType):
                auth_request.timeout = timeout

            with TimeoutGuard(remaining_time) as guard:
                self.credentials.refresh(auth_request)
            remaining_time = guard.remaining_timeout

            # Recurse. Pass in the original headers, not our modified set, but
            # do pass the adjusted max allowed time (i.e. the remaining total time).
            return self.request(
                method,
                url,
                data=data,
                headers=original_headers,
                max_allowed_time=remaining_time,
                timeout=timeout,
                credential_refresh_attempt=credential_refresh_attempt + 1,
                **kwargs
            )

        return response

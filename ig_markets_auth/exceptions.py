
class AuthError(Exception):
    """Base class for all auth errors."""


class RefreshError(AuthError):
    """Used to indicate that an refreshing the credentials' access token
    failed."""

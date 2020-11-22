import datetime

CLOCK_SKEW_SECS = 10  # 10 seconds
CLOCK_SKEW = datetime.timedelta(seconds=CLOCK_SKEW_SECS)


def utcnow():
    """Returns the current UTC datetime.

    Returns:
        datetime: The current time in UTC.
    """
    return datetime.datetime.utcnow()


def from_bytes(value):
    """Converts bytes to a string value, if necessary.

    Args:
        value (Union[str, bytes]): The value to be converted.

    Returns:
        str: The original value converted to unicode (if bytes) or as passed in
            if it started out as unicode.

    Raises:
        ValueError: If the value could not be converted to unicode.
    """
    result = value.decode("utf-8") if isinstance(value, bytes) else value
    if isinstance(result, str):
        return result
    else:
        raise ValueError("{0!r} could not be converted to unicode".format(value))

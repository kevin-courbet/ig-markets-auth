import time

import httpx
from ig_markets_api import __version__
from ig_markets_api.auth.flow import Flow


def test_version():
    assert __version__ == '0.1.0'


def test_logging():
    from ig_markets_api.config import settings
    flow = Flow.from_config(config=settings)
    flow.fetch_token()
    session = flow.authorized_session()

    headers = {
        'X-IG-API-KEY': settings.API_KEY,
        'IG-ACCOUNT-ID': settings.ACCOUNT_ID,
        'Version': "1"
    }
    response = session.get('/accounts', headers=headers)
    assert response.status_code == httpx.codes.OK

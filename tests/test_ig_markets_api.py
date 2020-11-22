import httpx
from ig_markets_auth import __version__


def test_version():
    assert __version__ == '1.0.0'


def test_api():
    import time

    from ig_markets_auth.config import settings
    from ig_markets_auth.flow import Flow

    flow = Flow.from_config(config=settings)
    flow.fetch_token()
    session = flow.authorized_session()
    response = session.get('/accounts', headers={'IG-ACCOUNT-ID': settings.ACCOUNT_ID})
    assert response.status_code == httpx.codes.OK
    time.sleep(1)
    response = session.get('/accounts', headers={'IG-ACCOUNT-ID': settings.ACCOUNT_ID})
    assert response.status_code == httpx.codes.OK
    time.sleep(45)
    response = session.get('/accounts', headers={'IG-ACCOUNT-ID': settings.ACCOUNT_ID})
    assert response.status_code == httpx.codes.OK

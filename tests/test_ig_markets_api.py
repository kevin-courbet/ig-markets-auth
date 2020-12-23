import httpx
from ig_markets_auth.config import Settings
from ig_markets_auth.flow import Flow


def test_api():
    settings = Settings()
    flow = Flow.from_config(config=settings)
    flow.fetch_token()
    session = flow.authorized_session()
    response = session.get('/accounts', headers={'IG-ACCOUNT-ID': settings.ACCOUNT_ID})
    assert response.status_code == httpx.codes.OK

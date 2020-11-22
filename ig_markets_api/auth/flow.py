from __future__ import annotations

from typing import Dict

import attr
import httpx
from ig_markets_api.config import Settings
from loguru import logger

from .credentials import Credentials
from .requests import AuthorizedSession


@attr.s
class Flow:
    """
    from ig_markets_api.flow import Flow

    # Create the flow using the app settings object
    flow = Flow.from_config(config=settings)

    # fetch token using credentials found in settings
    flow.fetch_token()

    # You can use flow.credentials, or you can just get a httpx Client
    # using flow.authorized_session.
    session = flow.authorized_session()
    print(session.get('https://www.googleapis.com/userinfo/v2/me').json())
    """
    api_url = attr.ib(type=str)
    username = attr.ib(type=str)
    password = attr.ib(type=str)
    api_key = attr.ib(type=str)
    account_id = attr.ib(type=str)
    client = attr.ib(factory=httpx.Client, repr=False)
    token = attr.ib(type=Dict, init=False)

    def __attrs_post_init__(self):
        self.client.base_url = self.api_url

    @classmethod
    def from_config(cls, config: Settings):
        return cls(
            api_url=config.API_URL,
            username=config.USERNAME,
            password=config.PASSWORD,
            api_key=config.API_KEY,
            account_id=config.ACCOUNT_ID
        )

    def fetch_token(self, **kwargs) -> Dict:
        logger.debug(
            f"Fetching token from {self.api_url} using client {self.client.__class__}")
        headers = {
            "X-IG-API-KEY": self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json; charset=UTF-8",
            "Version": "3"
        }
        data = {
            "identifier": self.username,
            "password": self.password
        }
        response = self.client.post('/session', headers=headers, json=data)
        response.raise_for_status()
        self.token = response.json()['oauthToken']
        return self.token

    @property
    def credentials(self):
        if not self.token:
            raise ValueError(
                "There is no access token for this session, did you call " "fetch_token?"
            )

        credentials = Credentials.with_expire_in(
            token=self.token,
            token_uri=self.api_url,
            client_id=self.username,
            client_secret=self.password,
            api_key=self.api_key,
        )
        return credentials

    def authorized_session(self):
        return AuthorizedSession(credentials=self.credentials, base_url=self.api_url)

    def __enter__(self) -> Flow:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.client.close()

from pydantic import AnyHttpUrl, BaseSettings


class Settings(BaseSettings):

    # Backend
    API_URL: AnyHttpUrl = "https://demo-api.ig.com/gateway/deal"
    USERNAME: str
    PASSWORD: str
    API_KEY: str
    ACCOUNT_ID: str = "ABC123"

    class Config:
        case_sensitive = True
        env_file = '.env'
        env_file_encoding = 'utf-8'


settings = Settings()

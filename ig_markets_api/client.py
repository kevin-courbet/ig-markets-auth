from .config import settings


class IGClient:
    def fetch_accounts(self, session=None):
        """Returns a list of accounts belonging to the logged-in client"""
        version = "1"
        params = {}
        endpoint = "/accounts"
        action = "read"
        response = self._req(action, endpoint, params, session, version)
        data = self.parse_response(response.text)
        if _HAS_PANDAS and self.return_dataframe:

            data = pd.DataFrame(data["accounts"])
            d_cols = {"balance": [u"available",
                                  u"balance", u"deposit", u"profitLoss"]}
            data = self.expand_columns(data, d_cols, False)

            if len(data) == 0:
                columns = [
                    "accountAlias",
                    "accountId",
                    "accountName",
                    "accountType",
                    "balance",
                    "available",
                    "balance",
                    "deposit",
                    "profitLoss",
                    "canTransferFrom",
                    "canTransferTo",
                    "currency",
                    "preferred",
                    "status",
                ]
                data = pd.DataFrame(columns=columns)
                return data

        return data

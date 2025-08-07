import logging, os, requests, json
import pandas as pd
from typing import Literal
import msal

class DataverseClient:
    def __init__(self, config_json: str):
        self.config_json = config_json
        workingDirectory = os.getcwd()
        
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)
        if not self.logger.handlers:
            file_handler = logging.FileHandler(os.path.join(workingDirectory, 'DataverseClient.log'))
            file_handler.setLevel(logging.DEBUG)
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
        
        authentication = self.get_authenticated_session(self.config_json)
        self.session: requests.Session = authentication[0]
        self.environmentURI: str = authentication[1]

    def get_authenticated_session(self, config_json: str) -> tuple[requests.Session, str]:
        """
        Authenticates with Azure Entra ID (formerly Azure Active Directory) using interactive login and returns an authenticated requests.Session.
        Args:
            config_json (str): Path to a JSON configuration file containing authentication parameters:
                - environmentURI (str): The base URI of the environment.
                - scopeSuffix (str): The suffix to append to the environment URI for the scope.
                - clientID (str): The client (application) ID registered in Azure.
                - authorityBase (str): The base authority URL (e.g., "https://login.microsoftonline.com/").
                - tenantID (str): The Azure tenant ID.
                Check Documentation for example JSON file.
        Returns:
            requests.Session: An authenticated session with the appropriate headers set for API requests.
        Raises:
            Exception: If authentication fails or an access token cannot be obtained.
        Notes:
            - This method uses interactive authentication, which requires user interaction in a browser window.
            - The application must be registered in Azure with a redirect URI of "http://localhost".
            Check Documentation for instructions on how to setup the app registration in Azure Portal.
        """
        config = json.load(open(config_json))
        environmentURI = config['environmentURI']
        scope = [environmentURI + '/' + config['scopeSuffix']]
        clientID = config['clientID']
        authority = config['authorityBase'] + config['tenantID']

        app = msal.PublicClientApplication(clientID, authority=authority)

        result = None

        logging.info('Obtaining new token from Azure Entra ID...')

        result = app.acquire_token_interactive(scopes=scope) # Only works if your app is registered with redirect_uri as http://localhost

        if 'access_token' in result:
            logging.info('Token obtained successfully.')
            session = requests.Session()
            session.headers.update(dict(Authorization='Bearer {}'.format(result.get('access_token'))))
            session.headers.update({'OData-MaxVersion': '4.0', 'OData-Version': '4.0', 'Accept': 'application/json'})
            return session, environmentURI
        else:
            logging.error(f'Failed to obtain token: {result.get('error')}\nDescription: {result.get('error_description')}\nCorrelation ID: {result.get('correlation_id')}')
            raise Exception(f"Authentication failed: {result.get('error')}, {result.get('error_description')}")
        
    def get_rows(self, entity: str, top: int | None = None, columns: list = [], filter: str | None = None, include_odata_annotations: bool = False) -> pd.DataFrame:
        """
        Retrieves rows from a specified Dataverse entity and returns them as a pandas DataFrame.
        Args:
            entity (str): The logical name of the Dataverse entity to query. Use PLURAL form (e.g. accounts, contacts).
            top (int, optional): The maximum number of rows to retrieve. If None, retrieves all available rows.
            columns (list, optional): List of column names to select. If empty, all columns are retrieved.
            filter (str, optional): OData filter string to apply to the query. If None, no filter is applied.
            include_odata_annotations (bool, optional): If True, includes OData annotations in the response. When using columns, odata annotations are also filtered.
        Returns:
            pd.DataFrame: A DataFrame containing the retrieved rows from the specified entity.
        Raises:
            Exception: If the HTTP request to the Dataverse API fails.
        """
        get_headers = self.session.headers.copy() # type: ignore
        if include_odata_annotations:
            get_headers.update({'Prefer': 'odata.include-annotations=*'})

        requestURI = f'{self.environmentURI}api/data/v9.2/{entity}'
        queryParams = []

        if top:
            queryParams.append(f'$top={top}')
        if columns:
            queryParams.append(f'$select={",".join(columns)}')
        if filter:
            queryParams.append(f'$filter={filter}')
        
        if queryParams:
            requestURI += '?' + '&'.join(queryParams)

        r = self.session.get(requestURI, headers=get_headers)

        if r.status_code != 200:
            self.logger.error(f"Request failed. Error code: {r.status_code}. Response: {r.content.decode('utf-8')}")
            raise Exception(f"Request failed with status code {r.status_code}. Response: {r.content.decode('utf-8')}")
        else:
            data = r.json()
            rows = data.get("value", [])
            df = pd.DataFrame(rows)
            while data.get('@odata.nextLink') is not None:
                next_url = data.get('@odata.nextLink')
                r = self.session.get(next_url)
                if r.status_code != 200:
                    self.logger.error(f"Request failed. Error code: {r.status_code}. Response: {r.content.decode('utf-8')}")
                    raise Exception(f"Request failed with status code {r.status_code}. Response: {r.content.decode('utf-8')}")
                else:
                    data = r.json()
                    rows = data.get("value", [])
                    df = pd.concat([df, pd.DataFrame(rows)], ignore_index=True)
            self.logger.info(f"Retrieved {len(df)} rows from entity '{entity}'.")
            return df
        
    def insert_rows(self, entity:str, df: pd.DataFrame) -> None:
        """
        Inserts rows from a pandas DataFrame into a specified Dataverse entity.
        Args:
            entity (str): The logical name of the Dataverse entity to insert rows into.
            df (pd.DataFrame): The DataFrame containing the rows to be inserted. Each row should match the entity's schema.
        Notes:
            - Each row in the DataFrame is converted to a JSON payload and sent as a POST request to the Dataverse Web API.
            - The method logs an error if the insertion of a row fails (status code != 204), including the error code and response content.
            - On successful insertion (status code == 204), an info log is created for the row.
        """
        insert_headers = dict(self.session.headers)
        insert_headers.update({'Content-Type': 'application/json; charset=utf-8'})

        requestURI = f'{self.environmentURI}api/data/v9.2/{entity}'

        for idx, row in df.iterrows():
            payload = json.loads(row.to_json())
            r = self.session.post(url=requestURI, headers=insert_headers, json=payload)

            if r.status_code != 204:
                self.logger.error(f"Insert failed for row {idx}. Error code: {r.status_code}. Response: {r.content.decode('utf-8')}")
            else:
                self.logger.info(f"Row {idx} inserted successfully into entity '{entity}'.")
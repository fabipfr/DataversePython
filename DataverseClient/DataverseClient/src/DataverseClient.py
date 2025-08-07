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
    
    def upsert_rows(self, entity: str, df: pd.DataFrame, primary_key_col: str, only_update_if_exists: bool = False) -> None:
        """
        Upserts rows for a specified Dynamics 365 entity based on the provided DataFrame.
        This function renames the provided primary key column in the DataFrame to "GUID",
        converts the remaining data to a list of JSON records, and writes these records to "result.json".
        It then iterates over each row of the DataFrame, constructs a PATCH request to update the
        entity identified by the GUID at the corresponding API endpoint, and updates the row.
        Successes and failures are tracked and printed during the process.
        Args:
            entity (str):
                The name of the Dynamics 365 entity to update.
            df (pandas.DataFrame):
                DataFrame containing the rows to upsert. Must include a column representing the primary key.
            primary_key_col (str):
                The name of the DataFrame column that contains the unique identifier for each row.
            only_update_if_exists (bool, optional):
                If True, the function will only update existing records and will not create new ones.
        """        
        upsert_headers = dict(self.session.headers)
        if only_update_if_exists:
            upsert_headers.update({'If-Match': '*'})
        upsert_headers.update({'If-None-Match': '*'})

        records = json.loads(df.drop(columns='GUID').to_json(orient="records"))

        successful_updates = 0
        failures = 0
        expected_updates = len(df)

        for idx, (_, row) in enumerate(df.iterrows()):
            guid = row[f'{primary_key_col}']
            requestURI = f'{self.environmentURI}api/data/v9.2/{entity}({guid})'
            payload = records[idx]

            for key, value in payload.items():
                if isinstance(value, str):
                    if value.lower() == "false":
                        payload[key] = False
                    elif value.lower() == "true":
                        payload[key] = True
            
            # Filter out keys with None values to prevent sending undeclared properties
            payload = {k: v for k, v in payload.items() if pd.notna(v)}

            r = self.session.patch(requestURI, headers=upsert_headers, json=payload)
            

            if r.status_code != 204:
                failures += 1
                self.logger.error(f'Error updating {guid}. Error {r.status_code}: \n{r.content.decode('utf-8')}\n')
            else:
                successful_updates += 1

            if idx % 10 == 0:
                self.logger.debug(f"Processed: {idx + 1}")

        self.logger.info(f'{successful_updates} updates made of {expected_updates} expected updates.\n{failures} failures.')

    def insert_m_n(self, entity_m: str, entity_n: str, relationship_name: str, df: pd.DataFrame) -> None:
        """
        Creates many-to-many relationships between two entities using data from a DataFrame.
        This function iterates over each row of the provided DataFrame and establishes a relationship between records identified by
        the specified entity column names. For each row, it builds the necessary API endpoint URLs and sends a POST request to connect
        the respective records. The function prints progress messages every 10 processed records and outputs error details when a
        request fails. At the end, it summarizes the number of successful and failed relationship creations.
        Args:
            entity_m (str): Name of the source entity column in the DataFrame, used to construct the primary record reference.
            entity_n (str): Name of the target entity column in the DataFrame, used to construct the related record reference.
            m_to_n_relationship (str): The relationship name that defines how entity_m is related to entity_n in the API.
            df (pd.DataFrame): A DataFrame containing rows with column names matching entity_m and entity_n. Each row represents a pair
                               of records to be linked.
        """
        insert_m_n_headers = dict(self.session.headers)

        successful_updates = 0
        failures = 0
        expected_updates = len(df)

        for idx, row in df.iterrows():
            record_m = row[entity_m]
            record_n = row[entity_n]
            
            requestURI = f'{self.environmentURI}api/data/v9.2/{entity_m}({record_m})/{relationship_name}/$ref'
            odata_id = f'{self.environmentURI}api/data/v9.2/{entity_n}({record_n})'
            payload = { "@odata.id": odata_id }

            r = self.session.post(requestURI, headers=insert_m_n_headers, json=payload)
            
            if r.status_code != 204:
                failures += 1
                logging.error(f'Error linking {record_m} to {record_n}. Error {r.status_code}: \n{r.content.decode('utf-8')}\n')
            
            else:
                successful_updates += 1
                
            if idx % 10 == 0: # type: ignore
                print(f"Processed: {idx + 1}") # type: ignore
                
        print(f'{successful_updates} updates made of {expected_updates} expected updates.\n{failures} failures.') 
        
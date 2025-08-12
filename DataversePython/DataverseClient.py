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
            entity (str): The logical name of the Dataverse entity to insert rows into. Use PLURAL form (e.g. accounts, contacts).
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
        Upserts rows for a specified Dynamics 365 entity using data from a pandas DataFrame.
        This method iterates over each row in the provided DataFrame, constructs a PATCH request for each record,
        and updates the corresponding entity in Dynamics 365 based on the primary key. The method can be configured
        to only update existing records or to create new ones if they do not exist. It tracks and logs the number
        of successful updates and failures.
        Args:
            entity (str):
                The name of the Dynamics 365 entity to update. Use PLURAL form (e.g. accounts, contacts).
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
        else:
            upsert_headers.update({'If-None-Match': '*'})

        records = json.loads(df.drop(columns=f'{primary_key_col}').to_json(orient="records"))

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

    def merge_rows(self, entity: Literal["account", "contact"], df:pd.DataFrame, is_master_col: str, duplicate_family_col: str, perform_parenting_checks:bool = True, primary_key_col = None) -> None:
        """
        Merges duplicate rows into master record in Microsoft Dataverse.
        This function identifies master and subordinate records in the provided DataFrame based on the `is_master_col` and `duplicate_family_col` columns.
        For each master record, it merges all subordinate records that share the same duplicate family ID into the master record using the Dataverse Merge API.
        Args:
            entity (Literal["account", "contact"]): The Dataverse entity type to merge (e.g., "account" or "contact").
            df (pd.DataFrame): The DataFrame containing records to be merged. Must include columns for master/subordinate identification and duplicate family grouping.
            is_master_col (str): The name of the column indicating whether a row is a master record (True) or subordinate (False).
            duplicate_family_col (str): The name of the column that groups records into duplicate families.
            perform_parenting_checks (bool, optional): Whether to perform parenting checks during the merge. Defaults to True.
            primary_key_col (str, optional): The name of the primary key column. If None, defaults to '{entity}id'.
        Note:
            This function sends HTTP POST requests to the Dataverse Merge API for each subordinate to be merged into its master.
            The DataFrame is expected to be pre-processed to identify master and subordinate records.
        """
        merge_headers = dict(self.session.headers)
        merge_headers.update({'Content-Type': 'application/json; charset=utf-8'})
        
        requestURI = f'{self.environmentURI}api/data/v9.2/Merge'
        
        masterDF = df[df[is_master_col] == True]
        subordinateDF = df[df[is_master_col] == False]


        for idx, row in masterDF.iterrows():
            if primary_key_col is None:
                masterID: str = row[f'{entity}id']
            else:
                masterID: str = row[str(primary_key_col)]

            completeRow = row.to_dict()
            completeRow['@odata.type'] = f"Microsoft.Dynamics.CRM.{entity}"
            completeRow.pop(is_master_col, None)
            completeRow.pop(duplicate_family_col, None)
            if primary_key_col is None:
                completeRow.pop(f'{entity}id', None)
            else:
                completeRow.pop(primary_key_col, None)

            duplicateFamilyID = row[duplicate_family_col]
            subordinates = subordinateDF[subordinateDF[duplicate_family_col] == duplicateFamilyID]
            
            if len(subordinates) == 0:
                self.logger.warning(f"No subordinates found for master ID: {masterID} with duplicate family ID: {duplicateFamilyID}. Skipping merge.")
                continue

            self.logger.debug(f"Processing master ID: {masterID} with duplicate family ID: {duplicateFamilyID} found: {len(subordinates)} subordinates.")
            self.logger.debug(completeRow)

            for subordinateIdx, subordinateRow in subordinates.iterrows():
                if primary_key_col is None:
                    subordinateID: str = subordinateRow[f'{entity}id']
                else:
                    subordinateID: str = subordinateRow[primary_key_col]
                
                payload = {
                    "Target": {
                        "@odata.type": f"Microsoft.Dynamics.CRM.{entity}",
                        f"{entity}id": masterID
                    },
                    "Subordinate": {
                        "@odata.type": f"Microsoft.Dynamics.CRM.{entity}",
                        f"{entity}id": subordinateID
                    },
                    "UpdateContent": completeRow,
                    "PerformParentingChecks": perform_parenting_checks
                }

                r = self.session.post(url=requestURI, headers=merge_headers, json=payload)
        
                self.logger.debug(f"requestURI: {r.request.method.upper()} {requestURI}") # type: ignore
                self.logger.debug(f"Headers: {merge_headers}")
                self.logger.debug(f"payload: {json.dumps(payload, indent=4)}")

                if r.status_code != 204:
                    self.logger.error(f"Request failed. Error code: {r.status_code}. Response: {r.content.decode('utf-8')}")
                else:
                    self.logger.debug(f"Request successful")


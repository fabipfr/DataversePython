# DataversePython

A Python client for interacting with Microsoft Dataverse (Dynamics 365) Web API, supporting authentication via Azure Entra ID (formerly Azure Active Directory), and providing convenient methods for querying, inserting, upserting, merging, and managing many-to-many relationships in Dataverse entities using pandas DataFrames.

## Features
- **Authentication**: Secure interactive login using MSAL and Azure Entra ID.
- **Querying**: Retrieve entity records as pandas DataFrames with flexible filtering and column selection.
- **Insert/Upsert**: Insert or upsert records from DataFrames into Dataverse entities.
- **Merge**: Merge duplicate records (accounts, contacts) programmatically.
- **Many-to-Many**: Manage many-to-many relationships between entities.
- **Logging**: Detailed logging to `DataverseClient.log` for all operations and errors.

## Installation

Use the following command to install this module:   
```bash
pip install DataversePython
```
After successfully installing it into your python environment you can import the "DataverseClient" class in your code or notebook:    
```python
from DataversePython import DataverseClient
```

## Usage

1. **Setup**
    
    1. Create the required Azure app registration, see [`App Registration Guide`](./APP_REGISTRATION.md).
    
    2. Add the created Service Principal (App Registration) as an application user your environments, see [`Add Application User Guide`](./APPLICATION_USER.md)

    3. Create a JSON config file (see [sample_config.json](./sample_config.json)) with your Azure app registration and Dataverse environment details. The config JSON looks like this:
        ```json
        {
        "environmentURI": "https://<your-org>.crm.dynamics.com/",
        "scopeSuffix": "user_impersonation",
        "clientID": "<your-client-id>",
        "authorityBase": "https://login.microsoftonline.com/",
        "tenantID": "<your-tenant-id>"
        }
        ```

2. **Basic Example**
    ```python
    from DataversePython.DataverseClient import DataverseClient
    import pandas as pd

    # Initialize client
    client = DataverseClient('sample_config.json')

    # Get records
    df = client.get_rows(entity='accounts', top=50, columns=['name', 'emailaddress1'], filter='revenue gt 100000')
    
    print(df.head())
    ```

3. **Insert, Upsert, Merge, and Many-to-Many**
    - See docstrings in `DataverseClient.py` for details on each method.

## Logging

All operations and errors are logged to `DataverseClient.log` in the project root. Reference this log file for troubleshooting.

## Resources

Below are some useful resources and documentation that were referenced during the development of this module:

- [PyConnectDataverse](https://github.com/YesWeCandrew/PyConnectDataverse)
- [Microsoft Dataverse documentation](https://learn.microsoft.com/en-us/power-apps/developer/data-platform/webapi/overview)
- [Azure App Registration documentation](https://learn.microsoft.com/en-us/azure/active-directory/develop/quickstart-register-app)
- [Pandas documentation](https://pandas.pydata.org/docs/)


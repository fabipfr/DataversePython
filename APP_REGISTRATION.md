# App Registration Guide for DataversePython

This guide explains how to create an Azure App Registration for use with the DataversePython module. This is required to authenticate and interact with Microsoft Dataverse (Dynamics 365) via the Web API.

## Steps to Create an App Registration

1. **Sign in to Azure Portal**
   - Go to [https://portal.azure.com](https://portal.azure.com) and sign in with your Azure account.

2. **Register a New Application**
   - Navigate to **App registrations** > **New registration**.
   - Enter a name for your app (e.g., `DataversePythonClient`).
   - Set the supported account types (usually "Accounts in this organizational directory only").
   - For the redirect URI, select "Public client/native (mobile&desktop)" and enter `http://localhost` (required for interactive authentication).
   - Click **Register**.

3. **Configure API Permissions**
   - After registration, go to **Manage** > **API permissions** > **Add a permission**.
   - Select **Microsoft APIs** and search for "Dynamics CRM".
   - Add the delegated permission `user_impersonation`.
   - Click **Add permissions**.

4. **Get Application (Client) ID and Tenant ID**
   - In the app registration overview, copy the **Application (client) ID** and **Directory (tenant) ID**. You will need these for your config .json file.

5. **Update Your Config File**
   - Use the values from your app registration in your `sample_config.json`:
     ```json
     {
       "environmentURI": "https://<your-org>.crm.dynamics.com/",
       "scopeSuffix": "user_impersonation",
       "clientID": "<your-client-id>",
       "authorityBase": "https://login.microsoftonline.com/",
       "tenantID": "<your-tenant-id>"
     }
     ```

If you encounter issues, please consult the Azure documentation or open an issue in this repository.

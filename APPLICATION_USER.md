# Add Application User Guide for DataversePython

This guide explains how to add your Azure App Registration (Service Principal) as an Application User in your Microsoft Dataverse environment using the Power Platform Admin Center.

## Steps to Add an Application User

1. **Open Power Platform Admin Center**
   - Go to [https://admin.powerplatform.microsoft.com/](https://admin.powerplatform.microsoft.com/) and sign in.

2. **Select Your Environment**
   - In the left navigation, click **Manage** >**Environments**.
   - Select the environment where you want to add the application user.

3. **Open Environment Settings**
   - Click on the environment name to open its details.
   - In the top menu, click **Settings**.

4. **Navigate to Users + Permissions**
   - Under **Users + permissions**, click **Application users**.

5. **Add a New Application User**
   - Click **+ New app user**.
   - In the "Create a new app user" pane, click **Add an app**.
   - Search for your app registration by name (the name you used in Azure App Registration).
   - Select your app and click **Add**.

6. **Assign Security Role**
   - Under **Business Unit**, select the appropriate business unit (usually the default one).
   - Under **Security roles**, click **Edit** and select the roles you want to assign (e.g., System Administrator, or a custom role with the required permissions).
   - Click **Save** to finish creating the application user.

7. **Verify**
   - The new application user should now appear in the list. You can edit the user to change roles or details as needed.

---

Your Azure App Registration is now set up as an application user in your Dataverse environment and can authenticate via the API using the assigned permissions.

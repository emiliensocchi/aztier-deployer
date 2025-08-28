# ☁️ Tenant configuration

This page summarizes the **Entra ID configuration** needed to run AzTier.


## 🤖 1. Create a Service Principal (SP) in Entra ID

> 📌 **Why?**  
> AzTier uses GitHub workflows and an Entra ID Service Principal (SP) to securely retrieve role definitions, assignments, and scopes from Azure Resource Manager (ARM) and Microsoft Graph APIs.

### Step 1: Register a Service Principal with Federated Credentials

In your Entra tenant, [register a new application](https://learn.microsoft.com/en-us/entra/identity-platform/quickstart-register-app) and configure a [Federated credential](https://learn.microsoft.com/en-us/entra/workload-id/workload-identity-federation-create-trust?pivots=identity-wif-apps-methods-azp#github-actions) for GitHub Actions. Record the following values:

1. **Tenant ID** for your Entra tenant
2. **Application (client) ID** of the registered app

### Step 2: Configure GitHub Repository Variables

In your [duplicated GitHub repository](https://github.com/emiliensocchi/aztier-deployer/wiki/github_configuration), add the following repository variables:

| Name               | Value                     |
|--------------------|---------------------------|
| `AZURE_TENANT_ID`  | `<your-tenant-id>`        |
| `AZURE_CLIENT_ID`  | `<your-client-id>`        |

---

## 🔑 2. Grant MS Graph Permissions to the SP

> 📌 **Why?**  
> AzTier requires access to Entra role definitions and MS Graph application permissions, which requires specific MS Graph permissions.

Assign the following **application permissions** to the Service Principal in Microsoft Graph:

| Application Permission | Purpose                                               |
|------------------------|------------------------------------------------------|
| [`Application.Read.All`](https://learn.microsoft.com/en-us/graph/permissions-reference#applicationreadall) | Read definitions of application permissions.         |
| [`RoleManagement.Read.Directory`](https://learn.microsoft.com/en-us/graph/permissions-reference#rolemanagementreaddirectory) | Read Entra role definitions.                        |

After assigning these permissions, ensure you grant admin consent for them in the Azure portal.

---

## ☁️ 3. Grant Azure Permissions to the SP

> 📌 **Why?**  
> AzTier needs to read Azure role assignments and scopes, which requires a custom Azure role with specific permissions.

### Step 1: Create a Custom Azure Role

At the Tenant Root Management Group, define a custom role as follows:

| Custom Role Name         | Description                                                                 |
|-------------------------|-----------------------------------------------------------------------------|
| Role assignment reader  | Read Azure scopes, role assignments, and definitions. No resource access.   |

**Required Actions:**

| Action Permission                                         | Purpose                                               |
|-----------------------------------------------------------|-------------------------------------------------------|
| `Microsoft.Authorization/roleAssignments/read`            | Read Azure role assignments (active, eligible, permanent). |
| `Microsoft.Authorization/roleDefinitions/read`            | Read Azure role definitions.                          |
| `Microsoft.Management/managementGroups/read`              | List Management Groups.                               |
| `Microsoft.Resources/subscriptions/read`                  | List subscriptions.                                   |
| `Microsoft.Resources/subscriptions/resourceGroups/read`   | List resource groups.                                 |
| `Microsoft.Resources/subscriptions/resourceGroups/resources/read` | List Azure resources.                        |

For more details, see the [Microsoft.Authorization](https://learn.microsoft.com/en-us/azure/role-based-access-control/permissions/management-and-governance#microsoftauthorization), [Microsoft.Management](https://learn.microsoft.com/en-us/azure/role-based-access-control/permissions/management-and-governance#microsoftmanagement), and [Microsoft.Resources](https://learn.microsoft.com/en-us/azure/role-based-access-control/permissions/management-and-governance#microsoftresources) documentation.

### Step 2: Assign the Custom Role to the SP

Assign the `Role assignment reader` role to your Service Principal at the Tenant Root Management Group scope. This enables the SP to read role assignments across all scopes (subscriptions, resource groups, etc.) without granting access to the contents of Azure resources.

# ⚙️ Project configuration

This page summarizes the different options available to **configure** AzTier.


## 🔧 Backend configuration breakdown

> [!NOTE]
> All backend configuration is centralized in [./config.json](https://github.com/emiliensocchi/aztier-deployer/blob/main/config.json).

The backend supports the following configuration options:

| Configuration name | Possible value(s) | Description | 
|---|---|---|
| `keepLocalChanges` | `true`/`false` |  Whether changes made to built-in assets inherited from [public AzTier](https://github.com/emiliensocchi/azure-tiering) should be kept during the next synchronization, or overwritten with upstream data. This allows to categorize built-in assets differently than upstream. <br>Default value: `false`.
| `includeOnlyRolesInUse` | `true`/`false` | Whether all roles from [public AzTier](https://github.com/emiliensocchi/azure-tiering) should be included during synchronization, or only those that are currently in use in the tenant (i.e. eligibly, actively or permanently assigned). <br>Default value: `true`.


## 🖥️ Frontend configuration breakdown

> [!NOTE]  
> All frontend configuration is centralized in [./app/frontend/config.json](https://github.com/emiliensocchi/aztier-deployer/app/frontend/config.json).

> [!IMPORTANT]  
> `company_name` is the only option necessary to configure for most users. The rest should be modified only if the configuration and data files are consumed differently than via the provided Flask backend (see [architecture](https://github.com/emiliensocchi/aztier-deployer/wiki/architecture) for more info).

The frontend supports the following configuration options:

| Configuration name | Description | 
|---|---|
| `company_name` | The name to be displayed in the AzTier frontend. | 
| `project_configuration_uri` | The URI of the JSON file containing the backend configuration of AzTier. | 
| `tier_definitions` | The URI of the JSON file describing tier definitions. | 
| `tiered_asset_uris` | The URIs of the JSON files with tiered assets (one per asset type: Azure, Entra, MS graph app permissions). |
| `untiered_asset_uris` | The URIs of the JSON files with untiered assets (one per asset type: Azure, Entra, MS graph app permissions). |

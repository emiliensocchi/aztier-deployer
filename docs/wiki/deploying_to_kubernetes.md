# ☸️ Deploying to Kubernetes

This page summarizes the instructions to **deploy AzTier** to Azure Kubernetes Services (AKS).


## ☁️ 1. Import your GitHub PAT to your Azure Key Vault

1. Import the GitHub Personal Access Token (PAT) generated at the end of the [GitHub configuration instructions](https://github.com/emiliensocchi/aztier-deployer/wiki/github_configuration) as a new Secret to your Azure Key Vault.

2. **Take note of its Secret Identifier**, typically in the following form:
    - `https://<your-kv-name>.vault.azure.net/secrets/<your-secret-name>`



## 🐳 2. Build the AzTier container images and push them to your registry

1. **Configure AzTier**  
Make sure you have configured AzTier to your liking (see [project configuration](https://github.com/emiliensocchi/aztier-deployer/wiki/project_configuration)).


2. **Edit [`config.json`](https://github.com/emiliensocchi/aztier-deployer/blob/main/app/frontend/config.json):**  
    Update `http://localhost` with domain name you wish to use for AzTier (e.g. `https://aztier.mydomain.com`).  
    **Note**: the domain will have to be configured separatly to point to the external IP address of your cluster's Ingress.


3. **Build the AzTier container images**  
    Build the frontend and backend components of AzTier into container images, using the provided Dockerfiles. From the root directory of this repository follow these steps:  
    **Frontend:**
    ```sh
    docker build -t <your-acr-name>.azurecr.io/aztier-frontend:latest ./app/frontend/
    ```
    **Backend:**
    ```sh
    docker build -t <your-acr-name>.azurecr.io/aztier-backend:latest ./app/backend/
    ```

4. **Push the images to your Azure Container Registry (ACR)**:  
    **Frontend:**
    ```sh
    docker push <your-acr-name>.azurecr.io/aztier-frontend:latest
    ```
    **Backend:**
    ```sh
    docker push <your-acr-name>.azurecr.io/aztier-backend:latest
    ```



## 🔑 3. Enable Entra Workload Identity on your AKS cluster

To enable secure access to Azure resources from your Kubernetes workloads, configure [Entra Workload Identity](https://learn.microsoft.com/en-us/azure/aks/workload-identity-deploy-cluster). This allows your pods to authenticate without storing credentials in your code or configuration.

Follow these steps:

1. **Install the Workload Identity Webhook Add-on**  
    Use the Azure CLI to enable the workload identity webhook on your AKS cluster:
    ```sh
    az aks update --name <aks-cluster-name> --resource-group <resource-group> --enable-oidc-issuer --enable-workload-identity
    ```

2. **Create a Managed Identity with a Federated Kubernetes Credential** 

    - Create a [user-assigned Managed Identity](https://learn.microsoft.com/en-us/entra/identity/managed-identities-azure-resources/how-manage-user-assigned-managed-identities?pivots=identity-mi-methods-azp).
    - Create a [Federated Credential](https://learn.microsoft.com/en-us/entra/workload-id/workload-identity-federation-create-trust-user-assigned-managed-identity?pivots=identity-wif-mi-methods-azp#kubernetes-accessing-azure-resources) linking your Kubernetes service account to the Managed Identity.

    The Federated Credential should be configured as follows:
    ```yaml
    Cluster Issuer URL: <retrieve-with-az-cli-below>
    Namespace: aztier
    Service Account: aztier-backend-workload-identity
    Subject identifier: system:serviceaccount:aztier:aztier-backend-workload-identity
    Name: aztier-backend-federation
    Audience: api://AzureADTokenExchange
    ```

    Using Azure CLI, the "Cluster Issuer URL" of your AKS cluster can be retrieved as follows ([more info](https://learn.microsoft.com/en-us/azure/aks/use-oidc-issuer#show-the-oidc-issuer-url)):
    ```sh
    az aks show --name myAKScluster --resource-group myResourceGroup --query "oidcIssuerProfile.issuerUrl" -o tsv
    ```

3. **Assign Azure Permissions**  
    Assign the Azure [Key Vault Secrets User](https://learn.microsoft.com/en-us/azure/role-based-access-control/built-in-roles/security#key-vault-secrets-user) role to the Managed Identity.



## 📝 4. Update Kubernetes manifest files with your configuration

Before deploying, customize the Kubernetes manifest files with your environment details:

1. **Edit [`configmap.yaml`](https://github.com/emiliensocchi/aztier-deployer/blob/main/app/k8s/configmap.yaml):**  
    Update the `data` section with your Azure and GitHub settings:
    ```yaml
    AZURE_TENANT_ID: <your-tenant-id>
    AZURE_CLIENT_ID: <your-managed-identity-client-id>
    AZURE_FEDERATED_TOKEN_FILE: /var/run/secrets/azure/tokens/azure-identity-token # should remain unchanged
    AZURE_KEY_VAULT_URL: <your-keyvault-secret-identifier>
    GITHUB_ORGANIZATION: <name-of-your-github-organization>
    GITHUB_REPOSITORY: <name-of-your-duplicated-repository>
    ```

2. **Edit [`serviceaccount.yaml`](https://github.com/emiliensocchi/aztier-deployer/blob/main/app/k8s/serviceaccount.yaml):**
    Update the `azure.workload.identity/client-id` section with the Client Id of your Managed Identity. 

3. **Edit [`ingress.yaml`](https://github.com/emiliensocchi/aztier-deployer/blob/main/app/k8s/ingress.yaml):**  
    Update the `host` section with the domain name you wish to use for AzTier.  
    **Note**: the domain will have to be configured separatly to point to the external IP address of your cluster's Ingress.

4. **Edit [`deployment.yaml`](https://github.com/emiliensocchi/aztier-deployer/blob/main/app/k8s/deployment.yaml):**  
    - Update the `image` sections with the image names pushed to your ACR in [step 2](#-2-build-the-aztier-container-images-and-push-them-to-your-registry).


## 🚀 5. Deploy AzTier to Kubernetes

After updating your manifest files, deploy AzTier to your AKS cluster using the following commands:

```sh
kubectl apply -f namespace.yaml
kubectl apply -f .
```

This sequence will:

- Create the required namespace.
- Configure your environment variables and secrets.
- Set up the service account for workload identity.
- Deploy the AzTier application components.

Monitor your deployment with:

```sh
kubectl get pods -n aztier
```

Check logs for troubleshooting:

```sh
kubectl logs -n aztier <pod-name>
```

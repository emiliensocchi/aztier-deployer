"""
The AzTier backend application, which makes the resources defined in "./app/aztier/config.json" and located in a private GitHub repository available via a Web API.
"""
from azure.identity import DefaultAzureCredential, WorkloadIdentityCredential
from azure.keyvault.secrets import SecretClient
from flask import Flask, jsonify, make_response
from kubernetes import client, config
import os
import requests


# Initialize Flask app
app = Flask(__name__)


# Helpers functions #######################################################################

def get_secret_from_key_vault(vault_url, secret_name):
    """
    Retrieve a secret from an Azure Key Vault using Azure Workload Identity.

    Args:
        vault_url (str): The URL of the Azure Key Vault.
        secret_name (str): The name of the secret to retrieve.

    Returns:
        str: The value of the secret.
    """
    tenant_id = os.environ["AZURE_TENANT_ID"]
    client_id = os.environ["AZURE_CLIENT_ID"]
    token_file = os.environ["AZURE_FEDERATED_TOKEN_FILE"]
    credential = WorkloadIdentityCredential(
        tenant_id=tenant_id,
        client_id=client_id,
        token_file_path=token_file
    )
    client = SecretClient(vault_url=vault_url, credential=credential)
    secret = client.get_secret(secret_name)
    return secret.value



# Routing functions ##########################################################################

@app.route('/api/tier-definitions')
def api_get_tier_definitions():
    """
    Get the tier definitions from the GitHub repository.

    Returns:
        JSON response from the GitHub API.
    """
    file_path_to_serve = 'tier_definitions.json'
    token = app.config["GITHUB_PAT_TOKEN"]
    headers = {
        'Authorization': f'token {token}',
        'Accept': 'application/vnd.github.v3.raw'
    }
    url = f'https://api.github.com/repos/{app.config["GITHUB_ORGANIZATION"]}/{app.config["GITHUB_REPOSITORY"]}/contents/{file_path_to_serve}'
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    
    resp = make_response(jsonify(response.json()))
    resp.headers['Access-Control-Allow-Origin'] = '*'
    return resp


@app.route('/api/project-config')
def api_get_project_config():
    """
    Get the project configuration from the GitHub repository.

    Returns:
        JSON response from the GitHub API.
    """
    file_path_to_serve = 'config.json'
    token = app.config["GITHUB_PAT_TOKEN"]
    headers = {
        'Authorization': f'token {token}',
        'Accept': 'application/vnd.github.v3.raw'
    }
    url = f'https://api.github.com/repos/{app.config["GITHUB_ORGANIZATION"]}/{app.config["GITHUB_REPOSITORY"]}/contents/{file_path_to_serve}'
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    
    resp = make_response(jsonify(response.json()))
    resp.headers['Access-Control-Allow-Origin'] = '*'
    return resp


@app.route('/api/azure/tiered-roles')
def api_get_azure_tiered_roles():
    """
    Get the tiered roles for Azure from the GitHub repository.

    Returns:
        JSON response from the GitHub API.
    """
    file_path_to_serve = 'Azure roles/tiered-azure-roles.json'
    token = app.config["GITHUB_PAT_TOKEN"]
    headers = {
        'Authorization': f'token {token}',
        'Accept': 'application/vnd.github.v3.raw'
    }
    # Encode the file path to handle spaces and special characters
    url = f'https://api.github.com/repos/{app.config["GITHUB_ORGANIZATION"]}/{app.config["GITHUB_REPOSITORY"]}/contents/{file_path_to_serve}'
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    
    resp = make_response(jsonify(response.json()))
    resp.headers['Access-Control-Allow-Origin'] = '*'
    return resp


@app.route('/api/azure/untiered-roles')
def api_get_azure_untiered_roles():
    """
    Get the untiered roles for Azure from the GitHub repository.

    Returns:
        JSON response from the GitHub API.
    """
    file_path_to_serve = 'Azure roles/untiered-azure-roles.json'
    token = app.config["GITHUB_PAT_TOKEN"]
    headers = {
        'Authorization': f'token {token}',
        'Accept': 'application/vnd.github.v3.raw'
    }
    url = f'https://api.github.com/repos/{app.config["GITHUB_ORGANIZATION"]}/{app.config["GITHUB_REPOSITORY"]}/contents/{file_path_to_serve}'
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    
    resp = make_response(jsonify(response.json()))
    resp.headers['Access-Control-Allow-Origin'] = '*'
    return resp


@app.route('/api/entra/tiered-roles')
def api_get_entra_tiered_roles():
    """
    Get the tiered roles for Entra from the GitHub repository.

    Returns:
        JSON response from the GitHub API.
    """
    file_path_to_serve = 'Entra roles/tiered-entra-roles.json'
    token = app.config["GITHUB_PAT_TOKEN"]
    headers = {
        'Authorization': f'token {token}',
        'Accept': 'application/vnd.github.v3.raw'
    }
    url = f'https://api.github.com/repos/{app.config["GITHUB_ORGANIZATION"]}/{app.config["GITHUB_REPOSITORY"]}/contents/{file_path_to_serve}'
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    
    resp = make_response(jsonify(response.json()))
    resp.headers['Access-Control-Allow-Origin'] = '*'
    return resp


@app.route('/api/entra/untiered-roles')
def api_get_entra_untiered_roles():
    """
    Get the untiered roles for Entra from the GitHub repository.

    Returns:
        JSON response from the GitHub API.
    """
    file_path_to_serve = 'Entra roles/untiered-entra-roles.json'
    token = app.config["GITHUB_PAT_TOKEN"]
    headers = {
        'Authorization': f'token {token}',
        'Accept': 'application/vnd.github.v3.raw'
    }
    url = f'https://api.github.com/repos/{app.config["GITHUB_ORGANIZATION"]}/{app.config["GITHUB_REPOSITORY"]}/contents/{file_path_to_serve}'
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    
    resp = make_response(jsonify(response.json()))
    resp.headers['Access-Control-Allow-Origin'] = '*'
    return resp


@app.route('/api/msgraph/tiered-permissions')
def api_get_msgraph_tiered_permissions():
    """
    Get the tiered permissions for MS Graph from the GitHub repository.

    Returns:
        JSON response from the GitHub API.
    """
    file_path_to_serve = 'Microsoft Graph application permissions/tiered-msgraph-app-permissions.json'
    token = app.config["GITHUB_PAT_TOKEN"]
    headers = {
        'Authorization': f'token {token}',
        'Accept': 'application/vnd.github.v3.raw'
    }
    url = f'https://api.github.com/repos/{app.config["GITHUB_ORGANIZATION"]}/{app.config["GITHUB_REPOSITORY"]}/contents/{file_path_to_serve}'
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    
    resp = make_response(jsonify(response.json()))
    resp.headers['Access-Control-Allow-Origin'] = '*'
    return resp


@app.route('/api/msgraph/untiered-permissions')
def api_get_msgraph_untiered_permissions():
    """
    Get the untiered permissions for MS Graph from the GitHub repository.

    Returns:
        JSON response from the GitHub API.
    """
    file_path_to_serve = 'Microsoft Graph application permissions/untiered-msgraph-app-permissions.json'
    token = app.config["GITHUB_PAT_TOKEN"]
    headers = {
        'Authorization': f'token {token}',
        'Accept': 'application/vnd.github.v3.raw'
    }
    url = f'https://api.github.com/repos/{app.config["GITHUB_ORGANIZATION"]}/{app.config["GITHUB_REPOSITORY"]}/contents/{file_path_to_serve}'
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    
    resp = make_response(jsonify(response.json()))
    resp.headers['Access-Control-Allow-Origin'] = '*'
    return resp



# Main #######################################################################################

if __name__ == '__main__':
    # Get Azure Workload Identity parameters 
    app.config['AZURE_TENANT_ID'] = os.environ["AZURE_TENANT_ID"]
    app.config['AZURE_CLIENT_ID'] = os.environ["AZURE_CLIENT_ID"]
    app.config['AZURE_FEDERATED_TOKEN_FILE'] = os.environ["AZURE_FEDERATED_TOKEN_FILE"]

    # Get GitHub Organization and Repository name used for storage
    app.config['GITHUB_ORGANIZATION'] = os.environ['GITHUB_ORGANIZATION']
    app.config['GITHUB_REPOSITORY'] = os.environ['GITHUB_REPOSITORY']

    # Get GitHub PAT token from Azure Key Vault
    az_keyvault_secret_uri = os.environ['AZURE_KEY_VAULT_URL']
    splitted_az_keyvault_secret_uri = az_keyvault_secret_uri.split('/secrets/')
    az_keyvault_uri = splitted_az_keyvault_secret_uri[0]
    az_keyvault_secret_name = splitted_az_keyvault_secret_uri[1]
    github_pat_token = get_secret_from_key_vault(az_keyvault_uri, az_keyvault_secret_name)
    app.config['GITHUB_PAT_TOKEN'] = github_pat_token

    # Start the webserver
    app.run(host='0.0.0.0', port=5000)

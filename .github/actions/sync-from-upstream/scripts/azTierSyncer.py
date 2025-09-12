"""
    Name: 
        AzTierSyncer
        
    Author: 
        Emilien Socchi

    Description:  
        AzTierSyncer synchronizes the following built-in assets with the upstream Azure Administrative Tiering (AAT) project:
            - Azure roles
            - Entra roles
            - MS Graph application permissions

    References:
        https://github.com/emiliensocchi/azure-tiering

    Requirements:
        - A service principal with the following access:
            1. Granted application permissions in MS Graph:
                a. 'RoleManagement.Read.Directory' (to read Entra role definitions)
                b. 'Application.Read.All' (to read the definitions of application permissions)
            2. Granted Azure role actions on the Tenant Root Management Group (to read Azure role definitions at every scope):
                a. Microsoft.Authorization/roleAssignments/read
                b. Microsoft.Authorization/roleDefinitions/read
                c. Microsoft.Management/managementGroups/read
                d. Microsoft.Resources/subscriptions/read
                e. Microsoft.Resources/subscriptions/resourceGroups/read
                f. Microsoft.Resources/subscriptions/resourceGroups/resources/read
        - Valid access tokens for ARM and MS Graph are expected to be available to AzTierWatcher via the following environment variables:
            - 'ARM_ACCESS_TOKEN'
            - 'MSGRAPH_ACCESS_TOKEN'

"""
import json
import os
import requests
import sys
import time
import uuid


# ARM functions ###################################################################################################################################################

def get_arm_access_token():
    """
        Acquires an ARM access token using the GitHub-issued OIDC token.
        
        Returns:
            str: The acquired ARM access token.

    """
    azure_tenant_id = os.environ["AZURE_TENANT_ID"]
    azure_client_id = os.environ["AZURE_CLIENT_ID"]
    github_action_token = os.environ.get('ACTIONS_ID_TOKEN_REQUEST_TOKEN')
    github_action_uri = os.environ.get('ACTIONS_ID_TOKEN_REQUEST_URL')

    # Get Github OIDC token
    endpoint = f"{github_action_uri}&audience=api://AzureADTokenExchange"
    headers = {'Authorization': f"Bearer {github_action_token}"}
    oidc_response = requests.get(endpoint, headers = headers)
    github_oidc_token = oidc_response.json()["value"]

    # Get ARM token
    endpoint = f"https://login.microsoftonline.com/{azure_tenant_id}/oauth2/v2.0/token"
    body = {
        "client_id": azure_client_id,
        "scope": "https://management.azure.com/.default",
        "grant_type": "client_credentials",
        "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
        "client_assertion": github_oidc_token
    }
    response = requests.post(endpoint, data = body)
    access_token = response.json().get("access_token")

    return access_token


def is_pim_enabled_for_arm():
    """
        Checks if the passed token has access to the PIM endpoints.

        Returns:
            bool: True if PIM is enabled, False otherwise

    """
    token = get_arm_access_token()
    endpoint = 'https://management.azure.com/providers/Microsoft.Authorization/roleEligibilityScheduleInstances?$filter=asTarget()&api-version=2020-10-01'
    headers = {'Authorization': f"Bearer {token}"}
    response = requests.get(endpoint, headers = headers)

    if response.status_code == 200:
        return True

    return False


def send_batch_request_to_arm(batch_requests):
    """
        Sends the passed batch requests to ARM, while handling pagination, throttling and other errors to return a complete response.

        More info:
            https://learn.microsoft.com/en-us/azure/azure-resource-manager/management/request-limits-and-throttling
        
        Args:
            batch_requests(list(dict)): list of batch requests to send to ARM

        Returns:
            list(dict): list of responses from ARM
    
    """
    def send_http_get_request(request, headers):
        """
            Sends an HTTP request and handles request exceptions.

            Args:
                request(str): the HTTP request to send
                headers(dict): the headers to include in the HTTP request
            
            Returns:
                requests.models.Response: the returned HTTP response

        """
        try:
            response = requests.get(request, headers = headers)
            return response
        
        except requests.exceptions.RequestException as e:
            default_wait_time = 60
            print(f"FATAL ERROR - An error occurred while checking the status of the asynchronous response: {e}")
            print (f"Sleep for {default_wait_time} seconds before retrying")
            time.sleep(default_wait_time)
            response = send_http_get_request(request, headers)
            return response


    def handle_asynchronous_http_responses(http_response):
        """
            Handles asynchronous HTTP responses from ARM, including pagination.

            Args:
                http_response(requests.models.Response): the HTTP response from ARM

            Returns:
                list(dict): list of responses from ARM

        """
        all_responses = []

        if http_response.status_code == 202:
            # Responses are processed asynchronously and served paginated
            retry_after_x_seconds = int(http_response.headers.get('Retry-After'))
            page_response = http_response

            while page_response.status_code == 202:
                # Check status periodically until the response is ready
                time.sleep(retry_after_x_seconds) 
                page = http_response.headers.get('Location')
                page_response = send_http_get_request(page, headers = headers)

            if page_response.status_code != 200:
                # The asynchronous response has failed and there is a problem with the API
                print ("FATAL ERROR - The asynchronous response from ARM has failed. There is an unknown issue with the API.")
                return None

            # The response is ready
            paginated_response = page_response.json()['value']
            all_responses += paginated_response
            next_page = page_response.json()['nextLink'] if 'nextLink' in page_response.json() else ''

            while next_page:
                # There are more pages to retrieve                    
                next_page_response = send_http_get_request(next_page, headers = headers)

                while next_page_response.status_code == 202:
                    # The next page is not ready yet, wait and retry
                    time.sleep(retry_after_x_seconds)

                # The next page is ready
                all_responses += next_page_response.json()['value']
                next_page = next_page_response.json()['nextLink'] if 'nextLink' in next_page_response.json() else ''

        elif http_response.status_code == 200:
            # The response is synchronous and ready
            if 'responses' in http_response.json():
                # The response is a multi-paginated response
                return http_response.json()['responses']
            
            elif 'value' in http_response.json():
                # The response is a single-paginated response
                return http_response.json()['value']
            
            # The response is a single non-paginated response
            return http_response.json()
        
        else:
            # The response has failed and there is a problem with the API
            print ("FATAL ERROR - The response from ARM is not valid. There is an unknown issue with the API.")
            return None

        return all_responses

    # Main function logic
    complete_response = []

    # Divide the passed batch into smaller chunks to stay within API limits
    batch_request_size_limit = 500
    chunked_batch_requests = [batch_requests[i:i + batch_request_size_limit] for i in range(0, len(batch_requests), batch_request_size_limit)]
    
    for chunked_batch_request in chunked_batch_requests:
        # Get a new ARM token for each chunk
        token = get_arm_access_token()
        remaining_requests = chunked_batch_request
        
        # Loop until no request is throttled
        while remaining_requests:
            # Create and send the batch request
            endpoint = 'https://management.azure.com/batch?api-version=2021-04-01'
            headers = {'Authorization': f"Bearer {token}"}
            body = { 
                'requests': remaining_requests
            }
            http_response = requests.post(endpoint, headers = headers, json = body)
            asynchronous_responses = handle_asynchronous_http_responses(http_response)

            # Analyze HTTP responses #######################################################################################################

            # 200 - Identify successful requests
            successful_responses = [response for response in asynchronous_responses if response['httpStatusCode'] == 200]
            complete_response += successful_responses

            # 429 - Identify throttled requests
            throttled_responses = [response for response in asynchronous_responses if response['httpStatusCode'] == 429]

            # 404 - Identify requests for resources that existed when retrieving scopes, but have been removed since then
            responses_for_removed_scopes = [response for response in asynchronous_responses if response['httpStatusCode'] == 404]

            # 500 - Identify requests that have failed due to server errors
            server_error_responses = [response for response in asynchronous_responses if response['httpStatusCode'] == 500]

            # 503 - Identify requests that have failed due to service unavailability
            service_unavailable_responses = [response for response in asynchronous_responses if response['httpStatusCode'] == 503]

            # Any - Identify other failed requests
            other_responses = [response for response in asynchronous_responses if response['httpStatusCode'] != 200 and response['httpStatusCode'] != 429 and response['httpStatusCode'] != 404 and response['httpStatusCode'] != 500 and response['httpStatusCode'] != 503]
            
            # Handle unsuccessful requests #################################################################################################
            remaining_requests = []

            # Any - Handle failed requests with unhandled HTTP status codes
            if other_responses:
                print("Responses received from ARM with unhandled HTTP status codes:")
                c = 0 
                for response in other_responses:
                    print(f"Response {c + 1}:")
                    print(f"Name: {response.get('status', '')}")
                    print(f"Headers: {response.get('headers', {})}")
                    print(f"Body (text): {response.get('content', '')}")
                    c += 1
                print()

            # 500 - Handle requests that have failed due to server errors
            if server_error_responses:
                default_wait_time = 60
                print (f"Server error - Sleep for {default_wait_time} seconds before retrying")
                time.sleep(default_wait_time)

            # 503 - Handle requests that have failed due to service unavailability
            if service_unavailable_responses:
                default_wait_time = 60
                print (f"Service unavailable - Sleep for {default_wait_time} seconds before retrying")
                time.sleep(default_wait_time)

            # Collect failed requests for retry
            failed_responses = server_error_responses + service_unavailable_responses
            for failed_response in failed_responses:
                failed_response_name = failed_response['name']
                failed_request = next((r for r in chunked_batch_request if r['name'] == failed_response_name), None)
                remaining_requests.append(failed_request)

            # 429 - Handle throttled requests
            if throttled_responses:
                # Collect throttled requests for retry
                for throttled_response in throttled_responses:
                    throttled_response_name = throttled_response['name']
                    throttled_request = next((r for r in chunked_batch_request if r['name'] == throttled_response_name), None)
                    remaining_requests.append(throttled_request)
                    
                # Calculate average 'Retry-After' header value across all throttled responses
                default_wait_time = 20
                retry_after_headers = [r['headers']['Retry-After'] for r in throttled_responses if ('headers' in r and 'Retry-After' in r['headers'])]
                total_retry_after = sum(int(h) for h in retry_after_headers) if retry_after_headers else 0
                avg_retry_after = (total_retry_after / len(retry_after_headers)) if total_retry_after else default_wait_time

                # Sleep for the average 'Retry-After' duration before retrying
                print(f"Throttled request - Sleep for: {avg_retry_after} seconds")
                time.sleep(avg_retry_after)
        
        #print (f"DEBUG - End of While: {len(complete_response)}")
        # End of While

    #print (f"DEBUG - Number of batch requests: {len(batch_requests)}")
    #print (f"DEBUG - Number of batch responses: {len(complete_response)}")

    return complete_response


def get_resource_id_of_all_scopes_from_arm():
    """
        Retrieves the resource Id of all scopes in the tenant:
            - Management Groups
            - Subscriptions
            - Resource groups
            - Individual resources

        Returns:
            list(str): list of resource Ids for all scopes in the tenant

    """
    all_scopes = []

    # Get Management groups and Subscriptions
    batch_requests = [
        {
            "httpMethod": "GET",
            "url": "https://management.azure.com/providers/Microsoft.Management/managementGroups?api-version=2021-04-01"
        },
        {
            "httpMethod": "GET",
            "url": "https://management.azure.com/subscriptions?api-version=2021-04-01"
        }
    ]

    http_responses = send_batch_request_to_arm(batch_requests)

    if http_responses is None:
        print('FATAL ERROR - The Azure scopes could not be retrieved from ARM.')
        exit()

    mg_responses = http_responses[0]['content']['value']
    mg_resource_ids = [response['id'] for response in mg_responses]
    subscription_responses = http_responses[1]['content']['value']
    subscription_resource_ids = [response['id'] for response in subscription_responses]

    # Get Resource groups
    batch_requests = []

    for subscription_resource_id in subscription_resource_ids:
        batch_requests.append({
            "name": str(uuid.uuid4()),
            "httpMethod": "GET",
            "url": f"https://management.azure.com{subscription_resource_id}/resourceGroups?api-version=2021-04-01"
        })

    http_responses = send_batch_request_to_arm(batch_requests)
    
    if http_responses is None:
        print('FATAL ERROR - The Azure scopes could not be retrieved from ARM.')
        exit()

    rg_responses = sum([response['content']['value'] for response in http_responses], [])
    rg_resource_ids = [response['id'] for response in rg_responses]

    # Get individual resources
    batch_requests = []

    for rg_resource_id in rg_resource_ids:
        batch_requests.append({
            "name": str(uuid.uuid4()),
            "httpMethod": "GET",
            "url": f"https://management.azure.com{rg_resource_id}/resources?api-version=2021-04-01"
        })

    http_responses = send_batch_request_to_arm(batch_requests)

    if http_responses is None:
        print('FATAL ERROR - The Azure scopes could not be retrieved from ARM.')
        exit()

    resource_responses = sum([response['content']['value'] for response in http_responses], [])
    resource_resource_ids = [response['id'] for response in resource_responses]

    # Merge all scopes
    all_scopes = mg_resource_ids + subscription_resource_ids + rg_resource_ids + resource_resource_ids
    return all_scopes


def get_resource_id_of_higher_scopes_from_arm():
    """
        Retrieves the resource Id of higher scopes in the tenant:
            - Management Groups
            - Subscriptions
            - Resource groups

        Returns:
            list(str): list of resource Ids for higher scopes in the tenant

    """
    higher_scopes = []

    # Get Management groups and Subscriptions
    batch_requests = [
        {
            "httpMethod": "GET",
            "url": "https://management.azure.com/providers/Microsoft.Management/managementGroups?api-version=2021-04-01"
        },
        {
            "httpMethod": "GET",
            "url": "https://management.azure.com/subscriptions?api-version=2021-04-01"
        }
    ]

    http_responses = send_batch_request_to_arm(batch_requests)

    if http_responses is None:
        print('FATAL ERROR - The Azure scopes could not be retrieved from ARM.')
        exit()

    mg_responses = http_responses[0]['content']['value']
    mg_resource_ids = [response['id'] for response in mg_responses]
    subscription_responses = http_responses[1]['content']['value']
    subscription_resource_ids = [response['id'] for response in subscription_responses]

    # Get Resource groups
    batch_requests = []

    for subscription_resource_id in subscription_resource_ids:
        batch_requests.append({
            "name": str(uuid.uuid4()),
            "httpMethod": "GET",
            "url": f"https://management.azure.com{subscription_resource_id}/resourceGroups?api-version=2021-04-01"
        })

    http_responses = send_batch_request_to_arm(batch_requests)
    
    if http_responses is None:
        print('FATAL ERROR - The Azure scopes could not be retrieved from ARM.')
        exit()

    rg_responses = sum([response['content']['value'] for response in http_responses], [])
    rg_resource_ids = [response['id'] for response in rg_responses]

    # Merge higher scopes
    higher_scopes = mg_resource_ids + subscription_resource_ids + rg_resource_ids
    return higher_scopes


def get_role_definition_id_of_assigned_azure_roles_within_scope_from_arm(scope):
    """
        Retrieves the definition Id of all assigned Azure roles within the passed scope.

        Note:
            Uses the traditional role-assignment endpoint for tenants without PIM 
         
        Args:
            scope(list(str)): list of resource Ids to check for existing role assignments

        Returns:
            list(str): list of role definition Ids

    """
    batch_requests = []

    for resource_id in scope:
        batch_requests.append({
            "httpMethod": "GET",
            "name": str(uuid.uuid4()),
            "url": f"https://management.azure.com{resource_id}/providers/Microsoft.Authorization/roleAssignments?api-version=2022-04-01&$filter=atScope()"
        })

    http_responses = send_batch_request_to_arm(batch_requests)

    if http_responses is None:
        print('FATAL ERROR - The assigned Azure role definition Ids could not be retrieved from ARM.')
        exit()
 
    assignment_responses = sum([response['content']['value'] for response in http_responses], [])
    role_definition_ids = [response['properties']['roleDefinitionId'] for response in assignment_responses]    
    unique_role_ids = set()
    unique_role_definition_ids = [role_definition_id for role_definition_id in role_definition_ids if role_definition_id.split("/")[-1] not in unique_role_ids and not unique_role_ids.add(role_definition_id.split("/")[-1])]

    return unique_role_definition_ids


def get_role_definition_id_of_active_azure_roles_within_scope_from_arm(scope):
    """
        Retrieves the definition Id of all active Azure roles within the passed scope.
        
        Note:
            Uses PIM endpoints, which requires an Entra Premium 2 license 
         
        Args:
            scope(list(str)): list of resource Ids to check for existing role assignments

        Returns:
            list(str): list of role definition Ids

    """
    batch_requests = []

    for resource_id in scope:
        batch_requests.append({
            "httpMethod": "GET",
            "name": str(uuid.uuid4()),
            "url": f"https://management.azure.com{resource_id}/providers/Microsoft.Authorization/roleAssignmentScheduleInstances?api-version=2020-10-01&$filter=atScope()"
        })

    http_responses = send_batch_request_to_arm(batch_requests)

    if http_responses is None:
        print('FATAL ERROR - The active Azure role definition Ids could not be retrieved from ARM.')
        exit()
 
    assignment_responses = sum([response['content']['value'] for response in http_responses], [])
    role_definition_ids = [response['properties']['roleDefinitionId'] for response in assignment_responses]    
    unique_role_ids = set()
    unique_role_definition_ids = [role_definition_id for role_definition_id in role_definition_ids if role_definition_id.split("/")[-1] not in unique_role_ids and not unique_role_ids.add(role_definition_id.split("/")[-1])]

    return unique_role_definition_ids


def get_role_definition_id_of_eligible_azure_roles_within_scope_from_arm(scope):
    """
        Retrieves the definition Id of all eligible Azure roles within the passed scope.

        Note:
            Uses PIM endpoints, which requires an Entra Premium 2 license 

        Args:
            scope(list(str)): list of resource Ids to check for existing role assignments

        Returns:
            list(str): list of role definition Ids

    """
    batch_requests = []

    for resource_id in scope:
        batch_requests.append({
            "httpMethod": "GET",
            "name": str(uuid.uuid4()),
            "url": f"https://management.azure.com{resource_id}/providers/Microsoft.Authorization/roleEligibilityScheduleInstances?api-version=2020-10-01&$filter=atScope()"
        })

    http_responses = send_batch_request_to_arm(batch_requests)

    if http_responses is None:
        print('FATAL ERROR - The eligible Azure role definition Ids could not be retrieved from ARM.')
        exit()
 
    assignment_responses = sum([response['content']['value'] for response in http_responses], [])
    role_definition_ids = [response['properties']['roleDefinitionId'] for response in assignment_responses]
    unique_role_ids = set()
    unique_role_definition_ids = [role_definition_id for role_definition_id in role_definition_ids if role_definition_id.split("/")[-1] not in unique_role_ids and not unique_role_ids.add(role_definition_id.split("/")[-1])]

    return unique_role_definition_ids


def get_all_azure_role_definitions_from_arm(role_definition_ids):
    """
        Retrieves the definition of all built-in and custom Azure roles with the passed definition Ids.

        Args:
            role_definition_ids(list): list of role definition Ids to check for existing role assignments

        Returns:
            list(str): list of resource Ids for all scopes that the token has access to

    """
    all_role_definitions = []
    batch_requests = []

    for role_definition_id in role_definition_ids:
        batch_requests.append({
            "httpMethod": "GET",
            "name": str(uuid.uuid4()),
            "url": f"https://management.azure.com{role_definition_id}?api-version=2022-04-01"
        })

    http_responses = send_batch_request_to_arm(batch_requests)

    if http_responses is None:
        print('FATAL ERROR - The Azure role definitions could not be retrieved from ARM.')
        exit()
 
    role_definition_responses = [response['content'] for response in http_responses if response['httpStatusCode'] == 200]

    for role_definition_response in role_definition_responses:
        all_role_definitions.append({
            'roleDefinitionId': role_definition_response['id'],
            'roleId': role_definition_response['name'],
            'roleName': role_definition_response['properties']['roleName'],
            'roleType': role_definition_response['properties']['type'],
            'roleDescription': role_definition_response['properties']['description']
        })

    return all_role_definitions


def get_built_in_azure_role_definitions_from_arm(role_definition_ids):
    """
        Retrieves the definition of all built-in Azure roles with the passed definition Ids.
        Note: 
        
        Args:
            role_definition_ids(list): list of role definition Ids to check for existing role assignments

        Returns:
            list(str): list of resource Ids for all scopes that the token has access to

        Returns:
            list(str): list of custom role definitions

    """
    all_role_definitions = get_all_azure_role_definitions_from_arm(role_definition_ids)
    built_in_role_definitions = [definition for definition in all_role_definitions if definition['roleType'] == 'BuiltInRole']

    return built_in_role_definitions



# Entra functions #################################################################################################################################################

def is_pim_enabled_for_graph():
    """
        Checks if the passed MS Graph token has access to the PIM endpoints.

        Returns:
            bool: True if PIM is enabled, False otherwise

    """
    token = get_msgraph_access_token()
    endpoint = 'https://graph.microsoft.com/v1.0/roleManagement/directory/roleEligibilityScheduleInstances'
    headers = {'Authorization': f"Bearer {token}"}
    response = requests.get(endpoint, headers=headers)

    if response.status_code == 200:
        return True

    return False


def get_role_definition_id_of_active_entra_roles_from_graph():
    """
        Retrieves the Id of all Entra role definitions that are actively assigned in the tenant.

        Note:
            Does NOT use PIM endpoints (i.e. an Entra Premium 2 license is NOT required to call this function)

        Returns:
            list(str): list of role definition Ids
    """
    token = get_msgraph_access_token()
    endpoint = "https://graph.microsoft.com/v1.0/roleManagement/directory/roleAssignments"
    headers = {"Authorization": f"Bearer {token}"}
    role_definition_ids = []
    next_link = endpoint

    while next_link:
        response = requests.get(next_link, headers=headers)

        if response.status_code != 200:
            print('FATAL ERROR - The active Entra role definition Ids could not be retrieved from MS Graph.')
            exit()

        data = response.json()
        assignments = data.get("value", [])

        for assignment in assignments:
            role_definition_id = assignment.get("roleDefinitionId")

            if role_definition_id:
                role_definition_ids.append(role_definition_id)

        next_link = data.get("@odata.nextLink")

    # Remove duplicates
    return list(set(role_definition_ids))


def get_role_definition_id_of_eligible_entra_roles_from_graph():
    """
        Retrieves the Id of all Entra role definitions that are eligibly assigned in the tenant (PIM eligible).

        Note:
            Uses PIM endpoints, which requires an Entra Premium 2 license 

        Returns:
            list(str): list of role definition Ids
    """
    token = get_msgraph_access_token()
    endpoint = "https://graph.microsoft.com/v1.0/roleManagement/directory/roleEligibilityScheduleInstances"
    headers = {"Authorization": f"Bearer {token}"}
    role_definition_ids = []
    next_link = endpoint

    while next_link:
        response = requests.get(next_link, headers=headers)

        if response.status_code != 200:
            print('FATAL ERROR - The eligible Entra role definition Ids could not be retrieved from MS Graph.')
            exit()

        data = response.json()
        eligibles = data.get("value", [])

        for eligible in eligibles:
            role_definition_id = eligible.get("roleDefinitionId")

            if role_definition_id:
                role_definition_ids.append(role_definition_id)

        next_link = data.get("@odata.nextLink")

    # Remove duplicates
    return list(set(role_definition_ids))



# MS Graph functions ##############################################################################################################################################

def get_msgraph_access_token():
    """
        Acquires an MS Graph access token using the GitHub-issued OIDC token.
        
        Returns:
            str: The acquired MS Graph access token.

    """
    azure_tenant_id = os.environ["AZURE_TENANT_ID"]
    azure_client_id = os.environ["AZURE_CLIENT_ID"]
    github_action_token = os.environ.get('ACTIONS_ID_TOKEN_REQUEST_TOKEN')
    github_action_uri = os.environ.get('ACTIONS_ID_TOKEN_REQUEST_URL')

    # Get Github OIDC token
    endpoint = f"{github_action_uri}&audience=api://AzureADTokenExchange"
    headers = {'Authorization': f"Bearer {github_action_token}"}
    oidc_response = requests.get(endpoint, headers = headers)
    github_oidc_token = oidc_response.json()["value"]

    # Get MS Graph token
    endpoint = f"https://login.microsoftonline.com/{azure_tenant_id}/oauth2/v2.0/token"
    body = {
        "client_id": azure_client_id,
        "scope": "https://graph.microsoft.com/.default",
        "grant_type": "client_credentials",
        "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
        "client_assertion": github_oidc_token
    }
    response = requests.post(endpoint, data = body)
    access_token = response.json().get("access_token")

    return access_token


def get_assigned_msgraph_app_permission_ids():
    """
        Retrieves all MS Graph application permission IDs (roleDefinitionIds) assigned to principals in the tenant.

        Returns:
            list(str): list of MS Graph application permission IDs
    """
    token = get_msgraph_access_token()
    endpoint = "https://graph.microsoft.com/v1.0/servicePrincipals?$select=id,appId,appRolesAssignedTo"
    headers = {"Authorization": f"Bearer {token}"}
    permission_ids = set()
    next_link = endpoint

    while next_link:
        response = requests.get(next_link, headers=headers)

        if response.status_code != 200:
            print('FATAL ERROR - The assigned MS Graph application permissions could not be retrieved from MS Graph.')
            exit()

        data = response.json()
        service_principals = data.get("value", [])

        for sp in service_principals:
            sp_id = sp.get("id")
            # Get assigned app roles for this service principal
            app_roles_endpoint = f"https://graph.microsoft.com/v1.0/servicePrincipals/{sp_id}/appRoleAssignments"
            roles_response = requests.get(app_roles_endpoint, headers=headers)

            if roles_response.status_code == 200:
                assignments = roles_response.json().get("value", [])
                for assignment in assignments:
                    app_role_id = assignment.get("appRoleId")
                    if app_role_id:
                        permission_ids.add(app_role_id)

        next_link = data.get("@odata.nextLink")

    return list(permission_ids)



# Helper functions ################################################################################################################################################

def get_tiered_builtin_azure_role_definitions_from_aat():
    """
        Retrieves a list of tiered built-in Azure roles from the Azure Administrative Tiering (AAT) project.
       
        Returns:
            list(): list of dict containing the tiered Azure roles

        References:
            https://github.com/emiliensocchi/azure-tiering

    """
    endpoint = 'https://raw.githubusercontent.com/emiliensocchi/azure-tiering/refs/heads/main/Azure%20roles/tiered-azure-roles.json'
    response = requests.get(endpoint)

    if response.status_code != 200:
        print('FATAL ERROR - The tiered Azure roles could not be retrieved from the AAT project.')
        exit()

    tiered_azure_role_definitions = response.json()
    return tiered_azure_role_definitions


def get_tiered_builtin_entra_role_definitions_from_aat():
    """
        Retrieves a list of tiered built-in Entra roles from the Azure Administrative Tiering (AAT) project.
       
        Returns:
            list(): list of dict containing the tiered Entra roles

        References:
            https://github.com/emiliensocchi/azure-tiering

    """
    endpoint = 'https://raw.githubusercontent.com/emiliensocchi/azure-tiering/refs/heads/main/Entra%20roles/tiered-entra-roles.json'
    response = requests.get(endpoint)

    if response.status_code != 200:
        print('FATAL ERROR - The tiered Entra roles could not be retrieved from the AAT project.')
        exit()

    tiered_entra_role_definitions = response.json()
    return tiered_entra_role_definitions


def get_tiered_builtin_msgraph_app_permission_definitions_from_aat():
    """
        Retrieves a list of tiered built-in MS Graph application permissions from the Azure Administrative Tiering (AAT) project.
       
        Returns:
            list(): list of dict containing the tiered application permissions

        References:
            https://github.com/emiliensocchi/azure-tiering

    """
    endpoint = 'https://raw.githubusercontent.com/emiliensocchi/azure-tiering/refs/heads/main/Microsoft%20Graph%20application%20permissions/tiered-msgraph-app-permissions.json'
    response = requests.get(endpoint)

    if response.status_code != 200:
        print('FATAL ERROR - The tiered MS Graph application permissions could not be retrieved from the AAT project.')
        exit()

    tiered_msgraph_app_permission_definitions = response.json()
    return tiered_msgraph_app_permission_definitions


def find_added_assets(extended_assets, base_assets):
    """
        Compares a base list with a list of extended assets, to determine the assets that have been added to the extended list.

        Args:
            extended_assets(list(dict(str:str))): list of extended assets, whose length is equal to or greater than the base list
            base_assets(list(dict(str:str))): list of base assets to compare with

        Returns:
            list(): added assets

    """
    if len(extended_assets) < len(base_assets):
        print ('FATAL ERROR - Improper use of function: the length of the extended list should be equal to or greater than the length of the base list')
        exit() 

    added_assets = []
    extended_asset_ids = [asset['id'] for asset in extended_assets]
    base_asset_ids = [asset['id'] for asset in base_assets]
    added_asset_ids = [asset_id for asset_id in extended_asset_ids if asset_id not in base_asset_ids]

    if added_asset_ids:
        for added_asset_id in added_asset_ids:
            asset = [asset for asset in extended_assets if asset['id'] == added_asset_id][0]
            added_assets.append(asset)

    return added_assets


def find_removed_assets(extended_assets, base_assets):
    """
        Compares a base list with a list of extended assets, to determine the assets that have been removed from the based list.

        Args:
            extended_assets(list(dict(str:str))): list of extended assets, whose length is equal to or greater than the base list
            base_assets(list(dict(str:str))): list of base assets to compare with
        
        Returns:
            list(): removed assets
            
    """
    if len(extended_assets) < len(base_assets):
        print ('FATAL ERROR - Improper use of function: the length of the extended list should be equal to or greater than the length of the base list')
        exit() 

    removed_assets = []
    extended_asset_ids = [asset['id'] for asset in extended_assets]
    base_asset_ids = [asset['id'] for asset in base_assets]
    removed_asset_ids = [asset_id for asset_id in base_asset_ids if asset_id not in extended_asset_ids]

    if removed_asset_ids:
        for removed_asset_id in removed_asset_ids:
            asset = [asset for asset in base_assets if asset['id'] == removed_asset_id][0]
            removed_assets.append(asset)

    return removed_assets


def find_modified_assets(extended_assets, base_assets):
    """
        Compares a base list with a list of extended assets, to determine the assets that have been modified in the extended list.

        Args:
            extended_assets(list(dict(str:str))): list of extended assets, whose length is equal to or greater than the base list
            base_assets(list(dict(str:str))): list of base assets to compare with

        Returns:
            list(): modified assets

    """
    if len(extended_assets) < len(base_assets):
        print ('FATAL ERROR - Improper use of function: the length of the extended list should be equal to or greater than the length of the base list')
        exit() 

    modified_assets = []

    for base_asset in base_assets:
        base_asset_id = base_asset['id']
        extended_asset = next((asset for asset in extended_assets if asset["id"] == base_asset_id), None)

        if extended_assets:
            base_asset_properties = base_asset.keys()
            extended_asset_properties = extended_asset.keys()

            for base_asset_property in base_asset_properties:
                if base_asset_property in extended_asset_properties:
                    is_asset_modified = base_asset[base_asset_property] != extended_asset[base_asset_property]

                    if is_asset_modified:
                        modified_assets.append(base_asset)

    return modified_assets


def read_tiered_json_file(tiered_json_file):
    """
         Retrieves the content of the passed tiered JSON file.

        Args:
            json_file(str): path to the local tiered JSON file from which the content is retrieved

        Returns:
            list(): the content of the tiered JSON file
    """
    try:
        if os.path.exists(tiered_json_file):
            with open(tiered_json_file, 'r', encoding = 'utf-8') as file:
                file_content = file.read()

                if file_content:
                    return json.loads(file_content)

        with open(tiered_json_file, 'w+', encoding = 'utf-8') as file:
            file.write('[]')
            file.seek(0)
            return json.load(file)
    
    except Exception:
        print('FATAL ERROR - The tiered JSON file could not be retrieved.')
        exit()


def update_tiered_assets(tiered_json_file, tiered_assets):
    """
        Updates the passed file providing an overview of tiered roles and permissions with the passed tiered assets.

        Args:
            tiered_file(str): the local JSON file with tiered roles and permissions
            tiered_assets(list(dict)): the assets to be added to the tiered file

    """
    try:
        with open(tiered_json_file, 'w', encoding = 'utf-8') as file:
            file.write(json.dumps(tiered_assets, indent = 4))
    except FileNotFoundError:
        print('FATAL ERROR - The tiered file could not be updated.')
        exit()


def enrich_asset_with_type(asset, asset_type):
    """
        Enriches the passed asset with the passed type, while keeping the structure of the asset.
    
        Args:
            asset(dict(str:str)): asset to enrich
            asset_type(str): the asset type information used to enrich the asset
    
        Returns:
            dict(str:str): the enriched asset
    
    """
    asset_type = asset_type.lower()
    valid_asset_types = [
        'builtin',
        'custom'
    ]

    if asset_type not in valid_asset_types:
        print ('FATAL ERROR - Improper use of function: the value of the asset_type parameter is invalid. Accepted values are: builtin, custom')
        exit()

    readable_asset_type = 'Built-in' if asset_type == valid_asset_types[0] else 'Custom'
    asset_values = list(asset.items())
    asset_values.insert(3, ('assetType', readable_asset_type))
    return dict(asset_values)


def enrich_asset_with_scope(asset, asset_scope):
    """
        Enriches the passed asset with the passed scope, while keeping the structure of the asset.

        Args:
            asset(dict(str:str)): asset to enrich
            asset_scope(str): the asset scope information used to enrich the asset

        Returns:
            dict(str:str): the enriched asset
    
    """
    asset_values = list(asset.items())
    asset_values.insert(4, ('assignableScope', asset_scope))
    return dict(asset_values)


def run_sync_workflow(keep_local_changes, include_only_roles_in_use, include_individual_resource_scope, role_type, tiered_builtin_roles_from_aat, tiered_all_roles_from_local):
    """
        Synchronizes the passed roles from AAT with local roles. Local changes are either overriden or preserved based on the passed workflow type.

        Args:
            keep_local_changes(bool): the type of workflow to execute, deciding whether local changes should be preserved or overriden from the AAT
            include_only_roles_in_use(bool): whether to include only roles that are currently in use
            include_individual_resource_scope(bool): whether to include individual resource scope in the synchronization
            role_type(str): the type of role to synchronize (accepted values: 'azure', 'entra', 'graph')
            tiered_builtin_roles_from_aat(list(dict)): list of built-in roles from the AAT
            tiered_all_roles_from_local(list(dict)): list of all roles currently tiered locally

        Returns:
            list(dict()): list of synchronized roles with the AAT

    """
    tiered_builtin_roles_from_local = [role for role in tiered_all_roles_from_local if role['assetType'] == 'Built-in']
    role_type = role_type.lower()

    if role_type == 'azure':
        # Added Azure roles
        added_tiered_azure_roles = find_added_assets(tiered_builtin_roles_from_aat, tiered_builtin_roles_from_local)
        all_azure_role_ids_in_use = []

        if include_only_roles_in_use:
            # Check if added roles are in use
            built_in_azure_role_definitions_in_use = []
            is_pim_enabled = is_pim_enabled_for_arm()

            if is_pim_enabled:
                # Get active + eligible roles
                azure_scope_resource_ids = get_resource_id_of_higher_scopes_from_arm() if not include_individual_resource_scope else get_resource_id_of_all_scopes_from_arm()
                active_azure_role_definition_ids = get_role_definition_id_of_active_azure_roles_within_scope_from_arm(azure_scope_resource_ids)
                eligible_azure_role_definition_ids = get_role_definition_id_of_eligible_azure_roles_within_scope_from_arm(azure_scope_resource_ids)
                all_azure_role_definition_ids_in_use = active_azure_role_definition_ids + eligible_azure_role_definition_ids
                all_azure_role_ids_in_use = [role_definition_id.split("/")[-1] for role_definition_id in all_azure_role_definition_ids_in_use]
                built_in_azure_role_definitions_in_use = get_built_in_azure_role_definitions_from_arm(all_azure_role_definition_ids_in_use)
            else:
                # Get permanently assigned roles
                azure_scope_resource_ids = get_resource_id_of_higher_scopes_from_arm() if not include_individual_resource_scope else get_resource_id_of_all_scopes_from_arm()
                all_azure_role_definition_ids_in_use = get_role_definition_id_of_assigned_azure_roles_within_scope_from_arm(azure_scope_resource_ids)
                all_azure_role_ids_in_use = [role_definition_id.split("/")[-1] for role_definition_id in all_azure_role_definition_ids_in_use]
                built_in_azure_role_definitions_in_use = get_built_in_azure_role_definitions_from_arm(all_azure_role_definition_ids_in_use)

            # Filter out only the roles that are in use
            added_tiered_azure_roles = [role for role in added_tiered_azure_roles if role['id'] in [r['roleId'] for r in built_in_azure_role_definitions_in_use]]

        # Enrich and add the roles to the local tiered roles
        for added_azure_role in added_tiered_azure_roles:
            type_enriched_added_azure_role = enrich_asset_with_type(added_azure_role, 'builtin')
            fully_enriched_added_azure_role = enrich_asset_with_scope(type_enriched_added_azure_role, '/')
            tiered_all_roles_from_local.append(fully_enriched_added_azure_role)

        # Modified Azure roles
        if not keep_local_changes:
            modified_tiered_azure_roles = find_modified_assets(tiered_builtin_roles_from_aat, tiered_builtin_roles_from_local)

            for modified_tiered_azure_role in modified_tiered_azure_roles:
                tiered_azure_roles_from_aat = [role for role in tiered_builtin_roles_from_aat if role['id'] == modified_tiered_azure_role['id']]

                if len(tiered_azure_roles_from_aat) > 0:
                    tiered_azure_role_from_aat = tiered_azure_roles_from_aat[0]
                    type_enriched_tiered_azure_role_from_aat = enrich_asset_with_type(tiered_azure_role_from_aat, 'builtin')
                    fully_enriched_added_azure_role = enrich_asset_with_scope(type_enriched_tiered_azure_role_from_aat, '/')
                    index = next((i for i, role in enumerate(tiered_all_roles_from_local) if role['id'] == modified_tiered_azure_role['id']), None)
                    tiered_all_roles_from_local[index] = fully_enriched_added_azure_role

        # Removed Azure roles
        removed_tiered_azure_roles = find_removed_assets(tiered_builtin_roles_from_aat, tiered_builtin_roles_from_local)
        removed_tiered_built_in_azure_role = [role for role in removed_tiered_azure_roles if role['assetType'] == 'Built-in']   # Custom roles should always be preserved

        for removed_azure_role in removed_tiered_built_in_azure_role:
            removed_azure_role_id = removed_azure_role['id']
            tiered_all_roles_from_local = [role for role in tiered_all_roles_from_local if role['id'] != removed_azure_role_id]

        if include_only_roles_in_use:
            # Check if tiered roles are still in use
            tiered_all_roles_from_local = [role for role in tiered_all_roles_from_local if (role['id'] in all_azure_role_ids_in_use or role['assetType'] == 'Custom')]


    elif role_type == 'entra':
        # Added Entra roles
        added_tiered_entra_roles = find_added_assets(tiered_builtin_roles_from_aat, tiered_builtin_roles_from_local)
        all_entra_role_ids_in_use = []

        if include_only_roles_in_use:
            # Check if added roles are in use
            is_pim_enabled = is_pim_enabled_for_graph()

            if is_pim_enabled:
                # Get active + eligible roles
                active_entra_role_definition_ids = get_role_definition_id_of_active_entra_roles_from_graph()
                eligible_entra_role_definition_ids = get_role_definition_id_of_eligible_entra_roles_from_graph()
                all_entra_role_definition_ids_in_use = active_entra_role_definition_ids + eligible_entra_role_definition_ids
                all_entra_role_ids_in_use = [role_definition_id.split("/")[-1] for role_definition_id in all_entra_role_definition_ids_in_use]
                built_in_entra_role_definitions_in_use = [role for role in added_tiered_entra_roles if role['id'] in all_entra_role_definition_ids_in_use]
            else:
                # Get active roles (= permanently assigned)
                all_entra_role_definition_ids_in_use = get_role_definition_id_of_active_entra_roles_from_graph()
                all_entra_role_ids_in_use = [role_definition_id.split("/")[-1] for role_definition_id in all_entra_role_definition_ids_in_use]
                built_in_entra_role_definitions_in_use = [role for role in added_tiered_entra_roles if role['id'] in all_entra_role_definition_ids_in_use]

            # Filter out only the roles that are in use
            added_tiered_entra_roles = [role for role in added_tiered_entra_roles if role['id'] in [r['id'] for r in built_in_entra_role_definitions_in_use]]

        # Enrich and add the roles to the local tiered roles
        for added_entra_role in added_tiered_entra_roles:
            type_enriched_added_entra_role = enrich_asset_with_type(added_entra_role, 'builtin')
            fully_enriched_added_entra_role = enrich_asset_with_scope(type_enriched_added_entra_role, '/')
            tiered_all_roles_from_local.append(fully_enriched_added_entra_role)

        # Modified Entra roles
        if not keep_local_changes:
            modified_tiered_entra_roles = find_modified_assets(tiered_builtin_roles_from_aat, tiered_builtin_roles_from_local)

            for modified_tiered_entra_role in modified_tiered_entra_roles:
                tiered_entra_roles_from_aat = [role for role in tiered_builtin_roles_from_aat if role['id'] == modified_tiered_entra_role['id']]

                if len(tiered_entra_roles_from_aat) > 0:
                    tiered_entra_role_from_aat = tiered_entra_roles_from_aat[0]
                    type_enriched_tiered_entra_role_from_aat = enrich_asset_with_type(tiered_entra_role_from_aat, 'builtin')
                    fully_enriched_tiered_entra_role_from_aat = enrich_asset_with_scope(type_enriched_tiered_entra_role_from_aat, '/')
                    index = next((i for i, role in enumerate(tiered_all_roles_from_local) if role['id'] == modified_tiered_entra_role['id']), None)
                    tiered_all_roles_from_local[index] = fully_enriched_tiered_entra_role_from_aat

        # Removed Entra roles
        removed_tiered_entra_roles = find_removed_assets(tiered_builtin_roles_from_aat, tiered_builtin_roles_from_local)
        removed_tiered_built_in_entra_role = [role for role in removed_tiered_entra_roles if role['assetType'] == 'Built-in']   # Custom roles should always be preserved

        for removed_role in removed_tiered_built_in_entra_role:
            removed_role_id = removed_role['id']
            tiered_all_entra_roles_from_local = [role for role in tiered_all_entra_roles_from_local if role['id'] != removed_role_id]

        if include_only_roles_in_use:
            # Check if tiered roles are still in use
            tiered_all_roles_from_local = [role for role in tiered_all_roles_from_local if (role['id'] in all_entra_role_ids_in_use or role['assetType'] == 'Custom')]

    elif role_type == 'graph':
        # Added MS Graph application permissions
        added_tiered_msgraph_permissions = find_added_assets(tiered_builtin_roles_from_aat, tiered_builtin_roles_from_local)
        all_assigned_msgraph_app_permission_ids = []

        if include_only_roles_in_use:
            # Check if added permissions are in use
            all_assigned_msgraph_app_permission_ids = get_assigned_msgraph_app_permission_ids()
            # Filter out only the permissions that are in use
            added_tiered_msgraph_permissions = [perm for perm in added_tiered_msgraph_permissions if perm['id'] in all_assigned_msgraph_app_permission_ids]

        # Enrich and add the roles to the local tiered roles
        for added_msgraph in added_tiered_msgraph_permissions:
            type_enriched_added_msgraph = enrich_asset_with_type(added_msgraph, 'builtin')
            fully_enriched_added_msgraph = enrich_asset_with_scope(type_enriched_added_msgraph, '/')
            tiered_all_roles_from_local.append(fully_enriched_added_msgraph)

        # Modified MS Graph application permissions
        if not keep_local_changes:
            modified_tiered_msgraph_permisssions = find_modified_assets(tiered_builtin_roles_from_aat, tiered_builtin_roles_from_local)

            for modified_tiered_msgraph in modified_tiered_msgraph_permisssions:
                tiered_msgraph_from_aat = [role for role in tiered_builtin_roles_from_aat if role['id'] == modified_tiered_msgraph['id']]

                if len(tiered_msgraph_from_aat) > 0:
                    tiered_msgraph_from_aat = tiered_msgraph_from_aat[0]
                    type_enriched_tiered_msgraph_from_aat = enrich_asset_with_type(tiered_msgraph_from_aat, 'builtin')
                    fully_enriched_tiered_msgraph_from_aat = enrich_asset_with_scope(type_enriched_tiered_msgraph_from_aat, '/')
                    index = next((i for i, role in enumerate(tiered_all_roles_from_local) if role['id'] == modified_tiered_msgraph['id']), None)
                    tiered_all_roles_from_local[index] = fully_enriched_tiered_msgraph_from_aat

        # Removed MS Graph application permissions
        removed_tiered_msgraph_permisssions = find_removed_assets(tiered_builtin_roles_from_aat, tiered_builtin_roles_from_local)
        removed_tiered_built_in_msgraph_permission = [role for role in removed_tiered_msgraph_permisssions if role['assetType'] == 'Built-in']   # Custom roles should always be preserved

        for removed_role in removed_tiered_built_in_msgraph_permission:
            removed_role_id = removed_role['id']
            tiered_all_roles_from_local = [role for role in tiered_all_roles_from_local if role['id'] != removed_role_id]

        if include_only_roles_in_use:
            # Check if tiered permissions are still in use
            tiered_all_roles_from_local = [role for role in tiered_all_roles_from_local if (role['id'] in all_assigned_msgraph_app_permission_ids or role['assetType'] == 'Custom')]
    else:
        print ('FATAL ERROR - Improper use of function: the value of the role_type parameter is invalid. Accepted values are: azure, entra, graph')
        exit()

    return tiered_all_roles_from_local



if __name__ == "__main__":
    # Set local directory
    github_action_dir_name = '.github'
    absolute_path_to_script = os.path.abspath(sys.argv[0])
    root_dir = absolute_path_to_script.split(github_action_dir_name)[0]

    # Set local config file
    config_file = root_dir + 'config.json'

    # Set local tier files
    azure_dir = root_dir + 'Azure roles'
    entra_dir = root_dir + 'Entra roles'
    app_permissions_dir = root_dir + 'Microsoft Graph application permissions'
    azure_roles_tier_file = f"{azure_dir}/tiered-azure-roles.json"
    entra_roles_tier_file = f"{entra_dir}/tiered-entra-roles.json"
    msgraph_app_permissions_tier_file = f"{app_permissions_dir}/tiered-msgraph-app-permissions.json"

    # Get project configuration from local config file
    project_config = {}
    try:
        with open(config_file, 'r', encoding = 'utf-8') as file:
            project_config = json.load(file)
    except Exception:
        print('FATAL ERROR - The config JSON file could not be retrieved.')
        exit()

    keep_local_changes_config = project_config['keepLocalChanges'].lower()
    include_only_roles_in_use_config = project_config['includeOnlyRolesInUse'].lower()
    include_individual_resource_scope_config = project_config['includeIndividualResourceScope'].lower()
    accepted_values = [ 'false', 'true' ]

    if not keep_local_changes_config in accepted_values:
        print("FATAL ERROR - The 'keepLocalChanges' value set in the project's configuration file is invalid. Accepted values are: 'True', 'False'")
        exit()

    if not include_only_roles_in_use_config in accepted_values:
        print("FATAL ERROR - The 'includeOnlyRolesInUse' value set in the project's configuration file is invalid. Accepted values are: 'True', 'False'")
        exit()

    if not include_individual_resource_scope_config in accepted_values:
        print("FATAL ERROR - The 'includeIndividualResourceScope' value set in the project's configuration file is invalid. Accepted values are: 'True', 'False'")
        exit()

    keep_local_changes = True if keep_local_changes_config == 'true' else False
    include_only_roles_in_use = True if include_only_roles_in_use_config == 'true' else False
    include_individual_resource_scope = True if include_individual_resource_scope_config == 'true' else False


    # AZURE ROLES ##################################################################################################################################################################

    # Update locally-tiered Azure roles with the latest upstream version
    tiered_all_azure_roles_from_local = read_tiered_json_file(azure_roles_tier_file)
    tiered_builtin_azure_roles_from_aat = get_tiered_builtin_azure_role_definitions_from_aat()

    updated_tiered_all_azure_roles_from_local = run_sync_workflow(keep_local_changes, include_only_roles_in_use, include_individual_resource_scope, 'azure', tiered_builtin_azure_roles_from_aat, tiered_all_azure_roles_from_local[:])
    has_aat_been_updated = False if (updated_tiered_all_azure_roles_from_local == tiered_all_azure_roles_from_local) else True

    if has_aat_been_updated:
        has_aat_been_updated = False if (len(updated_tiered_all_azure_roles_from_local) == len(tiered_all_azure_roles_from_local)) else True
        tiered_all_azure_roles_from_local = sorted(updated_tiered_all_azure_roles_from_local, key=lambda x: (x['tier'], x['assetName']))
        update_tiered_assets(azure_roles_tier_file, tiered_all_azure_roles_from_local)

        if has_aat_been_updated:
            if len(updated_tiered_all_azure_roles_from_local) < len(tiered_all_azure_roles_from_local):
                print ('Built-in Azure roles: no change detected in public AzTier, but upstream roles are not used locally anymore and have been removed from tiered assets')
            else:
                print ('Built-in Azure roles: changes have been detected and merged from public AzTier')
        else:
            print ("Built-in Azure roles: no change detected in public AzTier, but local changes have been overridden with upstream data ('keepLocalChanges' is set to 'false')")
    else:
        print ('Built-in Azure roles: no change')


    # ENTRA ROLES ##################################################################################################################################################################

    # Update locally-tiered Entra roles with the latest upstream version
    tiered_all_entra_roles_from_local = read_tiered_json_file(entra_roles_tier_file)
    tiered_builtin_entra_roles_from_aat = get_tiered_builtin_entra_role_definitions_from_aat()

    updated_tiered_all_entra_roles_from_local = run_sync_workflow(keep_local_changes, include_only_roles_in_use, include_individual_resource_scope, 'entra', tiered_builtin_entra_roles_from_aat, tiered_all_entra_roles_from_local[:])
    has_aat_been_updated = False if (updated_tiered_all_entra_roles_from_local == tiered_all_entra_roles_from_local) else True

    if has_aat_been_updated:
        has_aat_been_updated = False if (len(updated_tiered_all_entra_roles_from_local) == len(tiered_all_entra_roles_from_local)) else True
        tiered_all_entra_roles_from_local = sorted(updated_tiered_all_entra_roles_from_local, key=lambda x: (x['tier'], x['assetName']))
        update_tiered_assets(entra_roles_tier_file, tiered_all_entra_roles_from_local)

        if has_aat_been_updated:
            if len(updated_tiered_all_entra_roles_from_local) < len(tiered_all_entra_roles_from_local):
                print ('Built-in Entra roles: no change detected in public AzTier, but upstream roles are not used locally anymore and have been removed from tiered assets')
            else:
                print ('Built-in Entra roles: changes have been detected and merged from public AzTier')
        else:
            print ("Built-in Entra roles: no change detected in public AzTier, but local changes have been overridden with upstream data ('keepLocalChanges' is set to 'false')")
    else:
        print ('Built-in Entra roles: no change')


    # GRAPH PERMISSIONS ############################################################################################################################################################

    # Update locally-tiered MS Graph application permissions with the latest upstream version
    tiered_all_msgraph_app_permissions_from_local = read_tiered_json_file(msgraph_app_permissions_tier_file)
    tiered_builtin_msgraph_app_permissions_from_aat = get_tiered_builtin_msgraph_app_permission_definitions_from_aat()

    updated_tiered_all_msgraph_app_permissions_from_local = run_sync_workflow(keep_local_changes, include_only_roles_in_use, include_individual_resource_scope, 'graph', tiered_builtin_msgraph_app_permissions_from_aat, tiered_all_msgraph_app_permissions_from_local[:])
    has_aat_been_updated = False if (updated_tiered_all_msgraph_app_permissions_from_local == tiered_all_msgraph_app_permissions_from_local) else True

    if has_aat_been_updated:
        has_aat_been_updated = False if (len(updated_tiered_all_msgraph_app_permissions_from_local) == len(tiered_all_msgraph_app_permissions_from_local)) else True
        tiered_all_msgraph_app_permissions_from_local = sorted(updated_tiered_all_msgraph_app_permissions_from_local, key=lambda x: (x['tier'], x['assetName']))
        update_tiered_assets(msgraph_app_permissions_tier_file, tiered_all_msgraph_app_permissions_from_local)

        if has_aat_been_updated:
            if len(updated_tiered_all_msgraph_app_permissions_from_local) < len(tiered_all_msgraph_app_permissions_from_local):
                print ('Built-in MS Graph app permissions: no change detected in public AzTier, but upstream permissions are not used locally anymore and have been removed from tiered assets')
            else:
                print ('Built-in MS Graph app permissions: changes have been detected and merged from public AzTier')
        else:
            print ("Built-in MS Graph app permissions: no change detected in public AzTier, but local changes have been overridden with upstream data ('keepLocalChanges' is set to 'false')")
    else:
        print ('Built-in MS Graph app permissions: no change')

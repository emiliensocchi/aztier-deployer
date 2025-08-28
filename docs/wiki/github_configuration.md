# 🚀 GitHub configuration

This page summarizes the **GitHub configuration** needed to run AzTier.


## ⿻ 1. Duplicate this repository

To replicate this public repository into your internal repository:

1. **Create a new internal repository** in your organization's GitHub account.  
    - Go to your organization on GitHub.
    - Click **New repository**.
    - Set the repository to **Private** or **Internal**.
    - Do not initialize with a README.

2. **Mirror the public repository** into your new internal repository:

    In a terminal, run:
    ```sh
    # Clone the public repository as a bare repo
    git clone --bare https://github.com/emiliensocchi/aztier-deployer.git

    # Push to your new internal repository
    cd aztier-deployer.git
    git push --mirror https://github.com/<your-org>/<your-internal-repo>.git

    # Clean up
    cd ..
    rm -rf aztier-deployer.git
    ```

3. **Clone your internal repository** to start working:
    ```sh
    git clone https://github.com/<your-org>/<your-internal-repo>.git
    ```


## 🔑 2. Create a GitHub Personal Access Token (PAT)

1. In your GitHub account, [create a fine-grained Personal Access Token (PAT)](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens#creating-a-fine-grained-personal-access-token) with the following settings:

    ```yaml
    Repository access: Only select repositories
    Repositories: <your cloned repository>
    Permissions:
        Repository permissions:
        Contents: Read-only
        Metadata: Read-only
    ```
    **Note:** no organization-level permissions are required.

2. After generating the PAT, **copy and save it securely**. You will need it in the [Deploying to Kubernetes](https://github.com/emiliensocchi/aztier-deployer/wiki/deploying_to_kubernetes) step.

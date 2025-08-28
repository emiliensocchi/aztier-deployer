# 📋 Prerequisites

This page summarizes the prerequisites needed to **configure and deploy** AzTier to your Entra tenant.

## 🔑 Requirements

### 👤 Entra ID

An **Entra user** with the following permissions is required:

| Role type | Role name |  Justification |
|---|---|---|
| Azure | [User Access Administrator](https://learn.microsoft.com/en-us/azure/role-based-access-control/built-in-roles/privileged#user-access-administrator) on the [Tenant Root Management group](https://learn.microsoft.com/en-us/azure/governance/management-groups/overview) | Required to create and assign a custom Azure role on the Tenant Root Management group ([more info](./tenant_configuration.md)).
| Entra | [Cloud Application Administrator](https://learn.microsoft.com/en-us/entra/identity/role-based-access-control/permissions-reference#cloud-application-administrator) | Required to create a service principal and grant application permissions required by AzTier ([more info](./tenant_configuration.md)).


### 🚀 GitHub

A GitHub user with the ability to create a [fine-grained Personal Access Token (PAT)](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens#creating-a-fine-grained-personal-access-token) for the repository you are about to clone.

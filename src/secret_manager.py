"""Secret Manager integration for configuration management.

This module provides utilities to fetch secrets from Google Cloud Secret Manager,
enabling single-source-of-truth configuration without .env/tfvars duplication.
"""

import os
from functools import lru_cache

from google.api_core import exceptions as gcp_exceptions
from google.cloud import secretmanager


@lru_cache
def get_secret_manager_client() -> secretmanager.SecretManagerServiceClient:
    """Get cached Secret Manager client."""
    return secretmanager.SecretManagerServiceClient()


def get_secret(
    secret_id: str,
    project_id: str | None = None,
    version: str = "latest",
    default: str | None = None,
) -> str | None:
    """Fetch a secret value from Google Cloud Secret Manager.

    Args:
        secret_id: The secret ID (e.g., 'etude-rag2-db-password-dev')
        project_id: GCP project ID. If None, uses GOOGLE_PROJECT_ID env var.
        version: Secret version (default: 'latest')
        default: Default value if secret is not found

    Returns:
        The secret value as a string, or default if not found.
    """
    project = project_id or os.environ.get("GOOGLE_PROJECT_ID")
    if not project:
        return default

    try:
        client = get_secret_manager_client()
        name = f"projects/{project}/secrets/{secret_id}/versions/{version}"
        response = client.access_secret_version(request={"name": name})
        return response.payload.data.decode("UTF-8")
    except gcp_exceptions.NotFound:
        return default
    except gcp_exceptions.PermissionDenied:
        return default
    except Exception:
        # Fallback to default on any error (e.g., no credentials)
        return default


def build_secret_id(base_name: str, environment: str | None = None) -> str:
    """Build a secret ID with environment suffix.

    Args:
        base_name: Base secret name (e.g., 'db-password')
        environment: Environment name (e.g., 'dev', 'prod').
                     If None, uses ENVIRONMENT env var or defaults to 'dev'.

    Returns:
        Full secret ID (e.g., 'etude-rag2-db-password-dev')
    """
    env = environment or os.environ.get("ENVIRONMENT", "dev")
    return f"etude-rag2-{base_name}-{env}"


# Secret name mappings
SECRET_NAMES = {
    "db_password": "db-password",
    "target_folder_id": "drive-folder-id",
    "my_email": "my-email",
    "service_account_key": "service-account-key",
    # OAuth authentication
    "google_oauth_client_id": "oauth-client-id",
    "google_oauth_client_secret": "oauth-client-secret",
    "session_secret_key": "session-secret-key",
    "allowed_emails": "allowed-emails",
}


def get_app_secret(key: str, default: str | None = None) -> str | None:
    """Get an application secret by its config key.

    Args:
        key: Config key name (e.g., 'db_password', 'target_folder_id')
        default: Default value if secret is not found

    Returns:
        The secret value or default.
    """
    if key not in SECRET_NAMES:
        return default

    secret_id = build_secret_id(SECRET_NAMES[key])
    return get_secret(secret_id, default=default)


def get_app_config() -> dict[str, str]:
    """Get all application configuration from Secret Manager.

    Returns a dictionary with app configuration values stored as JSON
    in the 'etude-rag2-app-config-{env}' secret.

    Returns:
        Dictionary of configuration values, or empty dict if not found.
    """
    import json

    secret_id = build_secret_id("app-config")
    config_json = get_secret(secret_id)

    if not config_json:
        return {}

    try:
        return json.loads(config_json)
    except json.JSONDecodeError:
        return {}

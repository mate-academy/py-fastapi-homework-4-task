from config.settings import BaseAppSettings
from config.dependencies import (
    get_settings,
    get_jwt_auth_manager,
    get_accounts_email_notificator,
    get_s3_storage_client
)
from config.settings import API_LOCAL_URL

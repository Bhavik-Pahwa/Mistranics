from typing import Literal
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = (
        "postgresql+psycopg://mistranics:mistranics@localhost:5432/mistranics"
    )
    api_token: str = ""
    operator_token: str = ""
    internal_token: str = ""
    mqtt_enabled: bool = False
    mqtt_host: str = "localhost"
    mqtt_port: int = 1883
    mqtt_topic: str = "mistranics/+/telemetry"
    mqtt_client_id: str = "mistranics-backend"
    mqtt_username: str | None = None
    mqtt_password: str | None = None
    mqtt_tls: bool = False
    mqtt_ca: str | None = None
    mqtt_cert: str | None = None
    mqtt_key: str | None = None
    mqtt_qos: Literal[0, 1] = 1
    mqtt_reconnect_max: int = Field(30, ge=1)
    registry_file: str = "examples/registry.json"
    policy_file: str | None = None
    max_query_days: int = Field(31, ge=1)
    context_seconds: int = Field(120, ge=60)
    retry_seconds: int = Field(5, ge=0)

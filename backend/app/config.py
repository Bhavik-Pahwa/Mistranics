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
    # Opt-in evaluation mode; legacy database/AI/ML application remains available.
    iot_enabled: bool = False
    iot_topic: str = "indux/device-01/telemetry"
    iot_source: Literal["physical", "simulation"] = "physical"
    iot_physical_device: str = "device-01"
    iot_simulation_device: str = "simulation-01"
    anomaly_z_threshold: float = Field(3.0, gt=0, allow_inf_nan=False)
    anomaly_baseline_size: int = Field(20, ge=5, le=1000)
    anomaly_min_baseline_samples: int = Field(5, ge=2, le=1000)
    anomaly_std_floor: float = Field(0.1, gt=0, allow_inf_nan=False)
    telemetry_stale_after_seconds: float = Field(10, ge=3, le=300)
    registry_file: str = "examples/registry.json"
    policy_file: str | None = None
    max_query_days: int = Field(31, ge=1)
    context_seconds: int = Field(120, ge=60)
    retry_seconds: int = Field(5, ge=0)

    ml_enabled: bool = False
    ml_limits_file: str | None = None
    ml_model_file: str | None = None
    ml_incident_policy_file: str | None = None
    ai_enabled: bool = False
    ai_provider_url: str = "http://localhost:11434"
    ai_provider_token: str = ""
    ai_llm_model: str = ""
    ai_embedding_model: str = ""
    ai_provider_timeout: int = Field(60, ge=1, le=180)
    ai_stale_seconds: int = Field(15, ge=3)
    ai_ocr_enabled: bool = False
    ai_ocr_language: str = "eng"
    ai_max_pdf_pages: int = Field(100, ge=1, le=500)
    ai_max_chunks: int = Field(1000, ge=1, le=5000)

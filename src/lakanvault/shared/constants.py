# shared constants
# chunk size + names that must never ride on the cloud DTO
CHUNK_SIZE_BYTES = 1_048_576

FORBIDDEN_CLOUD_DTO_FIELDS = frozenset({
    "raw_prompt",
    "prompt",
    "model_bytes",
    "api_key",
    "hostname",
    "audit_json",
    "raw_audit",
})

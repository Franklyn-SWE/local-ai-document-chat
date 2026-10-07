# Troubleshooting Log

This document records material development issues, failed approaches,
diagnoses, attempted actions, and resolutions in chronological order.

## Current status

## 2026-10-07 — Editable installation failed due to package discovery

### Symptom

Running:

`pip install -e ".[dev]"`

failed with:

`Multiple top-level packages discovered in a flat-layout`

Setuptools identified application and non-application directories such as
`app`, `ui`, `data`, `demo`, and `evidence` during automatic package discovery.

### Diagnosis

The repository intentionally contains several top-level directories, but only
`app` is intended to be installed as the Python application package.
Relying on automatic setuptools package discovery was therefore ambiguous.

### Resolution

Configured explicit setuptools package discovery in `pyproject.toml` to include
only `app*` and exclude non-package project directories.

Added `__init__.py` files to the application subpackages so their package
boundaries are explicit.

### Result

The project can be installed in editable mode without treating runtime data,
demo fixtures, evidence, UI assets, or tests as Python application packages.

## 2026-10-07 — Static type checker did not understand environment-populated settings

### Symptom

`mypy app` reported that `LLM_URL` and `LLM_MODEL` were missing when
constructing `Settings()`.

### Diagnosis

At runtime, `pydantic-settings` populates these required fields from environment
variables. Vanilla mypy was analysing the constructor as a conventional Python
model and did not account for that settings behaviour.

### Resolution

Enabled the Pydantic mypy plugin so static analysis understands the
Pydantic-generated settings interface.

### Result

Configuration remains fail-fast at runtime while the project also passes
strict static type checking.

## 2026-10-07 — Development Python version did not match intended runtime

### Symptom

The initial virtual environment was created using Python 3.14 because that was
the machine's default Python installation.

### Diagnosis

Using a different interpreter version locally from the version intended for
CI and the container would introduce avoidable environment drift.

### Resolution

Recreated the project virtual environment using Python 3.11 and aligned the
project metadata, Ruff target, and mypy configuration with Python 3.11.

### Result

Local development, testing, static analysis, CI, and the final container can
use the same Python interpreter family.

---

## 2026-10-07 — Local inference integration issues

### Issue 1 — Docker Model Runner was unavailable

**Symptom**

`docker model status` reported that Docker Model Runner was not running, and the local API on port `12434` was unreachable.

**Cause**

Docker Model Runner was disabled in Docker Desktop.

**Resolution**

Enabled Docker Model Runner and verified the service with:

`docker model status`

and:

`curl.exe http://localhost:12434/engines/v1/models`

---

### Issue 2 — Application could not reach the local model

**Symptom**

The `/chat` endpoint selected the correct evidence and started an SSE response, but returned:

`inference_failed: local model is unavailable`

**Cause**

The local `.env` still used:

`http://host.docker.internal:12434/engines/v1`

That hostname is intended for container-to-host access, while FastAPI was running directly on the Windows host.

**Resolution**

Changed the local development configuration to:

`LLM_URL=http://localhost:12434/engines/v1`

Restarted Uvicorn because application settings are cached.

---

### Issue 3 — Initial model quality was too weak

**Symptom**

`SmolLM2 360M Q4_K_M` received the correct retrieved evidence but sometimes claimed the evidence was insufficient even when the answer was explicitly present.

**Resolution**

Evaluated stronger local models while preserving the assessment constraints.

- Qwen2.5 0.5B F16 produced better grounded answers but was rejected for the final configuration because it was not quantized.
- Llama 3.2 `1B-Q4_0` was rejected because Docker reported approximately `1.24B` parameters, exceeding the assessment limit.
- Final model selected:

`huggingface.co/qwen/qwen2.5-0.5b-instruct-gguf:Q4_K_M`

Docker Model Runner reports approximately `630M` parameters and `Q4_K_M` quantization.

The final Qwen model produced a correct grounded answer while remaining local, quantized, and below the one-billion-parameter limit.

---

### Issue 4 — Qwen GGUF pull initially failed

**Symptom**

The first attempt to pull the quantized Qwen model failed with:

`There is not enough space on the disk.`

**Cause**

Insufficient free space on the Windows system drive during the temporary model download/import process.

**Resolution**

Removed unused local models and retried the pull successfully.

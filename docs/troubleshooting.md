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

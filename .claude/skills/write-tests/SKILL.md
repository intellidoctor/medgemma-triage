---
name: write-tests
description: "Write comprehensive tests for: $ARGUMENTS. Use when asked to write tests, add test coverage, or test a module/agent/pipeline. Generates pytest tests following project conventions."
---

# Write Tests

## Conventions

- **Framework**: pytest
- **Location**: `tests/` mirror of `src/` structure
  - `src/agents/intake.py` → `tests/test_agents/test_intake.py`
  - `src/pipeline/orchestrator.py` → `tests/test_pipeline/test_orchestrator.py`
  - `src/fhir/builder.py` → `tests/test_fhir/test_builder.py`
- **Naming**: `test_<module>.py`, functions prefixed with `test_`
- **Imports**: Use relative paths from project root

## What to Test

- **Happy paths** — expected inputs produce correct outputs
- **Edge cases** — empty inputs, boundary values, missing fields
- **Error states** — invalid data raises appropriate exceptions
- **Agent behavior** — correct model calls, prompt construction, output parsing
- **FHIR output** — valid resource structure, required fields present
- **Pipeline flow** — correct agent sequencing, state transitions

## What NOT to Test

- Third-party library internals (fhir.resources, langchain, vertex SDK)
- Model inference quality (that's evaluation, not testing)
- Streamlit UI rendering

## Mocking Strategy

- **Always mock model calls** — `src/models/medgemma.py` functions should be patched, never hit real APIs
- **Always mock external services** — Vertex AI, any HTTP calls
- Use `pytest.fixture` for reusable test data (sample patients, images, triage cases)
- Use `unittest.mock.patch` or `pytest-mock` for patching

## Test Structure

```python
"""Tests for src/agents/<module>.py"""

import pytest
from unittest.mock import patch, MagicMock


class TestFeatureName:
    """Group related tests."""

    def test_happy_path(self):
        """Describe expected behavior."""
        ...

    def test_edge_case(self):
        """Describe the edge case."""
        ...

    def test_error_handling(self):
        """Describe the error condition."""
        ...


@pytest.fixture
def sample_patient_data():
    """Synthetic patient data for testing."""
    return {
        "name": "Maria Silva",
        "age": 45,
        "complaint": "Dor no peito com irradiacao para braco esquerdo",
    }
```

## Running

```bash
# All tests
pytest tests/

# Specific module
pytest tests/test_agents/test_intake.py

# With coverage
pytest --cov=src tests/

# Verbose
pytest -v tests/
```

## Rules

- No real patient data — only synthetic test cases
- No real API calls — all external services must be mocked
- Tests must run offline and without credentials
- Use Portuguese clinical terms in synthetic data to match production usage

#!/usr/bin/env python
# granite_smoke_test.py -- Phase 6.5 live Granite smoke test
#
# PURPOSE:
#   Verifies that the watsonx.ai connection is functional by making one minimal
#   Granite request and checking the response can be parsed.
#
# NEVER run automatically by pytest. Run manually:
#   cd backend
#   python granite_smoke_test.py
#
# EXIT CODES:
#   0  -- success (connected, model responded, JSON parsed)
#   1  -- configuration error (missing or invalid credentials/URL/model)
#   2  -- authentication or authorisation error
#   3  -- model availability error (model not found or not accessible)
#   4  -- network or timeout error
#   5  -- response parsing error (model responded but not valid JSON)
#   9  -- unexpected error
#
# CREDENTIAL SAFETY:
#   This script never prints credential values.
#   It prints only the model ID, latency, and success/failure category.
#   Do not add any print() call that could expose a credential value.
from __future__ import annotations

import json
import sys
import time

# ---------------------------------------------------------------------------
# Step 1: load and validate config
# ---------------------------------------------------------------------------
sys.path.insert(0, ".")

try:
    from config import get_settings
    from granite_client import _validate_config, _ConfigError
except ImportError as exc:
    print(f"[FAIL] Import error: {exc}")
    print("       Run this script from the backend/ directory.")
    sys.exit(9)

s = get_settings()
try:
    _validate_config(s)
except _ConfigError as exc:
    print(f"[FAIL] Configuration error: {exc}")
    print("       Set WATSONX_APIKEY, WATSONX_PROJECT_ID, WATSONX_URL, "
          "WATSONX_MODEL_ID in .env")
    sys.exit(1)

model_id = s.watsonx_model_id
print(f"[INFO] Model ID : {model_id}")
print(f"[INFO] URL      : {s.watsonx_url}")
# Project ID length only -- never print the actual value
print(f"[INFO] Project  : {'*' * len(s.watsonx_project_id)} ({len(s.watsonx_project_id)} chars)")
print(f"[INFO] API key  : {'*' * min(len(s.watsonx_apikey), 8)} (first chars masked)")

# ---------------------------------------------------------------------------
# Step 2: attempt a minimal live generation
# ---------------------------------------------------------------------------
MINIMAL_PROMPT = (
    'Respond with exactly this JSON and nothing else: '
    '{"status": "ok", "message": "smoke test passed"}'
)

print(f"\n[INFO] Sending minimal prompt to {model_id} ...")
t0 = time.perf_counter()

try:
    from ibm_watsonx_ai import Credentials
    from ibm_watsonx_ai.foundation_models import ModelInference
except ImportError as exc:
    print(f"[FAIL] ibm-watsonx-ai not installed: {exc}")
    sys.exit(9)

try:
    creds = Credentials(url=s.watsonx_url, api_key=s.watsonx_apikey)
    model = ModelInference(
        model_id=model_id,
        credentials=creds,
        project_id=s.watsonx_project_id,
    )
    response = model.chat(
        messages=[
            {"role": "user", "content": MINIMAL_PROMPT}
        ],
        params={
            "max_tokens": 60,
            "temperature": 0.0,
        },
    )

except Exception as exc:
    latency = time.perf_counter() - t0
    err_type = type(exc).__name__
    err_msg  = str(exc)

    # Categorise without revealing credentials
    if "401" in err_msg or "403" in err_msg or "Unauthorized" in err_type:
        print(f"[FAIL] Authentication error ({err_type}) after {latency:.2f}s")
        print("       Check WATSONX_APIKEY and WATSONX_PROJECT_ID.")
        sys.exit(2)
    if "404" in err_msg or "model" in err_msg.lower():
        print(f"[FAIL] Model availability error ({err_type}) after {latency:.2f}s")
        print(f"       Model '{model_id}' may not be available in this project.")
        print("       Update WATSONX_MODEL_ID in .env to a deployed model ID.")
        sys.exit(3)
    if "timeout" in err_msg.lower() or "connect" in err_msg.lower():
        print(f"[FAIL] Network error ({err_type}) after {latency:.2f}s")
        print("       Check WATSONX_URL and network connectivity.")
        sys.exit(4)
    print(f"[FAIL] Unexpected API error ({err_type}) after {latency:.2f}s")
    sys.exit(9)

latency = time.perf_counter() - t0
raw_text = response["choices"][0]["message"]["content"]
print(f"[INFO] Response received in {latency:.2f}s")
print(f"[INFO] Raw response (first 200 chars): {raw_text[:200]!r}")

# ---------------------------------------------------------------------------
# Step 3: attempt to parse the response
# ---------------------------------------------------------------------------
try:
    start = raw_text.find("{")
    end   = raw_text.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError("No JSON object found in response")
    data = json.loads(raw_text[start:end])
    print(f"[INFO] Parsed JSON: {data}")
except (ValueError, json.JSONDecodeError) as exc:
    print(f"[FAIL] Response parsing failed: {exc}")
    print(f"       Model responded but did not produce valid JSON.")
    print(f"       Model ID {model_id!r} may not support instruction following.")
    sys.exit(5)

# ---------------------------------------------------------------------------
# Step 4: report result
# ---------------------------------------------------------------------------
print(f"\n[PASS] Smoke test succeeded.")
print(f"       Model   : {model_id}")
print(f"       Latency : {latency:.2f}s")
print(f"       Parsed  : {data}")
sys.exit(0)

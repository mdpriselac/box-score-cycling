"""JSON-boundary tests for generated prediction artifacts."""

import json

import numpy as np

from netlify_site.build.predict_stage_scenarios import json_number


def test_json_number_maps_nonfinite_values_to_null():
    payload = {
        "finite": json_number(np.float64(0.25)),
        "missing": json_number(None),
        "nan": json_number(np.nan),
        "positive_infinity": json_number(np.inf),
        "negative_infinity": json_number(-np.inf),
    }

    encoded = json.dumps(payload, allow_nan=False)

    assert json.loads(encoded) == {
        "finite": 0.25,
        "missing": None,
        "nan": None,
        "positive_infinity": None,
        "negative_infinity": None,
    }

import hashlib, json
params = {
    "retest_depth_max": 0.30,
    "retest_atr_depth_fraction": 0.50,
    "body_ratio_min": 0.65,
    "atr_multiplier_min": 1.50,
    "expansion_atr_min_distance": 0.20
}
canonical = json.dumps(params, sort_keys=True)
h = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
print(h)
print(repr(canonical))
@fused.udf(cache_max_age="1h")
def udf():
    import pandas as pd

    return pd.DataFrame(
        {
            "city": ["Paris", "Lima", "Osaka"],
            "region": ["EU", "SA", "AS"],
            "population": [2_100_000, 9_700_000, 2_700_000],
            "lat": [48.86, -12.05, 34.69],
            "lng": [2.35, -77.04, 135.5],
        }
    )

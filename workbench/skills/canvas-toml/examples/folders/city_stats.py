@fused.udf
def udf(region: str = "EU", min_population: int = 1_000_000):
    df = fused.load("load_cities")()
    return df[(df["region"] == region) & (df["population"] >= min_population)]

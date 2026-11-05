@fused.udf
def udf(path: str = "s3://fused-sample/demo_data/airbnb_listings_sf.parquet"):
    import pandas as pd

    df = pd.read_parquet(
        path,
        columns=["name", "room_type", "price_in_dollar", "latitude", "longitude"],
    )
    df = df.dropna(subset=["price_in_dollar", "latitude", "longitude"])
    df = df.rename(columns={"price_in_dollar": "price", "latitude": "lat", "longitude": "lng"})
    df.insert(0, "id", range(len(df)))
    return df.reset_index(drop=True)

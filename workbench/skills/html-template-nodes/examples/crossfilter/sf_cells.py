@fused.udf
def udf(radius: int = 55):
    import h3
    import numpy as np
    import pandas as pd

    cells = list(h3.grid_disk(h3.latlng_to_cell(37.77, -122.43, 9), radius))
    ll = np.array([h3.cell_to_latlng(c) for c in cells])
    rng = np.random.default_rng(7)
    d = np.hypot(ll[:, 0] - 37.79, (ll[:, 1] + 122.41) * 0.8)
    return pd.DataFrame({
        "hex": cells,
        "lat": ll[:, 0].round(5),
        "lng": ll[:, 1].round(5),
        "temp": (24 - 90 * d + rng.normal(0, 1.5, len(cells))).round(1),
        "kind": rng.choice(["residential", "commercial", "park", "industrial"], len(cells), p=[0.5, 0.2, 0.2, 0.1]),
    })

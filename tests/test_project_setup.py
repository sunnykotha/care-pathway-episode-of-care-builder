import pandas as pd
import care_pathway

def test_package_imports():
    assert care_pathway.__doc__ == "Care pathway and episode-of-care builder."

def test_pandas_works():
    assert pd.DataFrame({"claim_id": [1]}).shape == (1, 1)

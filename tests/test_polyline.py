from app.providers.google import decode_polyline


def test_decode_google_polyline_example() -> None:
    decoded = decode_polyline("_p~iF~ps|U_ulLnnqC_mqNvxq`@")
    assert len(decoded) == 3
    assert decoded[0] == [-120.2, 38.5]
    assert decoded[1] == [-120.95, 40.7]
    assert decoded[2] == [-126.453, 43.252]

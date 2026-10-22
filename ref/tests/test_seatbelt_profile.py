from skillpact.core import _seatbelt_profile

def test_seatbelt_denies_unix_sockets_with_network(tmp_path):
    p = _seatbelt_profile(tmp_path, None, True)
    assert "(deny network-outbound (remote unix-socket))" in p and "mDNSResponder" in p
    assert "(deny network*)" in _seatbelt_profile(tmp_path, None, False)

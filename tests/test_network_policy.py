import pytest

from raven_validator.security.network_policy import NetworkPolicy, UnsafeNetworkTarget


@pytest.mark.parametrize('url',["http://127.0.0.1/v1","http://10.0.0.1","http://192.168.1.10","http://169.254.169.254/latest","http://localhost:8000"])
def test_private_targets_blocked(url):
    with pytest.raises(UnsafeNetworkTarget):
        NetworkPolicy(resolve_dns=False).validate_url(url)


def test_public_literal_allowed():
    assert NetworkPolicy(resolve_dns=False).validate_url('https://8.8.8.8')=='https://8.8.8.8'

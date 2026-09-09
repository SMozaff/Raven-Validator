from raven_validator.credentials.keychain import MemoryKeychain
from raven_validator.credentials.manager import CredentialManager
from raven_validator.domain.credentials import AuthScheme, CredentialProfile


def test_memory_backend_is_explicit_test_dependency():
    backend=MemoryKeychain(); manager=CredentialManager(backend)
    p=CredentialProfile(id='1',display_name='x',auth_type=AuthScheme.BEARER,keychain_username='u')
    manager.store_secret(p,'SECRET')
    assert manager.retrieve_secret(p)=='SECRET'
    assert CredentialManager.build_headers(p,'SECRET')=={'Authorization':'Bearer SECRET'}

import httpx
import pytest
from raven_validator.config.settings import AppSettings
from raven_validator.domain.candidates import APICandidate
from raven_validator.domain.credentials import AuthScheme, CredentialProfile
from raven_validator.services.validation_service import ValidationOptions, ValidationService


@pytest.mark.asyncio
async def test_standard_mode_never_sends_configured_credential():
    seen=[]
    def handler(req:httpx.Request):
        seen.append(dict(req.headers))
        if req.url.path.endswith('/models'):
            return httpx.Response(401,json={"error":"missing authorization"})
        if req.method=='OPTIONS':
            return httpx.Response(404)
        return httpx.Response(401,json={"error":"missing authorization"})
    transport=httpx.MockTransport(handler)
    candidate=APICandidate(name='x',base_url='https://api.example.com/v1',protocol_hint='openai-compatible',credential_profile_id='p1')
    profile=CredentialProfile(id='p1',display_name='p',auth_type=AuthScheme.BEARER,keychain_username='u')
    service=ValidationService(AppSettings(max_requests_per_api=6),lambda c:(profile,'TOPSECRET'),transport=transport,resolve_dns=False)
    await service.validate_one(candidate,ValidationOptions(mode='standard'))
    assert seen
    assert all('authorization' not in {k.lower():v for k,v in h.items()} for h in seen)


@pytest.mark.asyncio
async def test_authorized_anthropic_uses_messages_and_x_api_key():
    requests=[]
    def handler(req:httpx.Request):
        requests.append(req)
        if req.method=='GET' and req.url.path.endswith('/v1'):
            return httpx.Response(401,text='x-api-key required')
        if req.method=='OPTIONS' and req.url.path.endswith('/messages'):
            return httpx.Response(204,headers={'allow':'POST'})
        if req.method=='GET' and req.url.path.endswith('/models'):
            return httpx.Response(200,json={'data':[{'id':'claude-test'}]})
        if req.method=='POST' and req.url.path.endswith('/messages'):
            return httpx.Response(200,json={'content':[{'text':'OK'}]})
        return httpx.Response(404)
    candidate=APICandidate(name='a',base_url='https://anth.example.com/v1',protocol_hint='anthropic-compatible',credential_profile_id='p')
    profile=CredentialProfile(id='p',display_name='p',auth_type=AuthScheme.API_KEY_HEADER,header_name='x-api-key',keychain_username='u')
    service=ValidationService(AppSettings(max_requests_per_api=6),lambda c:(profile,'SECRET'),transport=httpx.MockTransport(handler),resolve_dns=False)
    result=await service.validate_one(candidate,ValidationOptions(mode='authorized',model='claude-test'))
    posts=[r for r in requests if r.method=='POST']
    assert posts and posts[-1].url.path.endswith('/messages')
    assert posts[-1].headers.get('x-api-key')=='SECRET'
    assert result.authorized_test_succeeded is True
    assert result.overall_status.value=='WORKING'
    assert result.auth_required is True


@pytest.mark.asyncio
async def test_request_budget_counts_actual_http_requests():
    count=0
    def handler(req:httpx.Request):
        nonlocal count; count+=1
        return httpx.Response(404)
    service=ValidationService(AppSettings(max_requests_per_api=2),transport=httpx.MockTransport(handler),resolve_dns=False)
    result=await service.validate_one(APICandidate(name='x',base_url='https://example.com'),ValidationOptions(mode='standard'))
    assert count==2
    assert result.request_count==2

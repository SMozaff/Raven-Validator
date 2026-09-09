import httpx
import pytest

from raven_validator.adapters.base import AuthorizedContext
from raven_validator.adapters.openai_compatible import OpenAICompatibleAdapter
from raven_validator.core.http_client import BudgetedSafeClient
from raven_validator.domain.candidates import APICandidate
from raven_validator.security.network_policy import NetworkPolicy
from raven_validator.security.request_policy import ProbeSafetyLevel, RequestPolicy


@pytest.mark.asyncio
async def test_429_quota_does_not_invent_zero_balance():
    candidate=APICandidate(name='x',base_url='https://api.example.com/v1',quota_endpoint='https://api.example.com/quota')
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r:httpx.Response(429,text='rate quota exceeded'))) as raw:
        client=BudgetedSafeClient(raw,RequestPolicy(6,ProbeSafetyLevel.CUSTOM_AUTHORIZED),NetworkPolicy(resolve_dns=False))
        out=await OpenAICompatibleAdapter().quota(AuthorizedContext(candidate,client,'https://api.example.com/v1',{'Authorization':'Bearer X'}))
    assert out.data['known'] is False
    assert out.data['status']=='UNKNOWN'
    assert 'balance' not in out.data

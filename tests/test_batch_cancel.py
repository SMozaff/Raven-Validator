import httpx
import pytest

from raven_validator.config.settings import AppSettings
from raven_validator.domain.candidates import APICandidate
from raven_validator.services.validation_service import ValidationOptions, ValidationService


@pytest.mark.asyncio
async def test_cancel_has_single_terminal_event():
    service=ValidationService(AppSettings(),transport=httpx.MockTransport(lambda r:httpx.Response(200,json={})),resolve_dns=False)
    gen=service.validate_batch([APICandidate(name='x',base_url='https://example.com')],ValidationOptions(mode='quick'))
    first=await gen.__anext__()
    assert first.kind=='run_started'
    service.cancel()
    second=await gen.__anext__()
    assert second.kind=='run_cancelled'
    with pytest.raises(StopAsyncIteration):
        await gen.__anext__()

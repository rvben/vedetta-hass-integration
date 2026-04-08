from unittest.mock import AsyncMock, patch

import pytest
from aiohttp import ClientSession


@pytest.fixture
def api_client():
    from custom_components.vedetta.api import VedettaApiClient

    return VedettaApiClient(
        host="http://192.168.1.180:5050",
        token="test-token",
        session=AsyncMock(spec=ClientSession),
    )

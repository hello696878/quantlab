"""Public refusal responses must not cache or expose changing source material."""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.research_explainer import service


pytestmark = [pytest.mark.db_free, pytest.mark.usefixtures("isolated_lab_db")]


@pytest.mark.parametrize("error,status", [
    (service.Missing, 404), (service.Changed, 409),
    (service.Unavailable, 422), (ValueError, 422),
])
def test_source_refusals_are_private_and_not_cacheable(monkeypatch, error, status):
    def refuse(*args):
        raise error("SYNTHETIC_PRIVATE_SOURCE_FIELD")

    monkeypatch.setattr(service, "explain", refuse)
    response = TestClient(app).get("/research-explainer/saved-backtests/1")
    assert response.status_code == status
    assert response.headers["cache-control"] == "no-store"
    assert "SYNTHETIC_PRIVATE_SOURCE_FIELD" not in response.text
    assert len(response.content) < 200


@pytest.mark.parametrize("suffix", ["0", "1?expected=invalid", "1?template=untrusted"])
def test_request_refusal_is_not_cacheable_and_never_acquires(monkeypatch, suffix):
    def forbidden(*args):
        pytest.fail("invalid public request reached source acquisition")

    monkeypatch.setattr(service, "acquire", forbidden)
    response = TestClient(app).get("/research-explainer/saved-backtests/" + suffix)
    assert response.status_code == 422
    assert response.headers["cache-control"] == "no-store"

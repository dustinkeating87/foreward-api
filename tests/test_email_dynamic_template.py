from unittest.mock import patch, MagicMock
import pytest
from app.email import send_dynamic_template


def _mock_response(status_code=202):
    mock = MagicMock()
    mock.status_code = status_code
    mock.raise_for_status = MagicMock()
    if status_code >= 400:
        mock.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
    return mock


def test_payload_has_template_id_no_subject_no_content():
    with patch("app.email.httpx.post", return_value=_mock_response(202)) as mock_post, \
         patch.dict("os.environ", {"SENDGRID_API_KEY": "SG.test"}):
        send_dynamic_template(
            to="user@example.com",
            template_id="d-abc123",
            dynamic_data={"first_name": "there", "course_name": "Lakeview Golf Course"},
        )
    assert mock_post.called
    payload = mock_post.call_args.kwargs["json"]
    assert payload["template_id"] == "d-abc123"
    assert "subject" not in payload
    assert "content" not in payload


def test_payload_dynamic_template_data_structure():
    with patch("app.email.httpx.post", return_value=_mock_response(202)) as mock_post, \
         patch.dict("os.environ", {"SENDGRID_API_KEY": "SG.test"}):
        send_dynamic_template(
            to="user@example.com",
            template_id="d-abc123",
            dynamic_data={"first_name": "there", "course_name": "BraeBen Golf Course"},
        )
    payload = mock_post.call_args.kwargs["json"]
    personalization = payload["personalizations"][0]
    assert personalization["to"] == [{"email": "user@example.com"}]
    dtd = personalization["dynamic_template_data"]
    assert dtd["first_name"] == "there"
    assert dtd["course_name"] == "BraeBen Golf Course"


def test_from_name_defaults_to_good_lie():
    with patch("app.email.httpx.post", return_value=_mock_response(202)) as mock_post, \
         patch.dict("os.environ", {"SENDGRID_API_KEY": "SG.test"}):
        send_dynamic_template(
            to="user@example.com",
            template_id="d-abc123",
            dynamic_data={},
        )
    payload = mock_post.call_args.kwargs["json"]
    assert payload["from"]["name"] == "Good Lie"
    assert payload["from"]["email"] == "hello@goodlie.golf"


def test_returns_true_on_success():
    with patch("app.email.httpx.post", return_value=_mock_response(202)), \
         patch.dict("os.environ", {"SENDGRID_API_KEY": "SG.test"}):
        result = send_dynamic_template(
            to="user@example.com",
            template_id="d-abc123",
            dynamic_data={},
        )
    assert result is True


def test_returns_false_and_does_not_raise_on_http_error():
    with patch("app.email.httpx.post", return_value=_mock_response(500)), \
         patch.dict("os.environ", {"SENDGRID_API_KEY": "SG.test"}):
        result = send_dynamic_template(
            to="user@example.com",
            template_id="d-abc123",
            dynamic_data={},
        )
    assert result is False


def test_returns_false_when_api_key_missing():
    with patch.dict("os.environ", {}, clear=True):
        result = send_dynamic_template(
            to="user@example.com",
            template_id="d-abc123",
            dynamic_data={},
        )
    assert result is False


def test_returns_false_when_template_id_empty():
    with patch.dict("os.environ", {"SENDGRID_API_KEY": "SG.test"}):
        result = send_dynamic_template(
            to="user@example.com",
            template_id="",
            dynamic_data={},
        )
    assert result is False


def test_does_not_raise_on_network_error():
    with patch("app.email.httpx.post", side_effect=Exception("Connection refused")), \
         patch.dict("os.environ", {"SENDGRID_API_KEY": "SG.test"}):
        result = send_dynamic_template(
            to="user@example.com",
            template_id="d-abc123",
            dynamic_data={},
        )
    assert result is False

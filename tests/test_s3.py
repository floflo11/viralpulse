from unittest.mock import patch, MagicMock
from viralpulse.s3 import upload_screenshot, upload_screenshot_base64
import base64


@patch("viralpulse.s3.get_s3_client")
def test_upload_screenshot(mock_client):
    mock_client.return_value = MagicMock()
    url = upload_screenshot("user-123", "post-456", b"fake png bytes")
    assert "user-123/post-456.png" in url
    mock_client.return_value.put_object.assert_called_once()


@patch("viralpulse.s3.get_s3_client")
def test_upload_base64(mock_client):
    mock_client.return_value = MagicMock()
    b64 = base64.b64encode(b"fake png").decode()
    url = upload_screenshot_base64("user-123", "post-456", b64)
    assert "user-123/post-456.png" in url


@patch("viralpulse.s3.get_s3_client")
def test_upload_base64_with_data_uri(mock_client):
    mock_client.return_value = MagicMock()
    b64 = "data:image/png;base64," + base64.b64encode(b"fake png").decode()
    url = upload_screenshot_base64("user-123", "post-456", b64)
    assert "post-456.png" in url

"""S3 screenshot storage."""

import base64
import boto3
from viralpulse.config import settings


def get_s3_client():
    return boto3.client(
        "s3",
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
        region_name=settings.aws_region,
    )


def upload_screenshot(user_id: str, post_id: str, png_bytes: bytes) -> str:
    """Upload screenshot PNG to S3. Returns the public URL."""
    key = f"{user_id}/{post_id}.png"
    client = get_s3_client()
    client.put_object(
        Bucket=settings.s3_bucket,
        Key=key,
        Body=png_bytes,
        ContentType="image/png",
    )
    return f"https://{settings.s3_bucket}.s3.{settings.aws_region}.amazonaws.com/{key}"


def upload_screenshot_base64(user_id: str, post_id: str, b64_data: str) -> str:
    """Upload base64-encoded screenshot to S3."""
    if "," in b64_data:
        b64_data = b64_data.split(",", 1)[1]
    png_bytes = base64.b64decode(b64_data)
    return upload_screenshot(user_id, post_id, png_bytes)


def delete_screenshot(user_id: str, post_id: str):
    """Delete a screenshot from S3."""
    key = f"{user_id}/{post_id}.png"
    client = get_s3_client()
    client.delete_object(Bucket=settings.s3_bucket, Key=key)

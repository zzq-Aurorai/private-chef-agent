import uuid
from datetime import timedelta
from pathlib import Path

import alibabacloud_oss_v2 as oss

from app.config import (
    OSS_ACCESS_KEY_ID,
    OSS_ACCESS_KEY_SECRET,
    OSS_BUCKET,
    OSS_ENDPOINT,
    OSS_REGION,
)

_cfg = oss.config.load_default()
_cfg.credentials_provider = oss.credentials.StaticCredentialsProvider(
    access_key_id=OSS_ACCESS_KEY_ID,
    access_key_secret=OSS_ACCESS_KEY_SECRET,
)
_cfg.endpoint = OSS_ENDPOINT
_cfg.region = OSS_REGION

client = oss.Client(_cfg)


def upload_bytes(data: bytes, filename: str, content_type: str) -> str:
    """上传到 OSS，返回可直接访问的 URL（bucket 需为公共读）。"""
    suffix = Path(filename or "").suffix or ".jpg"
    key = f"private-chef/{uuid.uuid4().hex}{suffix}"

    client.put_object(
        oss.models.PutObjectRequest(
            bucket=OSS_BUCKET,
            key=key,
            body=data,
            content_type=content_type,
        )
    )
    return f"https://{OSS_BUCKET}.{OSS_ENDPOINT}/{key}"


def signed_url(key: str, expires: int = 3600) -> str:
    """私有读 bucket 用：生成一个临时可访问链接。"""
    result = client.presign(
        oss.models.GetObjectRequest(bucket=OSS_BUCKET, key=key),
        expires=timedelta(seconds=expires),
    )
    return result.url

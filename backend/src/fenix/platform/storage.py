"""Media storage: objects in Garage over the S3 API, served to guests by Caddy (AD-12).

Garage itself is configured through its admin API (`ensure_bucket`), so a fresh stand
needs no manual `garage` commands: layout, bucket, access key and website access are
created on deploy and left alone when they already exist.
"""

import asyncio
import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Protocol

import boto3
from botocore.config import Config

from fenix.platform.config import Settings

# Objects never change under a key (a new photo gets a new key), so caches keep them.
IMMUTABLE = "public, max-age=31536000, immutable"


class MediaStorage(Protocol):
    async def put(self, key: str, body: bytes, content_type: str) -> None: ...

    async def delete(self, key: str) -> None: ...


class S3Storage:
    def __init__(self, settings: Settings) -> None:
        self.bucket = settings.s3_bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            region_name="garage",
            aws_access_key_id=settings.s3_access_key_id,
            aws_secret_access_key=settings.s3_secret_access_key.get_secret_value(),
            config=Config(s3={"addressing_style": "path"}, retries={"max_attempts": 3}),
        )

    async def put(self, key: str, body: bytes, content_type: str) -> None:
        await asyncio.to_thread(
            self.client.put_object,
            Bucket=self.bucket,
            Key=key,
            Body=body,
            ContentType=content_type,
            CacheControl=IMMUTABLE,
        )

    async def delete(self, key: str) -> None:
        await asyncio.to_thread(self.client.delete_object, Bucket=self.bucket, Key=key)


@dataclass
class GarageAdmin:
    url: str
    token: str

    def call(self, method: str, path: str, body: Any = None) -> tuple[int, Any]:
        request = urllib.request.Request(  # noqa: S310 - internal admin endpoint from settings
            self.url.rstrip("/") + path,
            data=json.dumps(body).encode() if body is not None else None,
            method=method,
            headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310
                return response.status, json.loads(response.read() or b"null")
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read() or b"null")


def ensure_bucket(settings: Settings, capacity_bytes: int = 20 * 1024**3) -> list[str]:
    """Bring a single-node Garage to a usable state; returns what was changed."""
    admin = GarageAdmin(settings.garage_admin_url, settings.garage_admin_token.get_secret_value())
    done: list[str] = []

    status, cluster = admin.call("GET", "/v2/GetClusterStatus")
    if status != 200:
        raise RuntimeError(f"garage admin API: {status}")
    if cluster["layoutVersion"] == 0:
        node = cluster["nodes"][0]["id"]
        role = {"id": node, "zone": "dc1", "capacity": capacity_bytes, "tags": []}
        admin.call("POST", "/v2/UpdateClusterLayout", {"roles": [role]})
        admin.call("POST", "/v2/ApplyClusterLayout", {"version": 1})
        done.append("layout")

    bucket_name = settings.s3_bucket
    status, bucket = admin.call("GET", f"/v2/GetBucketInfo?globalAlias={bucket_name}")
    if status == 404:
        status, bucket = admin.call("POST", "/v2/CreateBucket", {"globalAlias": bucket_name})
        done.append("bucket")
    if status != 200:
        raise RuntimeError(f"garage bucket: {status}")

    key_id = settings.s3_access_key_id
    status, _ = admin.call("GET", f"/v2/GetKeyInfo?id={key_id}")
    if status != 200:
        status, _ = admin.call(
            "POST",
            "/v2/ImportKey",
            {
                "accessKeyId": key_id,
                "secretAccessKey": settings.s3_secret_access_key.get_secret_value(),
                "name": "fenix",
            },
        )
        if status != 200:
            raise RuntimeError(f"garage key import: {status}")
        done.append("key")

    granted = {k["accessKeyId"]: k["permissions"] for k in bucket.get("keys", [])}
    if not granted.get(key_id, {}).get("write"):
        admin.call(
            "POST",
            "/v2/AllowBucketKey",
            {
                "bucketId": bucket["id"],
                "accessKeyId": key_id,
                "permissions": {"read": True, "write": True, "owner": True},
            },
        )
        done.append("permissions")

    if not bucket.get("websiteAccess"):
        admin.call(
            "POST",
            f"/v2/UpdateBucket?id={bucket['id']}",
            {
                "websiteAccess": {
                    "enabled": True,
                    "indexDocument": "index.html",
                    "errorDocument": None,
                }
            },
        )
        done.append("website")
    return done

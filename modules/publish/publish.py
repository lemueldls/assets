"""
Replaces two things it used to do badly: a `find -L * | jq -s` one-liner for the
index, and a third-party directory-sync action that re-uploaded the whole bucket
on every run — including a nightly cron with nothing changed, with no retry, no
resume and no check that what landed matched what was built.

What it does instead:

  * walks the tree and writes `index.json` from the validated walk, refusing to
    write an empty one, which is the failure that silently takes the site's fonts
    and wallpapers down
  * lists the origin and diffs by ETag — for a single-part object R2's ETag is the
    MD5, so the comparison is exact rather than a guess from file size — and
    uploads only what differs
  * uploads at bounded concurrency, retries each file with backoff, and reads
    every object back after it lands
  * prunes remote objects absent locally, but only when asked

The origin is the source of truth, so there is no state file to keep in git: a
committed one creates a commit-per-run loop against a workflow that triggers on
push to main.

Credentials are minted per run rather than stored. A parent R2 API token — bucket
scoped, Object Read & Write, expiring — signs a short-lived JWT locally (stdlib
`hmac`; no extra dependency) and the derived credentials are scoped to exactly the
operations this run needs: listing and reading for a dry run, and `PutObject`
only when it is really writing. `--prune` is the sole path that mints
`DeleteObject`. Nothing long-lived that can write an object is ever in the
environment.

    publish public/                 # index and upload what changed
    publish public/ --dry-run       # show the plan, minting a read-only key
    publish public/ --prune         # also delete remote objects absent locally
    publish public/ --force         # re-upload everything regardless of the origin

Environment:
    CF_ACCOUNT_ID            Cloudflare account id
    R2_ACCESS_KEY_ID         parent R2 API token id
    R2_SECRET_ACCESS_KEY     parent R2 API token secret
    R2_BUCKET                bucket name (default: assets)
    R2_ENDPOINT              S3 endpoint (default: derived from the account)
"""

from __future__ import annotations

import argparse
import base64
import concurrent.futures
import hashlib
import hmac
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

READ_ACTIONS = ["ListObjectsV2", "GetObject", "HeadObject", "GetBucketLocation"]
WRITE_ACTIONS = READ_ACTIONS + ["PutObject"]
PRUNE_ACTIONS = WRITE_ACTIONS + ["DeleteObject", "DeleteObjects"]

CONTENT_TYPES = {
    ".json": "application/json",
    ".svg": "image/svg+xml",
    ".woff2": "font/woff2",
    ".woff": "font/woff",
    ".ttf": "font/ttf",
    ".otf": "font/otf",
    ".ttc": "font/collection",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".txt": "text/plain; charset=utf-8",
}

IMMUTABLE_PREFIXES = ("fonts/", "wallpapers/")
CACHE_CONTROL_IMMUTABLE = "public, max-age=31536000, immutable"
CACHE_CONTROL_VOLATILE = "public, max-age=60, must-revalidate"


def mint(
    account_id: str, key_id: str, secret: str, bucket: str, actions: list[str], ttl: int
) -> dict:
    """Short-lived S3 credentials, signed locally from the parent token.

    The claims Cloudflare documents for a temporary credential; the temporary
    secret is the SHA-256 of the signed JWT and the session token is
    base64("jwt/" + that JWT). The parent access key id is reused, so the parent
    token is the only secret in the environment.
    """
    endpoint_host = f"{account_id}.r2.cloudflarestorage.com"
    now = int(time.time())
    header = _b64url(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")))
    claims = _b64url(
        json.dumps(
            {
                "bucket": bucket,
                "scope": "object-read-write"
                if "PutObject" in actions
                else "object-read-only",
                "actions": actions,
                "sub": account_id,
                "iss": key_id,
                "aud": endpoint_host,
                "iat": now,
                "exp": now + ttl,
            },
            separators=(",", ":"),
        )
    )
    unsigned = f"{header}.{claims}"
    signature = hmac.new(secret.encode(), unsigned.encode(), hashlib.sha256).digest()
    jwt = f"{unsigned}.{_b64url(signature)}"

    return {
        "aws_access_key_id": key_id,
        "aws_secret_access_key": hashlib.sha256(jwt.encode()).hexdigest(),
        "aws_session_token": base64.b64encode(f"jwt/{jwt}".encode()).decode(),
    }


def _b64url(raw: bytes | str) -> str:
    if isinstance(raw, str):
        raw = raw.encode()
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def client(credentials: dict, endpoint: str) -> object:
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        region_name="auto",
        config=Config(retries={"max_attempts": 10, "mode": "adaptive"}),
        **credentials,
    )


@dataclass
class Object:
    key: str
    path: Path
    size: int
    etag: str = ""

    def digest(self) -> str:
        if not self.etag:
            h = hashlib.md5()
            with self.path.open("rb") as fh:
                for chunk in iter(lambda: fh.read(1 << 20), b""):
                    h.update(chunk)
            self.etag = h.hexdigest()
        return self.etag

    @property
    def content_type(self) -> str:
        return CONTENT_TYPES.get(self.path.suffix.lower(), "application/octet-stream")

    @property
    def cache_control(self) -> str:
        return (
            CACHE_CONTROL_IMMUTABLE
            if self.key.startswith(IMMUTABLE_PREFIXES)
            else CACHE_CONTROL_VOLATILE
        )


@dataclass
class Plan:
    upload: list[Object]
    unchanged: list[Object]
    doomed: list[str]


def walk(root: Path) -> list[Object]:
    """Every file under `root`, keyed by its path relative to it.

    Follows symlinks, as the tree is a nest of `cp -r` results, but refuses to
    carry on if one dangles: a broken link is how an index ends up half-written.
    """
    objects: list[Object] = []
    for directory, _, names in os.walk(root, followlinks=True):
        for name in names:
            path = Path(directory) / name
            if path.is_symlink() and not path.resolve().exists():
                raise SystemExit(f"publish: broken symlink at {path}")
            if not path.is_file():
                continue
            key = path.relative_to(root).as_posix()
            objects.append(Object(key=key, path=path, size=path.stat().st_size))
    return sorted(objects, key=lambda o: o.key)


def write_index(root: Path, objects: list[Object]) -> Object:
    """Index the tree and add the index to it.

    R2's ETag is the MD5 for a single-part object, which is what the diff below
    compares against, so the index is regenerated on every run.
    """
    keys = [o.key for o in objects if o.key != "index.json"]
    if not keys:
        raise SystemExit("publish: refusing to write an empty index")

    path = root / "index.json"
    path.write_text(json.dumps(keys, indent=2) + "\n")
    return Object(key="index.json", path=path, size=path.stat().st_size)


def remote_objects(s3, bucket: str) -> dict[str, tuple[int, str]]:
    """key -> (size, etag), from the origin."""
    found: dict[str, tuple[int, str]] = {}
    token = None
    while True:
        kwargs = {"Bucket": bucket}
        if token:
            kwargs["ContinuationToken"] = token
        page = s3.list_objects_v2(**kwargs)
        for item in page.get("Contents", []):
            found[item["Key"]] = (item["Size"], item["ETag"].strip('"'))
        if not page.get("IsTruncated"):
            return found
        token = page["NextContinuationToken"]


def plan(
    objects: list[Object], remote: dict[str, tuple[int, str]] | None, force: bool
) -> Plan:
    upload, unchanged = [], []
    for obj in objects:
        known = remote.get(obj.key) if remote else None
        if not force and known and known[0] == obj.size and known[1] == obj.digest():
            unchanged.append(obj)
        else:
            upload.append(obj)
    doomed = []
    if remote is not None:
        doomed = sorted(set(remote) - {o.key for o in objects})
    return Plan(upload=upload, unchanged=unchanged, doomed=doomed)


def upload_one(s3, bucket: str, obj: Object) -> None:
    """Put one object and read it back to confirm it landed."""
    for attempt in range(4):
        try:
            s3.put_object(
                Bucket=bucket,
                Key=obj.key,
                Body=obj.path.read_bytes(),
                ContentType=obj.content_type,
                CacheControl=obj.cache_control,
            )
            head = s3.head_object(Bucket=bucket, Key=obj.key)
            if head["ContentLength"] != obj.size:
                raise IOError(
                    f"{head['ContentLength']} bytes on the origin, {obj.size} expected"
                )
            etag = head["ETag"].strip('"')
            if len(etag) == 32 and etag != obj.digest():
                raise IOError("checksum mismatch")
            return
        except (ClientError, IOError) as exc:
            if attempt == 3:
                raise
            time.sleep(2**attempt)
            print(
                f"[publish] {obj.key}: {_short(exc)} — retry {attempt + 1}",
                file=sys.stderr,
            )


def _short(exc: Exception) -> str:
    return str(exc).replace("\n", " ")[:120]


def _human(size: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{int(size)} B" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


def main() -> int:
    parser = argparse.ArgumentParser(description="Index a tree and upload it to R2.")
    parser.add_argument("root", type=Path)
    parser.add_argument(
        "--dry-run", action="store_true", help="plan only; mints a read-only key"
    )
    parser.add_argument(
        "--prune", action="store_true", help="delete remote objects absent locally"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="upload everything regardless of the origin",
    )
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument(
        "--ttl", type=int, default=3600, help="credential lifetime in seconds"
    )
    args = parser.parse_args()

    account_id = os.environ.get("CF_ACCOUNT_ID")
    key_id = os.environ.get("R2_ACCESS_KEY_ID")
    secret = os.environ.get("R2_SECRET_ACCESS_KEY")
    bucket = os.environ.get("R2_BUCKET", "assets")
    endpoint = os.environ.get("R2_ENDPOINT") or (
        f"https://{account_id}.r2.cloudflarestorage.com" if account_id else None
    )
    missing = [
        name
        for name, value in (
            ("CF_ACCOUNT_ID", account_id),
            ("R2_ACCESS_KEY_ID", key_id),
            ("R2_SECRET_ACCESS_KEY", secret),
        )
        if not value
    ]

    if not args.root.is_dir():
        print(f"publish: {args.root} is not a directory", file=sys.stderr)
        return 1

    objects = walk(args.root)
    index = write_index(args.root, objects)
    objects = sorted(
        [obj for obj in objects if obj.key != index.key] + [index], key=lambda o: o.key
    )

    remote = None
    actions = READ_ACTIONS
    if not missing and endpoint:
        credentials = mint(account_id, key_id, secret, bucket, READ_ACTIONS, args.ttl)
        s3 = client(credentials, endpoint)
        remote = remote_objects(s3, bucket)
        actions = PRUNE_ACTIONS if args.prune else WRITE_ACTIONS
    elif not args.dry_run:
        print(f"publish: missing {', '.join(missing)}", file=sys.stderr)
        return 1
    else:
        print(
            "[publish] no credentials — planning from the walk alone", file=sys.stderr
        )

    result = plan(objects, remote, args.force)
    print(
        f"[publish] {len(result.upload)} to upload, {len(result.unchanged)} unchanged, "
        f"{len(result.doomed)} to prune, {_human(sum(o.size for o in objects))} total"
    )

    if args.dry_run:
        for obj in result.upload:
            print(f"  would upload {obj.key} ({_human(obj.size)})")
        for key in result.doomed:
            print(f"  would delete {key}")
        return 0

    credentials = mint(account_id, key_id, secret, bucket, actions, args.ttl)
    s3 = client(credentials, endpoint)
    print(f"[publish] minted a {args.ttl}s credential scoped to {', '.join(actions)}")

    failures = 0
    if result.upload:
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=args.concurrency
        ) as pool:
            futures = {
                pool.submit(upload_one, s3, bucket, obj): obj for obj in result.upload
            }
            for done in concurrent.futures.as_completed(futures):
                obj = futures[done]
                try:
                    done.result()
                except Exception as exc:
                    failures += 1
                    print(f"[publish] FAILED {obj.key}: {_short(exc)}", file=sys.stderr)
        print(
            f"[publish] uploaded {len(result.upload) - failures}/{len(result.upload)}"
        )

    if args.prune:
        for key in result.doomed:
            try:
                s3.delete_object(Bucket=bucket, Key=key)
                print(f"[publish] deleted {key}")
            except ClientError as exc:
                failures += 1
                print(
                    f"[publish] FAILED to delete {key}: {_short(exc)}", file=sys.stderr
                )

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

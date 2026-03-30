# Design

## Overview

`aws-sigv4` is a minimal Python library for signing HTTP requests with AWS
Signature Version 4 and resolving AWS credentials — including IRSA (IAM Roles
for Service Accounts) on EKS — without pulling in `boto3` or `botocore`.

The goal is to let callers use AWS HTTP APIs directly (via `aiohttp`, `httpx`,
`requests`, or anything else) while this library handles the authentication
plumbing.

---

## Code Structure

```
src/aws_sigv4/
├── __init__.py        # Public API re-exports
├── py.typed           # PEP 561 marker (typed package)
├── signing.py         # SigV4 algorithm — pure functions, zero I/O
├── credentials.py     # Credentials dataclass + RefreshableCredentials
├── resolve.py         # resolve_credentials() — the provider chain
├── signer.py          # Signer — high-level sign() wrapper
└── providers/
    ├── env.py          # AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY
    ├── web_identity.py # IRSA: token file → STS AssumeRoleWithWebIdentity
    ├── config_file.py  # ~/.aws/credentials and ~/.aws/config
    ├── container.py    # ECS task role endpoint
    └── imds.py         # EC2 Instance Metadata Service (IMDSv2)
```

---

## Two-Layer API

### Low-level: `sign_headers()`

Pure function in `signing.py`. Takes a `Credentials` dataclass directly.
Does zero I/O. Runs in microseconds. Suitable for callers that manage their
own credentials and need predictable, non-blocking latency.

```python
from aws_sigv4 import Credentials, sign_headers

headers = sign_headers(
    method="GET",
    url="https://s3.us-east-1.amazonaws.com/my-bucket",
    headers={"host": "s3.us-east-1.amazonaws.com"},
    body=b"",
    region="us-east-1",
    service="s3",
    credentials=Credentials(access_key="...", secret_key="..."),
)
```

### High-level: `Signer`

Wraps credential resolution, auto-refresh, and signing into a single object.
Most callers should use this.

```python
from aws_sigv4 import Signer

signer = Signer(region="us-east-1", service="s3")
signer.credentials.refresh()  # optional pre-warm
headers = signer.sign(method="GET", url="https://s3.us-east-1.amazonaws.com/my-bucket")
```

---

## SigV4 Signing Algorithm (`signing.py`)

Implements the AWS Signature Version 4 specification exactly, reverse-engineered
from `botocore/auth.py`. All logic is pure Python stdlib (`hashlib`, `hmac`,
`urllib.parse`).

Steps:

1. **Timestamp** — `YYYYMMDDTHHMMSSZ` format for `X-Amz-Date`
2. **Canonical Request** — 6 components joined by newline:
   - HTTP method (uppercased)
   - Canonical URI (path, URI-encoded with `safe='/~'`)
   - Canonical query string (keys and values sorted and URI-encoded)
   - Canonical headers (lowercased, sorted, whitespace-collapsed)
   - Blank line
   - Signed headers (semicolon-joined sorted lowercase names)
   - Payload hash (SHA-256 hex of body, or `EMPTY_SHA256` for empty body)
3. **String to Sign** — algorithm + date + credential scope + SHA-256 of canonical request
4. **Signing key** — four-step HMAC-SHA256: `AWS4+secret` → date → region → service → `aws4_request`
5. **Signature** — HMAC-SHA256 of string-to-sign with signing key, hex-encoded
6. **Authorization header** — `AWS4-HMAC-SHA256 Credential=…, SignedHeaders=…, Signature=…`

**Header blacklist** (never signed, matching botocore): `authorization`,
`connection`, `expect`, `keep-alive`, `proxy-authenticate`,
`proxy-authorization`, `te`, `trailer`, `transfer-encoding`, `upgrade`,
`user-agent`, `x-amzn-trace-id`.

---

## Credential Model (`credentials.py`)

### `Credentials`

Frozen dataclass. Immutable — a new instance is created on each refresh.

```python
@dataclass(frozen=True)
class Credentials:
    access_key: str
    secret_key: str
    token: str | None = None      # STS session token (IRSA, ECS, IMDS)
    expires_at: datetime | None = None  # UTC; None for long-lived IAM creds
```

### `CredentialProvider` (Protocol)

```python
class CredentialProvider(Protocol):
    def load(self) -> Credentials | None: ...
```

Return `None` if this provider cannot supply credentials in the current
environment (env vars not set, not on EC2, etc.).

### `RefreshableCredentials`

Wraps a `CredentialProvider` with thread-safe lazy fetching and auto-refresh.

**Refresh thresholds** (matching botocore):
- **Advisory** (15 min before expiry): one thread refreshes; others get cached
- **Mandatory** (10 min before expiry): all threads block until refreshed

**Observable properties**:
- `is_ready` — fetched at least once and not expired
- `needs_refresh` — in advisory or mandatory window
- `expires_at` — expiry of current credentials

**Pre-warming**:
```python
creds = resolve_credentials()
creds.refresh()   # fetch now, on your schedule
```

---

## Credential Provider Chain (`resolve.py`)

`resolve_credentials()` iterates providers in priority order:

| # | Provider | Trigger |
|---|----------|---------|
| 1 | `EnvProvider` | `AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY` |
| 2 | `WebIdentityProvider` | `AWS_WEB_IDENTITY_TOKEN_FILE` + `AWS_ROLE_ARN` (IRSA) |
| 3 | `ConfigFileProvider` | `~/.aws/credentials` / `~/.aws/config` |
| 4 | `ContainerProvider` | `AWS_CONTAINER_CREDENTIALS_RELATIVE_URI` (ECS) |
| 5 | `IMDSProvider` | EC2 instance metadata at `169.254.169.254` |

The `_ChainProvider` wrapper calls each provider's `load()` in order, skipping
providers that return `None` or raise exceptions. Errors are logged at DEBUG
level and do not halt the chain.

---

## IRSA Flow (`providers/web_identity.py`)

1. Read `AWS_WEB_IDENTITY_TOKEN_FILE` path and `AWS_ROLE_ARN`
2. Open the token file and read the JWT (re-read on every refresh — Kubernetes
   rotates the projected service account token periodically)
3. POST to STS `AssumeRoleWithWebIdentity` with the JWT (no AWS auth needed —
   the JWT is the proof of identity)
4. Parse the XML response with `xml.etree.ElementTree` (stdlib)
5. Return a `Credentials` with the temporary `AccessKeyId`, `SecretAccessKey`,
   `SessionToken`, and `Expiration`

STS is called without signing (`urllib.request` with no auth headers) because
`AssumeRoleWithWebIdentity` accepts the web identity token as authentication.

---

## Dependencies

**Runtime:** none — pure Python stdlib only (`hashlib`, `hmac`, `urllib`,
`xml.etree`, `configparser`, `threading`, `datetime`)

**Dev:** `pytest`, `mypy`, `ruff`

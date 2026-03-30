# SPDX-FileCopyrightText: 2025-present Doug Richardson <git@rekt.email>
# SPDX-License-Identifier: MIT

"""
Credential provider: environment variables.

Reads ``AWS_ACCESS_KEY_ID``, ``AWS_SECRET_ACCESS_KEY``, and optionally
``AWS_SESSION_TOKEN`` from the process environment.
"""

import os

from aws_sigv4.credentials import Credentials


class EnvProvider:
    """Load credentials from environment variables."""

    def load(self) -> Credentials | None:
        access_key = os.environ.get("AWS_ACCESS_KEY_ID")
        secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY")

        if not access_key or not secret_key:
            return None

        token = os.environ.get("AWS_SESSION_TOKEN") or os.environ.get(
            "AWS_SECURITY_TOKEN"
        )

        return Credentials(
            access_key=access_key,
            secret_key=secret_key,
            token=token or None,
        )

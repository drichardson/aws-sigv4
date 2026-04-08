# SPDX-FileCopyrightText: 2025-present Doug Richardson <git@rekt.email>
# SPDX-License-Identifier: MIT

"""Session-wide pytest configuration.

Configures pytest-httpserver to bind to 127.0.0.1 so that test URLs use
``http://127.0.0.1:<port>/...``, which is in the container provider's
allowed-URI list (alongside ``http://169.254.170.2`` and ``https://``).
"""

import pytest


@pytest.fixture(scope="session")
def httpserver_listen_address():
    return ("127.0.0.1", 0)

#!/usr/bin/python
# -*- coding: utf-8 -*-

DOCUMENTATION = r"""
---
name: artifactory_api_client
short_description: HttpApi Plugin for JFrog Artifactory
description:
  - This HttpApi plugin provides methods to connect to and interact with
    JFrog Artifactory REST API.
author:
  - Ansible Artifactory Collection Authors
options:
  token:
    type: str
    description:
      - The API token for Artifactory authentication.
      - Alternatively set via C(ansible_httpapi_token) in inventory.
    vars:
      - name: ansible_httpapi_token
"""

import json

from ansible.module_utils.connection import ConnectionError
from ansible.plugins.httpapi import HttpApiBase


class HttpApi(HttpApiBase):
    """HttpApi plugin for JFrog Artifactory."""
    def print_debug(self, message):
        """Print a debug message."""
        print(f"DEBUG: {message}")

    def send_request(self, data, **message_kwargs):
        """Send a request to Artifactory and return (response_body, response_code).

        Modules call this via Connection(module._socket_path).send_request().
        """
        path = message_kwargs.get("path", "/api/system/version")
        method = message_kwargs.get("method", "GET")
        headers = message_kwargs.get("headers") or {}

        self._set_auth_headers(headers)

        response, response_data = self.connection.send(
            path,
            data,
            method=method,
            headers=headers,
        )

        response_code = response.getcode()
        try:
            body = response_data.getvalue()
        except AttributeError:
            body = response_data.read() if hasattr(response_data, "read") else response_data

        if isinstance(body, bytes):
            try:
                body = json.loads(body)
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass

        return body, response_code

    def _set_auth_headers(self, headers):
        """Add authentication headers to the request."""
        token = self.get_option("token") if self.has_option("token") else None
        # raise Exception(f"------------------------{token}---------------------------")
        if token:
            headers.setdefault("Authorization", f"Bearer {token}")
        elif self.connection._auth:
            headers.setdefault("Authorization", f"Basic {self.connection._auth}")

    def login(self, username, password):
        """Authenticate against Artifactory.

        With token auth (ansible_httpapi_token), no login exchange is needed.
        With basic auth (ansible_user/ansible_password), the credentials are
        sent on every request via _set_auth_headers.
        """
        if username and password:
            import base64
            self.connection._auth = base64.b64encode(
                f"{username}:{password}".encode()
            ).decode()

    def logout(self):
        """No logout action needed for Artifactory REST API."""
        pass

    def handle_httperror(self, exc):
        """Handle HTTP errors from Artifactory.

        Return True to let the caller handle the error (re-raises),
        or return a response to suppress it.
        """
        return exc

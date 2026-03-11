#!/usr/bin/python
# -*- coding: utf-8 -*-

DOCUMENTATION = r"""
---
module: artifactory_download
short_description: Download an artifact from JFrog Artifactory
description:
  - Downloads an artifact from a JFrog Artifactory repository to the Ansible controller.
  - Uses the httpapi connection plugin for authentication and API access.
  - Connection details (URL, credentials, SSL) are configured in inventory.
  - Supports idempotency via SHA-256 checksum comparison.
options:
  repo:
    description: The name of the Artifactory repository.
    required: true
    type: str
  path:
    description: The path to the artifact within the repository.
    required: true
    type: str
  name:
    description: The filename of the artifact to download.
    required: true
    type: str
  dest:
    description:
      - The destination directory on the controller where the artifact will be saved.
      - The file will be saved as C(dest/name).
    required: false
    type: path
    default: .
  force:
    description:
      - If C(true), always download the artifact even if a local file with a matching checksum exists.
    required: false
    type: bool
    default: false
author:
  - Ansible Artifactory Collection Authors
"""

EXAMPLES = r"""
# inventory.networking
# [artifactory]
# https://repo.cci.nokia.net/artifactory
#
# [artifactory:vars]
# ansible_connection=httpapi
# ansible_network_os=ansible.artifactory.artifactory_api_client
# ansible_httpapi_use_ssl=true
# ansible_httpapi_validate_certs=false
# ansible_user=jfrog
# ansible_httpapi_token=<token>

- name: Download an RPM from Artifactory
  ansible.artifactory.artifactory_download:
    repo: cbis-generic-releases
    path: cbis_vlab_repo/24.7.0/ncs/506
    name: patchiso-24.7.0-506.os8.noarch.rpm
    dest: /tmp/artifacts

- name: Force re-download even if file exists
  ansible.artifactory.artifactory_download:
    repo: cbis-generic-releases
    path: cbis_vlab_repo/24.7.0/ncs/506
    name: patchiso-24.7.0-506.os8.noarch.rpm
    dest: /tmp/artifacts
    force: true
"""

RETURN = r"""
dest:
  description: The full path to the downloaded file.
  returned: success
  type: str
  sample: /tmp/artifacts/patchiso-24.7.0-506.os8.noarch.rpm
checksum:
  description: The SHA-256 checksum of the downloaded file.
  returned: success
  type: str
size:
  description: The size of the downloaded file in bytes.
  returned: success
  type: int
"""

import hashlib
import json
import os
import tempfile

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.connection import Connection


CHUNK_SIZE = 8192


def sha256_file(filepath):
    """Calculate the SHA-256 checksum of a local file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(CHUNK_SIZE), b""):
            h.update(chunk)
    return h.hexdigest()


def get_artifact_info(connection, repo, path, name):
    """Retrieve artifact metadata including SHA-256 checksum via AQL."""
    aql_query = (
        f'items.find({{"repo":{{"$eq":"{repo}"}},'
        f' "path":{{"$eq":"{path}"}},'
        f' "name":{{"$eq":"{name}"}}}})'
        f'.include("repo", "path", "name", "size", "actual_md5", "actual_sha1", "sha256")'
    )
    response, response_code = connection.send_request(
        data=aql_query,
        path="/api/search/aql",
        method="POST",
        headers={"Content-Type": "text/plain"},
    )
    if response_code not in (200,):
        raise Exception(f"AQL query failed with status {response_code}: {response}")

    if isinstance(response, str):
        response = json.loads(response)

    results = response.get("results", [])
    if not results:
        return None
    return results[0]


def download_artifact(connection, repo, path, name, dest_dir):
    """Download the artifact via the httpapi connection and save to dest_dir."""
    download_path = f"/{repo}/{path}/{name}"
    dest_file = os.path.join(dest_dir, name)

    response, response_code = connection.send_request(
        data=None,
        path=download_path,
        method="GET",
        headers={"Accept": "*/*"},
    )
    if response_code not in (200,):
        raise Exception(f"Download failed with status {response_code}")

    content = response if isinstance(response, bytes) else response.encode("utf-8")

    fd, tmp_path = tempfile.mkstemp(dir=dest_dir)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(content)
        os.rename(tmp_path, dest_file)
    except Exception:
        os.unlink(tmp_path)
        raise

    return dest_file


def run_module():
    module = AnsibleModule(
        argument_spec=dict(
            repo=dict(type="str", required=True),
            path=dict(type="str", required=True),
            name=dict(type="str", required=True),
            dest=dict(type="path", default="."),
            force=dict(type="bool", default=False),
        ),
        supports_check_mode=True,
    )

    repo = module.params["repo"]
    path = module.params["path"]
    name = module.params["name"]
    dest = module.params["dest"]
    force = module.params["force"]

    dest_file = os.path.join(dest, name)
    result = dict(changed=False, dest=dest_file)

    connection = Connection(module._socket_path)
    connection.print_debug(f"----------------------------------------------------------")

    try:
        artifact_info = get_artifact_info(connection, repo, path, name)
    except Exception as e:
        module.fail_json(msg=f"Failed to query artifact metadata: {e}", **result)

    if artifact_info is None:
        module.fail_json(msg=f"Artifact not found: {repo}/{path}/{name}", **result)

    remote_sha256 = artifact_info.get("sha256", "")
    result["remote_size"] = artifact_info.get("size", 0)

    if not force and os.path.isfile(dest_file):
        local_sha256 = sha256_file(dest_file)
        if local_sha256 == remote_sha256:
            result["checksum"] = local_sha256
            result["size"] = os.path.getsize(dest_file)
            module.exit_json(msg="File already exists with matching checksum, skipping download.", **result)

    if module.check_mode:
        result["changed"] = True
        module.exit_json(msg="Would download the artifact (check mode).", **result)

    if not os.path.isdir(dest):
        try:
            os.makedirs(dest)
        except OSError as e:
            module.fail_json(msg=f"Failed to create destination directory '{dest}': {e}", **result)

    try:
        download_artifact(connection, repo, path, name, dest)
    except Exception as e:
        module.fail_json(msg=f"Failed to download artifact: {e}", **result)

    local_sha256 = sha256_file(dest_file)
    if remote_sha256 and local_sha256 != remote_sha256:
        os.unlink(dest_file)
        module.fail_json(
            msg=f"Checksum mismatch after download. Expected {remote_sha256}, got {local_sha256}.",
            **result,
        )

    result["changed"] = True
    result["checksum"] = local_sha256
    result["size"] = os.path.getsize(dest_file)
    module.exit_json(msg="Artifact downloaded successfully.", **result)


def main():
    run_module()


if __name__ == "__main__":
    main()

# shahargolshani.artifactory

[![CI](https://github.com/ishavkon/ansible.artifactory/actions/workflows/ansible-test.yml/badge.svg)](https://github.com/ishavkon/ansible.artifactory/actions/workflows/ansible-test.yml)

An Ansible collection for interacting with [JFrog Artifactory](https://jfrog.com/artifactory/). It uses a dedicated `httpapi` connection plugin to talk to the Artifactory REST API, so modules never make direct HTTP calls themselves — authentication, SSL, and request handling are all configured once in your inventory.

Currently the collection provides a single module for downloading artifacts, with idempotent, checksum-verified downloads.

## Requirements

- ansible-core >= 2.16.0
- Python 3.8+
- Network access from the Ansible controller to your Artifactory instance's REST API
- A valid Artifactory API/access token, or a username and password for Basic auth

## Installation

Install the collection from Ansible Galaxy:

```bash
ansible-galaxy collection install shahargolshani.artifactory
```

Or add it to a `requirements.yml` file:

```yaml
---
collections:
  - name: shahargolshani.artifactory
```

and install with:

```bash
ansible-galaxy collection install -r requirements.yml
```

## Authentication and connection setup

This collection uses the `httpapi` connection plugin, so Artifactory connection details are configured in your inventory rather than passed to each task. Two authentication methods are supported:

- **Bearer token** — set `ansible_httpapi_token`
- **Basic auth** — set `ansible_user` and `ansible_password`

Example inventory:

```ini
[artifactory]
https://repo.example.com

[artifactory:vars]
ansible_connection=httpapi
ansible_network_os=shahargolshani.artifactory.artifactory_api_client
ansible_httpapi_use_ssl=true
ansible_httpapi_validate_certs=false
ansible_httpapi_token=<your-token>
```

Store tokens and passwords in [Ansible Vault](https://docs.ansible.com/ansible/latest/vault_guide/index.html) rather than plain text inventory.

## Included content

### HttpApi plugins

| Name | Description |
| --- | --- |
| [artifactory_api_client](plugins/httpapi/artifactory_api_client.py) | Handles authentication and request/response plumbing for the Artifactory REST API. |

### Modules

| Name | Description |
| --- | --- |
| [artifactory_download](plugins/modules/artifactory_download.py) | Downloads an artifact from an Artifactory repository to the Ansible controller, with checksum-based idempotency. |

## Usage example

```yaml
- name: Download an artifact from Artifactory
  shahargolshani.artifactory.artifactory_download:
    repo: my-generic-repo
    path: my-project/1.0.0
    name: artifact-1.0.0.rpm
    dest: /tmp/artifacts

- name: Force re-download even if a matching file already exists
  shahargolshani.artifactory.artifactory_download:
    repo: my-generic-repo
    path: my-project/1.0.0
    name: artifact-1.0.0.rpm
    dest: /tmp/artifacts
    force: true

- name: Download an artifact and save its Artifactory metadata alongside it
  shahargolshani.artifactory.artifactory_download:
    repo: my-generic-repo
    path: my-project/1.0.0
    name: artifact-1.0.0.rpm
    dest: /tmp/artifacts
    metadata: true
```

`artifactory_download` compares the local file's SHA-256 checksum against the one reported by Artifactory and skips the download if they already match (unless `force: true`), and supports `check_mode`.

## Testing

Sanity and unit tests run in CI (`.github/workflows/ansible-test.yml`) against ansible-core `stable-2.18`, `stable-2.19`, `stable-2.20`, and `devel`:

```bash
ansible-test sanity --docker default
ansible-test unit --docker default
```

Integration tests live under `tests/integration/targets/artifactory_download/` and require a reachable Artifactory instance; they are not currently run in CI. They cover first download, idempotency, forced re-download, check mode, a missing-artifact error, and an invalid-token error. To run them, configure `tests/integration/inventory.networking` and the test variables in `tests/integration/targets/artifactory_download/vars/main.yml` with your own Artifactory details, then run:

```bash
ansible-test integration --docker default
```

## Contributing

Issues and pull requests are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## Release notes

See the [changelog](CHANGELOG.rst).

## License

GNU General Public License v3.0 or later.

See [LICENSE](LICENSE) for the full text.

## Authors

- Shahar Golshani
- Ilya Shavkonov

# -*- coding: utf-8 -*-
# Copyright: (c) 2025, Ansible Artifactory Collection Authors
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import json
import os
import tempfile
import pytest

from ansible_collections.shahargolshani.artifactory.plugins.modules import artifactory_download
from ansible.module_utils import basic
from ansible.module_utils.common.text.converters import to_bytes


# Mock exceptions for module exit functions
class AnsibleExitJson(Exception):
    """Exception class to replace exit_json()."""
    pass


class AnsibleFailJson(Exception):
    """Exception class to replace fail_json()."""
    pass


def set_module_args(args):
    """Set module arguments for testing."""
    args_json = json.dumps({"ANSIBLE_MODULE_ARGS": args})
    basic._ANSIBLE_ARGS = to_bytes(args_json)


def exit_json(*args, **kwargs):
    """Mock exit_json function."""
    if "changed" not in kwargs:
        kwargs["changed"] = False
    raise AnsibleExitJson(kwargs)


def fail_json(*args, **kwargs):
    """Mock fail_json function."""
    kwargs["failed"] = True
    raise AnsibleFailJson(kwargs)


@pytest.fixture
def mock_module(mocker):
    """Fixture to create a mock AnsibleModule."""
    mocker.patch.multiple(
        basic.AnsibleModule,
        exit_json=exit_json,
        fail_json=fail_json,
    )


@pytest.fixture
def mock_connection(mocker):
    """Fixture to create a mock Connection object."""
    mock_conn = mocker.Mock()
    mock_conn.send_request = mocker.Mock()
    mock_conn.print_debug = mocker.Mock()
    mocker.patch(
        "ansible_collections.shahargolshani.artifactory.plugins.modules.artifactory_download.Connection",
        return_value=mock_conn,
    )
    return mock_conn


@pytest.fixture
def temp_dir():
    """Fixture to create and cleanup a temporary directory."""
    tmpdir = tempfile.mkdtemp()
    yield tmpdir
    # Cleanup
    # Cleanup
    import shutil
    if os.path.exists(tmpdir):
        shutil.rmtree(tmpdir)


class TestSha256File:
    """Test cases for sha256_file function."""

    def test_sha256_file_calculates_checksum_correctly(self, temp_dir):
        """Test that sha256_file calculates correct SHA-256 checksum."""
        test_file = os.path.join(temp_dir, "test.txt")
        test_content = b"Hello, World!"
        # SHA-256 checksum of b"Hello, World!" calculated via: echo -n "Hello, World!" | sha256sum
        expected_sha256 = "dffd6021bb2bd5b0af676290809ec3a53191dd81c7f70a4b28688a362182986f"

        with open(test_file, "wb") as f:
            f.write(test_content)

        result = artifactory_download.sha256_file(test_file)
        assert result == expected_sha256

    def test_sha256_file_handles_binary_content(self, temp_dir):
        """Test that sha256_file handles binary content correctly."""
        test_file = os.path.join(temp_dir, "binary.bin")
        # Create binary content with all byte values 0x00-0xFF (256 bytes total)
        test_content = bytes(range(256))

        with open(test_file, "wb") as f:
            f.write(test_content)

        result = artifactory_download.sha256_file(test_file)
        # SHA-256 produces 64 hexadecimal characters (256 bits / 4 bits per hex digit)
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)


class TestGetArtifactInfo:
    """Test cases for get_artifact_info function."""

    def test_get_artifact_info_returns_metadata_on_success(self, mocker):
        """Test that get_artifact_info returns artifact metadata successfully."""
        mock_conn = mocker.Mock()
        response_data = {
            "results": [
                {
                    "repo": "test-repo",
                    "path": "test/path",
                    "name": "test.rpm",
                    "size": 1024,  # Arbitrary size for mock metadata
                    "sha256": "abc123",  # Mock checksum (not a real SHA-256 value)
                    "actual_md5": "def456",  # Mock MD5 checksum
                    "actual_sha1": "ghi789",  # Mock SHA-1 checksum
                }
            ]
        }
        mock_conn.send_request.return_value = (response_data, 200)

        result = artifactory_download.get_artifact_info(
            mock_conn, "test-repo", "test/path", "test.rpm"
        )

        assert result is not None
        assert result["repo"] == "test-repo"
        assert result["name"] == "test.rpm"
        assert result["size"] == 1024
        assert result["sha256"] == "abc123"
        assert mock_conn.send_request.call_count == 1

    def test_get_artifact_info_handles_string_response(self, mocker):
        """Test that get_artifact_info handles JSON string responses."""
        mock_conn = mocker.Mock()
        response_data = json.dumps({
            "results": [
                {
                    "repo": "test-repo",
                    "name": "test.rpm",
                    "sha256": "abc123",  # Mock checksum
                }
            ]
        })
        mock_conn.send_request.return_value = (response_data, 200)

        result = artifactory_download.get_artifact_info(
            mock_conn, "test-repo", "test/path", "test.rpm"
        )

        assert result is not None
        assert result["repo"] == "test-repo"  # type: ignore

    def test_get_artifact_info_returns_none_when_no_results(self, mocker):
        """Test that get_artifact_info returns None when artifact is not found."""
        mock_conn = mocker.Mock()
        response_data = {"results": []}
        mock_conn.send_request.return_value = (response_data, 200)

        result = artifactory_download.get_artifact_info(
            mock_conn, "test-repo", "test/path", "missing.rpm"
        )

        assert result is None  # type: ignore

    def test_get_artifact_info_raises_exception_on_api_error(self, mocker):
        """Test that get_artifact_info raises exception on API error."""
        mock_conn = mocker.Mock()
        mock_conn.send_request.return_value = ({"error": "Not found"}, 404)

        with pytest.raises(Exception) as exc_info:
            artifactory_download.get_artifact_info(
                mock_conn, "test-repo", "test/path", "test.rpm"
            )

        assert "AQL query failed with status 404" in str(exc_info.value)

    def test_get_artifact_info_constructs_correct_aql_query(self, mocker):
        """Test that get_artifact_info constructs the correct AQL query."""
        mock_conn = mocker.Mock()
        response_data = {"results": [{"repo": "test-repo", "name": "test.rpm"}]}
        mock_conn.send_request.return_value = (response_data, 200)

        artifactory_download.get_artifact_info(
            mock_conn, "my-repo", "my/path", "myfile.rpm"
        )

        call_args = mock_conn.send_request.call_args
        assert call_args[1]["path"] == "/artifactory/api/search/aql"
        assert call_args[1]["method"] == "POST"
        assert call_args[1]["headers"]["Content-Type"] == "text/plain"
        aql_query = call_args[1]["data"]
        assert "my-repo" in aql_query
        assert "my/path" in aql_query
        assert "myfile.rpm" in aql_query


class TestCreateMetadataYaml:
    """Test cases for create_metadata_yaml function."""

    def test_create_metadata_yaml_creates_file_with_correct_name(self, temp_dir):
        """Test that create_metadata_yaml creates file with correct naming."""
        artifact_info = {
            "repo": "test-repo",
            "name": "test.rpm",
            "sha256": "abc123",  # Mock checksum
            "size": 1024,  # Arbitrary size for test
        }

        result = artifactory_download.create_metadata_yaml(
            artifact_info, temp_dir, "test.rpm"
        )

        expected_path = os.path.join(temp_dir, "test.rpm.metadata.yaml")
        assert result == expected_path
        assert os.path.exists(expected_path)

    def test_create_metadata_yaml_writes_correct_content(self, temp_dir):
        """Test that create_metadata_yaml writes correct YAML content."""
        artifact_info = {
            "repo": "test-repo",
            "name": "test.rpm",
            "sha256": "abc123",  # Mock checksum
            "size": 1024,  # Arbitrary size for test
        }

        result = artifactory_download.create_metadata_yaml(
            artifact_info, temp_dir, "test.rpm"
        )

        import yaml
        with open(result, "r") as f:
            content = yaml.safe_load(f)

        assert content["repo"] == "test-repo"
        assert content["name"] == "test.rpm"
        assert content["sha256"] == "abc123"
        assert content["size"] == 1024


class TestDownloadArtifact:
    """Test cases for download_artifact function."""

    def test_download_artifact_saves_bytes_response(self, mocker, temp_dir):
        """Test that download_artifact handles binary response correctly."""
        mock_conn = mocker.Mock()
        test_content = b"Binary artifact content"
        mock_conn.send_request.return_value = (test_content, 200)

        result = artifactory_download.download_artifact(
            mock_conn, "test-repo", "test/path", "test.rpm", temp_dir
        )

        expected_path = os.path.join(temp_dir, "test.rpm")
        assert result == expected_path
        assert os.path.exists(expected_path)

        with open(expected_path, "rb") as f:
            saved_content = f.read()
        assert saved_content == test_content

    def test_download_artifact_handles_string_response(self, mocker, temp_dir):
        """Test that download_artifact converts string response to bytes."""
        mock_conn = mocker.Mock()
        test_content = "Text artifact content"
        mock_conn.send_request.return_value = (test_content, 200)

        result = artifactory_download.download_artifact(
            mock_conn, "test-repo", "test/path", "test.txt", temp_dir
        )

        expected_path = os.path.join(temp_dir, "test.txt")
        with open(expected_path, "rb") as f:
            saved_content = f.read()
        assert saved_content == test_content.encode("utf-8")

    def test_download_artifact_raises_exception_on_failure(self, mocker, temp_dir):
        """Test that download_artifact raises exception on download failure."""
        mock_conn = mocker.Mock()
        mock_conn.send_request.return_value = ({"error": "Not found"}, 404)

        with pytest.raises(Exception) as exc_info:
            artifactory_download.download_artifact(
                mock_conn, "test-repo", "test/path", "test.rpm", temp_dir
            )

        assert "Download failed with status 404" in str(exc_info.value)

    def test_download_artifact_uses_correct_path(self, mocker, temp_dir):
        """Test that download_artifact constructs correct download path."""
        mock_conn = mocker.Mock()
        mock_conn.send_request.return_value = (b"content", 200)

        artifactory_download.download_artifact(
            mock_conn, "my-repo", "my/path", "myfile.rpm", temp_dir
        )

        call_args = mock_conn.send_request.call_args
        assert call_args[1]["path"] == "/my-repo/my/path/myfile.rpm"
        assert call_args[1]["method"] == "GET"


class TestArtifactoryDownloadModule:
    """Test cases for the main module functionality."""

    def test_module_fails_when_required_params_missing(self, mock_module):
        """Test that module fails when required parameters are missing."""
        set_module_args({"repo": "test-repo"})

        with pytest.raises(AnsibleFailJson) as exc_info:
            artifactory_download.main()

        result = exc_info.value.args[0]
        assert result["failed"] is True
        assert "missing required arguments" in result["msg"]

    def test_module_fails_when_artifact_not_found(self, mock_module, mock_connection):
        """Test that module fails when artifact is not found in Artifactory."""
        set_module_args({
            "repo": "test-repo",
            "path": "test/path",
            "name": "missing.rpm",
            "dest": "/tmp",
        })

        mock_connection.send_request.return_value = ({"results": []}, 200)

        with pytest.raises(AnsibleFailJson) as exc_info:
            artifactory_download.main()

        result = exc_info.value.args[0]
        assert result["failed"] is True
        assert "Artifact not found" in result["msg"]

    def test_module_skips_download_when_file_exists_with_matching_checksum(
        self, mock_module, mock_connection, temp_dir, mocker
    ):
        """Test idempotency - skip download when file exists with matching checksum."""
        test_file = os.path.join(temp_dir, "test.rpm")
        test_content = b"Test content"
        # SHA-256 checksum of b"Test content" calculated via: echo -n "Test content" | sha256sum
        expected_sha256 = "9d9595c5d94fb65b824f56e9999527dba9542481580d69feb89056aabaa0aa87"

        with open(test_file, "wb") as f:
            f.write(test_content)

        set_module_args({
            "repo": "test-repo",
            "path": "test/path",
            "name": "test.rpm",
            "dest": temp_dir,
            "force": False,
        })

        artifact_info = {
            "repo": "test-repo",
            "name": "test.rpm",
            "sha256": expected_sha256,
            "size": len(test_content),  # Actual byte length of b"Test content" (12 bytes)
        }
        mock_connection.send_request.return_value = ({"results": [artifact_info]}, 200)

        # Spy on critical functions to verify actual logic execution
        sha256_spy = mocker.spy(artifactory_download, "sha256_file")
        download_spy = mocker.spy(artifactory_download, "download_artifact")

        with pytest.raises(AnsibleExitJson) as exc_info:
            artifactory_download.main()

        result = exc_info.value.args[0]
        assert result["changed"] is False
        assert "skipping download" in result["msg"]
        assert result["checksum"] == expected_sha256

        # Verify checksum was calculated and download was skipped
        sha256_spy.assert_called_once_with(test_file)
        download_spy.assert_not_called()

    def test_module_downloads_when_force_is_true(
        self, mock_module, mock_connection, temp_dir, mocker
    ):
        """Test that module downloads when force=true even if file exists."""
        test_file = os.path.join(temp_dir, "test.rpm")
        old_content = b"Old content"
        new_content = b"New content"

        with open(test_file, "wb") as f:
            f.write(old_content)

        set_module_args({
            "repo": "test-repo",
            "path": "test/path",
            "name": "test.rpm",
            "dest": temp_dir,
            "force": True,
        })

        artifact_info = {
            "repo": "test-repo",
            "name": "test.rpm",
            # SHA-256 checksum of b"New content" calculated via: echo -n "New content" | sha256sum
            "sha256": "12f41b1c321df0c829ce581996566fde52af6cafe1d2a0c7466cde53e6f13cca",
            "size": len(new_content),  # Actual byte length of b"New content" (11 bytes)
        }

        def mock_send_request(*args, **kwargs):
            if kwargs.get("path") == "/artifactory/api/search/aql":
                return ({"results": [artifact_info]}, 200)
            else:
                return (new_content, 200)

        mock_connection.send_request.side_effect = mock_send_request

        # Spy on download_artifact to verify it's called even with force=true
        download_spy = mocker.spy(artifactory_download, "download_artifact")
        # Also spy on sha256_file to verify checksum validation happens
        sha256_spy = mocker.spy(artifactory_download, "sha256_file")

        with pytest.raises(AnsibleExitJson) as exc_info:
            artifactory_download.main()

        result = exc_info.value.args[0]
        assert result["changed"] is True
        assert "downloaded successfully" in result["msg"]

        # Verify download was called even though file existed
        download_spy.assert_called_once_with(
            mock_connection, "test-repo", "test/path", "test.rpm", temp_dir
        )
        # Verify checksum validation happened after download
        sha256_spy.assert_called_once_with(test_file)

    def test_module_creates_metadata_file_when_requested(
        self, mock_module, mock_connection, temp_dir, mocker
    ):
        """Test that module creates metadata YAML file when metadata=true."""
        set_module_args({
            "repo": "test-repo",
            "path": "test/path",
            "name": "test.rpm",
            "dest": temp_dir,
            "metadata": True,
        })

        artifact_info = {
            "repo": "test-repo",
            "name": "test.rpm",
            # SHA-256 checksum of b"test content" calculated via: echo -n "test content" | sha256sum
            "sha256": "6ae8a75555209fd6c44157c0aed8016e763ff435a19cf186f76863140143ff72",
            "size": 12,  # Actual byte length of b"test content"
        }

        def mock_send_request(*args, **kwargs):
            if kwargs.get("path") == "/artifactory/api/search/aql":
                return ({"results": [artifact_info]}, 200)
            else:
                return (b"test content", 200)

        mock_connection.send_request.side_effect = mock_send_request

        # Spy on functions to verify download and metadata creation happen
        download_spy = mocker.spy(artifactory_download, "download_artifact")
        metadata_spy = mocker.spy(artifactory_download, "create_metadata_yaml")

        with pytest.raises(AnsibleExitJson) as exc_info:
            artifactory_download.main()

        result = exc_info.value.args[0]
        assert result["changed"] is True
        assert "metadata_file" in result
        assert result["metadata_file"].endswith("test.rpm.metadata.yaml")
        assert os.path.exists(result["metadata_file"])

        # Verify both download and metadata creation were called
        download_spy.assert_called_once()
        metadata_spy.assert_called_once_with(artifact_info, temp_dir, "test.rpm")

    def test_module_check_mode_does_not_download(
        self, mock_module, mock_connection, temp_dir, mocker
    ):
        """Test that check mode doesn't actually download the file."""
        set_module_args({
            "repo": "test-repo",
            "path": "test/path",
            "name": "test.rpm",
            "dest": temp_dir,
            "_ansible_check_mode": True,
        })

        artifact_info = {
            "repo": "test-repo",
            "name": "test.rpm",
            "sha256": "abc123",  # Mock checksum
            "size": 1024,  # Arbitrary size for test
        }
        mock_connection.send_request.return_value = ({"results": [artifact_info]}, 200)

        # Spy on download_artifact to verify it's NOT called in check mode
        download_spy = mocker.spy(artifactory_download, "download_artifact")
        # Also spy on sha256_file to verify checksum calculation is NOT called
        sha256_spy = mocker.spy(artifactory_download, "sha256_file")

        with pytest.raises(AnsibleExitJson) as exc_info:
            artifactory_download.main()

        result = exc_info.value.args[0]
        assert result["changed"] is True
        assert "check mode" in result["msg"]
        # Verify download was not called
        assert mock_connection.send_request.call_count == 1  # Only AQL query
        download_spy.assert_not_called()
        sha256_spy.assert_not_called()

    def test_module_fails_on_checksum_mismatch(
        self, mock_module, mock_connection, temp_dir, mocker
    ):
        """Test that module fails when downloaded file checksum doesn't match."""
        set_module_args({
            "repo": "test-repo",
            "path": "test/path",
            "name": "test.rpm",
            "dest": temp_dir,
        })

        artifact_info = {
            "repo": "test-repo",
            "name": "test.rpm",
            "sha256": "wrongchecksum123",  # Intentionally wrong checksum for negative test case
            "size": 1024,  # Arbitrary size for test
        }

        def mock_send_request(*args, **kwargs):
            if kwargs.get("path") == "/artifactory/api/search/aql":
                return ({"results": [artifact_info]}, 200)
            else:
                return (b"actual content", 200)

        mock_connection.send_request.side_effect = mock_send_request

        # Spy on functions to verify download and checksum validation happen
        download_spy = mocker.spy(artifactory_download, "download_artifact")
        sha256_spy = mocker.spy(artifactory_download, "sha256_file")

        with pytest.raises(AnsibleFailJson) as exc_info:
            artifactory_download.main()

        result = exc_info.value.args[0]
        assert result["failed"] is True
        assert "Checksum mismatch" in result["msg"]
        # Verify file was deleted after mismatch
        test_file = os.path.join(temp_dir, "test.rpm")
        assert os.path.exists(test_file) is False

        # Verify download happened and checksum was calculated
        download_spy.assert_called_once()
        sha256_spy.assert_called_once_with(test_file)

    def test_module_creates_destination_directory_if_missing(
        self, mock_module, mock_connection, temp_dir, mocker
    ):
        """Test that module creates destination directory if it doesn't exist."""
        nested_dir = os.path.join(temp_dir, "nested", "path")

        set_module_args({
            "repo": "test-repo",
            "path": "test/path",
            "name": "test.rpm",
            "dest": nested_dir,
        })

        artifact_info = {
            "repo": "test-repo",
            "name": "test.rpm",
            # SHA-256 checksum of b"Test content" calculated via: echo -n "Test content" | sha256sum
            "sha256": "9d9595c5d94fb65b824f56e9999527dba9542481580d69feb89056aabaa0aa87",
            "size": 12,  # Actual byte length of b"Test content"
        }

        def mock_send_request(*args, **kwargs):
            if kwargs.get("path") == "/artifactory/api/search/aql":
                return ({"results": [artifact_info]}, 200)
            else:
                return (b"Test content", 200)

        mock_connection.send_request.side_effect = mock_send_request

        # Spy on download to verify it actually happens
        download_spy = mocker.spy(artifactory_download, "download_artifact")
        sha256_spy = mocker.spy(artifactory_download, "sha256_file")

        with pytest.raises(AnsibleExitJson) as exc_info:
            artifactory_download.main()

        result = exc_info.value.args[0]
        assert result["changed"] is True
        assert os.path.exists(nested_dir)
        assert os.path.exists(os.path.join(nested_dir, "test.rpm"))

        # Verify download and checksum validation happened
        download_spy.assert_called_once()
        sha256_spy.assert_called_once()

    def test_module_fails_on_aql_query_error(self, mock_module, mock_connection):
        """Test that module fails when AQL query returns an error."""
        set_module_args({
            "repo": "test-repo",
            "path": "test/path",
            "name": "test.rpm",
            "dest": "/tmp",
        })

        mock_connection.send_request.return_value = ({"error": "Unauthorized"}, 401)

        with pytest.raises(AnsibleFailJson) as exc_info:
            artifactory_download.main()

        result = exc_info.value.args[0]
        assert result["failed"] is True
        assert "Failed to query artifact metadata" in result["msg"]

    def test_module_fails_on_download_error(self, mock_module, mock_connection, temp_dir):
        """Test that module fails when download request fails."""
        set_module_args({
            "repo": "test-repo",
            "path": "test/path",
            "name": "test.rpm",
            "dest": temp_dir,
        })

        artifact_info = {
            "repo": "test-repo",
            "name": "test.rpm",
            "sha256": "abc123",  # Mock checksum
            "size": 1024,  # Arbitrary size for test
        }

        def mock_send_request(*args, **kwargs):
            if kwargs.get("path") == "/artifactory/api/search/aql":
                return ({"results": [artifact_info]}, 200)
            else:
                return ({"error": "Server error"}, 500)

        mock_connection.send_request.side_effect = mock_send_request

        with pytest.raises(AnsibleFailJson) as exc_info:
            artifactory_download.main()

        result = exc_info.value.args[0]
        assert result["failed"] is True
        assert "Failed to download artifact" in result["msg"]

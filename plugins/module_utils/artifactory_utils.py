import requests
from requests.auth import HTTPBasicAuth


def list_repositories(self, prefix=None):
    """ Retrieve a list of repositories. """
    endpoint = f"{self.base_url}/api/repositories"
    response = requests.get(endpoint, auth=self.auth, headers=self.headers)
    if prefix and response.status_code == 200:
        filtered = [repo for repo in response.json() if repo['key'].startswith(prefix)]
        return filtered
    return response

def search_aql(self, aql_query):
    """ Search Artifactory using AQL (Artifactory Query Language). """
    endpoint = f"{self.base_url}/api/search/aql"
    headers = {'Content-Type': 'text/plain'}
    response = requests.post(endpoint, auth=self.auth, headers=headers, data=aql_query)
    return response

def search_artifact(self, repo, path, name):
    """ Search for all items in a specific repository, including checksums. """
    aql_query = (
        f'items.find({{"repo":{{"$eq":"{repo}"}}, "path":{{"$eq":"{path}"}}, "name":{{"$eq":"{name}"}}}})'
        f'.include("repo", "path", "name", "size", "actual_md5", "actual_sha1", "sha256")'
    )
    return self.search_aql(aql_query)

# --- Example Usage ---
if __name__ == "__main__":
    # Configuration
    URL = "https://repo.cci.nokia.net/artifactory"
    USER = "user"
    TOKEN = "TOKEN"
    REPO = "cbis-generic-releases"
    PATH = "cbis_vlab_repo/24.7.0/ncs/506"
    NAME = "patchiso-24.7.0-506.os8.noarch.rpm"
    client = ArtifactoryClient(URL, USER, TOKEN)

    # Test connection
    res = client.get_system_info()
    if res.status_code == 200:
        print("Successfully authenticated!")
        repositories = client.list_repositories("cbis-")
        for repo in repositories:
            print(repo['key'])
        print ("--------------------------------")
        res = client.search_artifact(REPO, PATH, NAME)
        print(res.text)
        print ("--------------------------------")
    else:
        print(f"Failed to connect. Status Code: {res.status_code}")
        print(res.text)

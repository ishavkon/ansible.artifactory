[artifactory]
${ARTIFACTORY_HOST}

[artifactory:vars]
ansible_connection=httpapi
ansible_network_os=shahargolshani.artifactory.artifactory_api_client
ansible_httpapi_use_ssl=true
ansible_httpapi_validate_certs=false
ansible_httpapi_token=${ARTIFACTORY_TOKEN}
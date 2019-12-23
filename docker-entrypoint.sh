#!/usr/bin/dumb-init /bin/bash

if [ "$1" == 'anchore-manager' ]; then
  shift 1;
  set -- /opt/rh/rh-python36/root/usr/bin/anchore-manager $@
fi

if [[ "${SET_HOSTID_TO_HOSTNAME}" == "true" ]]; then
    echo "Setting ANCHORE_HOST_ID to ${HOSTNAME}"
    export ANCHORE_HOST_ID=${HOSTNAME}
fi

if [[ -f "/opt/rh/rh-python36/enable" ]]; then
    source /opt/rh/rh-python36/enable
fi

# check if /home/anchore/certs/ exists & has files in it
if [[ -d "/home/anchore/certs" ]] && [[ ! -z "$(ls -A /home/anchore/certs)" ]]; then
    mkdir -p /home/anchore/certs_override/python
    mkdir -p /home/anchore/certs_override/os
    ### for python
    cp /opt/rh/rh-python36/root/usr/lib/python3.6/site-packages/certifi/cacert.pem /home/anchore/certs_override/python/cacert.pem
    for file in /home/anchore/certs/*; do
        if grep -q 'BEGIN CERTIFICATE' "${file}"; then
            cat "${file}" >> /home/anchore/certs_override/python/cacert.pem
            cat "${file}" >> /home/anchore/certs_override/python/cacert.pem
        fi
    done
    ### for OS (go, openssl)
    cp -a /etc/pki/tls/certs/* /home/anchore/certs_override/os/
    for file in /home/anchore/certs/*; do
        if grep -q 'BEGIN CERTIFICATE' "${file}"; then
            cat "${file}" >> /home/anchore/certs_override/os/anchore.bundle.crt
            cat "${file}" >> /home/anchore/certs_override/os/anchore.bundle.crt
        fi
    done
    ### setup ENV overrides to system CA bundle utilizing appended custom certs
    export REQUESTS_CA_BUNDLE=/home/anchore/certs_override/python/cacert.pem
    export SSL_CERT_DIR=/home/anchore/certs_override/os/
fi

exec "$@"

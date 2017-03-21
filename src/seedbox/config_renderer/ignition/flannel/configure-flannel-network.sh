#!/bin/bash -ex

function init_flannel {
  echo "Waiting for etcd..."
  while true
  do
      for ETCD in {{ cluster.etcd_endpoints|join(' ') }}; do
          echo "Trying: $ETCD"
          if [ -n "$(curl --fail --silent --show-error "$ETCD/v2/machines")" ]; then
              local ACTIVE_ETCD=$ETCD
              break
          fi
          sleep 1
      done
      if [ -n "$ACTIVE_ETCD" ]; then
          break
      fi
  done

  curl --fail --silent --show-error -X PUT -d "value={\"Network\":\"{{ cluster.k8s_pod_network }}\",\"Backend\":{\"Type\":\"vxlan\"}}" "$ACTIVE_ETCD/v2/keys/coreos.com/network/config"
}

init_flannel

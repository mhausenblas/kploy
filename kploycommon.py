"""
The kploy commons (utility) functions

@author: Michael Hausenblas, http://mhausenblas.info/#i
@since: 2015-12-12
@status: init
"""

import os
import logging

from pyk import toolkit
from pyk import util


def _fmt_cmds(cmds):
    keys = sorted(cmds.keys())
    fk = "\n"
    for k in keys:
        fk += "`" + k + "`, "
    return fk

def _connect(api_server, debug):
    try:
        pyk_client = toolkit.KubeHTTPClient(kube_version="1.1", api_server=api_server, debug=debug)
        pyk_client.execute_operation(method="GET", ops_path="/api/v1")
    except:
        print("\nCan't connect to the Kubernetes cluster at %s\nCheck the `apiserver` setting in your Kployfile, your Internet connection or maybe it's a VPN issue?" %(api_server))
        sys.exit(1)
    return pyk_client

def _visit(dir_name, resource_name):
    """
    Walks a given directory and return list of files in there.
    """
    flist = []
    logging.debug("Visiting %s" %dir_name)
    for _, _, file_names in os.walk(dir_name):
        for afile in file_names:
            logging.debug("Detected %s %s" %(resource_name, afile))
            flist.append(afile)
    return flist

def _dump(alist):
    """
    Dumps a list to the INFO logger.
    """
    for litem in alist:
        logging.info("-> %s" %litem)

def _deploy(pyk_client, here, dir_name, alist, resource_name, verbose):
    """
    Deploys resources based on manifest files. Currently the following resources are supported:
    replication controllers, services.
    """
    for litem in alist:
        file_name = os.path.join(os.path.join(here, dir_name), litem)
        if verbose: logging.info("Deploying %s %s" %(resource_name, file_name))
        if resource_name == "service":
            _, res_url = pyk_client.create_svc(manifest_filename=file_name)
        elif resource_name == "RC":
            _, res_url = pyk_client.create_rc(manifest_filename=file_name)
        else: return None
        res = pyk_client.describe_resource(res_url)
        logging.debug(res.json())

def _destroy(pyk_client, here, dir_name, alist, resource_name, verbose):
    """
    Destroys resources based on manifest files. Currently the following resources are supported:
    replication controllers, services.
    """
    for litem in alist:
        if verbose: logging.info("Trying to destroy %s %s" %(resource_name, file_name))
        file_name = os.path.join(os.path.join(here, dir_name), litem)
        res_manifest, _  = util.load_yaml(filename=file_name)
        res_name = res_manifest["metadata"]["name"]
        if resource_name == "service":
            res_path = "".join(["/api/v1/namespaces/default/services/", res_name])
        elif resource_name == "RC":
            res_path = "".join(["/api/v1/namespaces/default/replicationcontrollers/", res_name])
        else: return None
        pyk_client.delete_resource(resource_path=res_path)

def _check_status(pyk_client, resource_path):
    """
    Checks the status of a resources
    """
    res = pyk_client.describe_resource(resource_path)
    logging.debug(res.json())
    if res.status_code == 200: return "online"
    else: return "offline"
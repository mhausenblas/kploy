#!/usr/bin/env python

"""
The kploy main UX.

@author: Michael Hausenblas, http://mhausenblas.info/#i
@since: 2015-11-29
@status: init
"""

import argparse
import logging
import os
import sys
import pprint
import kploycommon

from tabulate import tabulate
from pyk import toolkit
from pyk import util


DEBUG = False    # you can change that to enable debug messages ...
VERBOSE = False  # ... but leave this one in peace
DEPLOYMENT_DESCRIPTOR = "Kployfile"
RC_DIR = "rcs/"
SVC_DIR = "services/"

if DEBUG:
  FORMAT = "%(asctime)-0s %(levelname)s %(message)s [at line %(lineno)d]"
  logging.basicConfig(level=logging.DEBUG, format=FORMAT, datefmt="%Y-%m-%dT%I:%M:%S")
else:
  FORMAT = "%(asctime)-0s %(message)s"
  logging.basicConfig(level=logging.INFO, format=FORMAT, datefmt="%Y-%m-%dT%I:%M:%S")

logging.getLogger("requests").setLevel(logging.WARNING)

def cmd_dryrun():
    """
    Looks for a `Kployfile` file in the current directory and tries
    to validate its content, incl. syntax validation and mock execution.
    """
    here = os.path.dirname(os.path.realpath(__file__))
    kployfile = os.path.join(here, DEPLOYMENT_DESCRIPTOR)
    if VERBOSE: logging.info("Trying to execute a dry run on %s " %(kployfile))
    try:
        kploy, _  = util.load_yaml(filename=kployfile)
        logging.debug(kploy)
        print("Validating application `%s` ..." %(kploy["name"]))
        
        print("\n  CHECK: Is the Kubernetes cluster up & running and accessible via `%s`?" %(kploy["apiserver"]))
        pyk_client = kploycommon._connect(api_server=kploy["apiserver"], debug=DEBUG)
        nodes = pyk_client.execute_operation(method='GET', ops_path='/api/v1/nodes')
        if VERBOSE: logging.info("Got node list %s " %(util.serialize_tojson(nodes.json())))
        print("  \o/ ... I found %d node(s) to deploy your wonderful app onto." %(len(nodes.json()["items"])))
        
        print("\n  CHECK: Are there RC and service manifests available around here?")
        try:
            rcs = os.path.join(here, RC_DIR)
            logging.debug("Asserting %s exists" %(os.path.dirname(rcs)))
            assert os.path.exists(rcs)
            rc_manifests_confirmed = kploycommon._visit(rcs, 'RC')
            print("         I found %s RC manifest(s) in %s" %(int(len(rc_manifests_confirmed)), os.path.dirname(rcs)))
            if VERBOSE: kploycommon._dump(rc_manifests_confirmed)

            services = os.path.join(here, SVC_DIR)
            logging.debug("Asserting %s exists" %(os.path.dirname(services)))
            assert os.path.exists(services)
            svc_manifests_confirmed = kploycommon._visit(services, 'service')
            print("         I found %s service manifest(s) in %s" %(int(len(svc_manifests_confirmed)), os.path.dirname(services)))
            if VERBOSE: kploycommon._dump(svc_manifests_confirmed)
            print("  \o/ ... I found both RC and service manifests to deploy your wonderful app!")
        except:
            print("No RC and/or service manifests found to deploy your app. You can use `kploy init` to create missing artefacts.")
            sys.exit(1)
    except (IOError, IndexError, KeyError) as e:
        print("Something went wrong:\n%s" %(e))
        sys.exit(1)
    print(80*"=")
    print("\nOK, we're looking good! You're ready to deploy your app with `kploy run` now :)\n")

def cmd_run():
    """
    Looks for a `Kployfile` file in the current directory and tries to run it.
    """
    here = os.path.dirname(os.path.realpath(__file__))
    kployfile = os.path.join(here, DEPLOYMENT_DESCRIPTOR)
    if VERBOSE: logging.info("Trying to run %s " %(kployfile))
    try:
        kploy, _  = util.load_yaml(filename=kployfile)
        logging.debug(kploy)
        pyk_client = kploycommon._connect(api_server=kploy["apiserver"], debug=DEBUG)
        rc_manifests_confirmed, svc_manifests_confirmed = [], []
        services = os.path.join(here, SVC_DIR)
        rcs = os.path.join(here, RC_DIR)
        svc_manifests_confirmed = kploycommon._visit(services, 'service')
        rc_manifests_confirmed = kploycommon._visit(rcs, 'RC')
        kploycommon._deploy(pyk_client, here, SVC_DIR, svc_manifests_confirmed, 'service', VERBOSE)
        kploycommon._deploy(pyk_client, here, RC_DIR, rc_manifests_confirmed, 'RC', VERBOSE)
    except (Error) as e:
        print("Something went wrong deploying your app:\n%s" %(e))
        print("Consider validating your deployment with with `kploy dryrun` first!")
        sys.exit(1)
    print(80*"=")
    print("\nOK, I've deployed `%s`.\nUse `kploy list` to check how it's doing." %(kploy["name"]))

def cmd_list():
    """
    Lists apps and their status.
    """
    here = os.path.dirname(os.path.realpath(__file__))
    kployfile = os.path.join(here, DEPLOYMENT_DESCRIPTOR)
    if VERBOSE: logging.info("Listing resource status of app based on %s " %(kployfile))
    try:
        kploy, _  = util.load_yaml(filename=kployfile)
        print("Resources of `%s`:" %(kploy["name"]))
        pyk_client = kploycommon._connect(api_server=kploy["apiserver"], debug=DEBUG)
        rc_manifests_confirmed, svc_manifests_confirmed = [], []
        services = os.path.join(here, SVC_DIR)
        rcs = os.path.join(here, RC_DIR)
        svc_list = kploycommon._visit(services, 'service')
        rc_list = kploycommon._visit(rcs, 'RC')
        res_list = []
        for svc in svc_list:
            svc_manifest, _  = util.load_yaml(filename=os.path.join(here, SVC_DIR, svc))
            svc_name = svc_manifest["metadata"]["name"]
            svc_path = "".join(["/api/v1/namespaces/default/services/", svc_name])
            svc_URL = "".join([kploy["apiserver"], svc_path])
            svc_status = kploycommon._check_status(pyk_client, svc_path)
            res_list.append([svc_name, os.path.join(SVC_DIR, svc), "service", svc_status, svc_URL])
        for rc in rc_list:
            rc_manifest, _  = util.load_yaml(filename=os.path.join(here, RC_DIR, rc))
            rc_name = rc_manifest["metadata"]["name"]
            rc_path = "".join(["/api/v1/namespaces/default/replicationcontrollers/", rc_name])
            rc_URL = "".join([kploy["apiserver"], rc_path])
            rc_status = kploycommon._check_status(pyk_client, rc_path)
            res_list.append([rc_name, os.path.join(RC_DIR, rc), "RC", rc_status, rc_URL])
        print tabulate(res_list, ["NAME", "MANIFEST", "TYPE", "STATUS", "URL"], tablefmt="plain")
    except (Error) as e:
        print("Something went wrong:\n%s" %(e))
        print("Consider validating your deployment with with `kploy dryrun` first!")
        sys.exit(1)

def cmd_init():
    """
    Creates a dummy `Kployfile` file in the current directory sets up the directories.
    """    
    here = os.path.dirname(os.path.realpath(__file__))
    kployfile = os.path.join(here, DEPLOYMENT_DESCRIPTOR)
    if os.path.exists(kployfile):
        print("Hey! %s already exists.\nI'm not going to destroy existing work. #kthxbye" %(kployfile))
        sys.exit(1)
    if VERBOSE: logging.info("Setting up app %s " %(kployfile))
    ikploy = {}
    ikploy["apiserver"] = "http://localhost:8080"
    ikploy["author"] = "CHANGE_ME"
    ikploy["name"] = "CHANGE_ME"
    ikploy["source"] = "CHANGE_ME"
    if VERBOSE: logging.info("%s" %(ikploy))
    util.serialize_yaml_tofile(kployfile, ikploy)
    if not os.path.exists(SVC_DIR):
        os.makedirs(SVC_DIR)
    if not os.path.exists(RC_DIR):
        os.makedirs(RC_DIR)
    print(80*"=")
    print("\nOK, I've set up the %s deployment file and created necessary directories.\nNow edit the deployment file and copy manifests into the respective directories.\n" %(DEPLOYMENT_DESCRIPTOR))

def cmd_destroy():
    """
    Destroys the app, removing all resources.
    """
    here = os.path.dirname(os.path.realpath(__file__))
    kployfile = os.path.join(here, DEPLOYMENT_DESCRIPTOR)
    if VERBOSE: logging.info("Trying to destroy app based on %s " %(kployfile))
    try:
        kploy, _  = util.load_yaml(filename=kployfile)
        logging.debug(kploy)
        pyk_client = kploycommon._connect(api_server=kploy["apiserver"], debug=DEBUG)
        rc_manifests_confirmed, svc_manifests_confirmed = [], []
        services = os.path.join(here, SVC_DIR)
        rcs = os.path.join(here, RC_DIR)
        svc_manifests_confirmed = kploycommon._visit(services, 'service')
        rc_manifests_confirmed = kploycommon._visit(rcs, 'RC')
        kploycommon._destroy(pyk_client, here, SVC_DIR, svc_manifests_confirmed, 'service', VERBOSE)
        kploycommon._destroy(pyk_client, here, RC_DIR, rc_manifests_confirmed, 'RC', VERBOSE)
    except (Error) as e:
        print("Something went wrong destroying your app:\n%s" %(e))
        print("Consider validating your deployment with with `kploy dryrun` first!")
        sys.exit(1)
    print(80*"=")
    print("\nOK, I've destroyed `%s`\n" %(kploy["name"]))


if __name__ == "__main__":
    try:
        cmds = {
            "dryrun" : cmd_dryrun,
            "run" : cmd_run,
            "list": cmd_list,
            "init": cmd_init,
            "destroy": cmd_destroy
        }

        parser = argparse.ArgumentParser(
            description="kploy is an opinionated Kubernetes deployment system for appops",
            epilog="Examples: `kploy init`, `kploy run`, `kploy list`, or to learn its usage: `kploy explain run`, `kploy explain list`, etc.")
        parser.add_argument("command", nargs="*", help="Currently supported commands are: %s and if you want to learn about a command, prepend `explain`, like: explain list " %(kploycommon._fmt_cmds(cmds)))
        parser.add_argument("-v", "--verbose", help="let me tell you every little dirty secret", action="store_true")
        args = parser.parse_args()
        if len(args.command)==0:
            parser.print_help()
            sys.exit(0)
        if args.verbose:
            VERBOSE = True
        logging.debug("Got command `%s`" %(args))
        if args.command[0] == "explain":
            cmd = args.command[1]
            print(cmd + ":" + cmds[cmd].__doc__)
        else:
            cmd = args.command[0]
            if cmd in cmds.keys():
                cmds[cmd]()
    except:
        sys.exit(1)
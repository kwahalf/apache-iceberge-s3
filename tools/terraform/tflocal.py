#!/usr/bin/env python

"""
borrowed from https://github.com/localstack/terraform-local/blob/main/bin/tflocal 
and updated to suit this repos needs
"""

import plac
import os
import re
import sys
import glob
import subprocess

PARENT_FOLDER = os.path.realpath(os.path.join(os.path.dirname(__file__), '..'))
if os.path.isdir(os.path.join(PARENT_FOLDER, '.venv')):
    sys.path.insert(0, PARENT_FOLDER)

from localstack_client import config  # noqa: E402
import hcl2  # noqa: E402

DEFAULT_REGION = "us-east-1"
LOCALHOST_HOSTNAME = "localhost.localstack.cloud"
S3_HOSTNAME = os.environ.get("S3_HOSTNAME") or f"s3.{LOCALHOST_HOSTNAME}"
USE_EXEC = str(os.environ.get("USE_EXEC")).strip().lower() in ["1", "true"]
TF_CMD = os.environ.get("TF_CMD") or "terraform"
LS_PROVIDERS_FILE = os.environ.get("LS_PROVIDERS_FILE") or "localstack_providers_override.tf"
LOCALSTACK_HOSTNAME = os.environ.get("LOCALSTACK_HOSTNAME") or "localhost"
EDGE_PORT = int(os.environ.get("EDGE_PORT") or 4566)
TF_PROVIDER_CONFIG = """
terraform {
  backend "local" {
  }
  required_providers {
    aws = {
      source = "hashicorp/aws"
      version = "= 5.10.0"
    }
  }
}
provider "aws" {
  access_key                  = "test"
  secret_key                  = "test"
  skip_credentials_validation = true
  skip_metadata_api_check     = true
  <configs>
 endpoints {
<endpoints>
 }
}
"""
PROCESS = None


def create_provider_config_file(provider_aliases=None):
    provider_aliases = provider_aliases or []

    # maps services to be replaced with alternative names
    service_replaces = {
        "apigatewaymanagementapi": "",
        "ce": "costexplorer",
        "edge": "",
        "iotdata": "",
        "iotjobsdata": "",
        "logs": "cloudwatchlogs",
        "timestream": "",
        "dynamodbstreams": "",
        "ioteventsdata": "",
        "iotwireless": "",
        "mediastoredata": "",
        "qldbsession": "",
        "rdsdata": "",
        "sagemakerruntime": "",
        "support": "",
        "timestreamquery": ""
    }
    # service names to be excluded (not yet available in TF)
    service_excludes = ["meteringmarketplace"]

    # create list of service names
    services = list(config.get_service_ports())
    services = [srvc for srvc in services if srvc not in service_excludes]
    services = [s.replace("-", "") for s in services]
    for old, new in service_replaces.items():
        try:
            services.remove(old)
            if new:
                services.append(new)
        except ValueError:
            pass
    services = sorted(services)

    # add default (non-aliased) provider, if not defined yet
    default_provider = [p for p in provider_aliases if not p.get("alias")]
    if not default_provider:
        provider_aliases.append({"region": get_region()})

    # create provider configs
    provider_configs = []
    for provider in provider_aliases:
        endpoints = "\n".join([f'{s} = "{get_service_endpoint(s)}"' for s in services])
        provider_config = TF_PROVIDER_CONFIG.replace("<endpoints>", endpoints)
        additional_configs = []
        if use_s3_path_style():
            additional_configs += [" s3_use_path_style = true"]
        if provider.get("alias"):
            additional_configs += [f' alias = "{provider["alias"]}"']
        region = provider.get("region") or get_region()
        additional_configs += [f' region = "{region}"']
        provider_config = provider_config.replace("<configs>", "\n".join(additional_configs))
        provider_configs.append(provider_config)

    # construct final config file content
    tf_config = "\n".join(provider_configs)

    # write temporary config file
    providers_file = get_providers_file_path()
    if os.path.exists(providers_file):
        msg = f"Providers override file {providers_file} already exists - please delete it first"
        raise Exception(msg)
    with open(providers_file, mode="w") as fp:
        fp.write(tf_config)
    return providers_file


def get_providers_file_path() -> str:
    """Determine the path under which the providers override file should be stored"""
    chdir = [arg for arg in sys.argv if arg.startswith("-chdir=")]
    base_dir = "."
    if chdir:
        base_dir = chdir[0].removeprefix("-chdir=")
    return os.path.join(base_dir, LS_PROVIDERS_FILE)


def get_service_endpoint(service: str) -> str:
    # allow configuring a custom endpoint via the environment
    env_name = f"{service.replace('-', '_').upper().strip()}_ENDPOINT"
    env_endpoint = os.environ.get(env_name, "").strip()
    if env_endpoint:
        if "://" not in env_endpoint:
            env_endpoint = f"http://{env_endpoint}"
        return env_endpoint

    # some services need specific hostnames
    hostname = LOCALSTACK_HOSTNAME

    return f"http://{hostname}:{EDGE_PORT}"


def use_s3_path_style() -> bool:
    regex = r"^[a-z]+://(localhost|[0-9.]+)(:[0-9]+)?$"
    return bool(re.match(regex, get_service_endpoint("s3")))


def get_region() -> str:
    region = str(os.environ.get("AWS_DEFAULT_REGION") or "").strip()
    if region:
        return region
    try:
        # If boto3 is installed, try to get the region from local credentials.
        # Note that boto3 is currently not included in the dependencies, to
        # keep the library lightweight.
        import boto3
        region = boto3.session.Session().region_name
    except Exception:
        pass
    # fall back to default region
    return region or DEFAULT_REGION


def to_bytes(obj) -> bytes:
    return obj.encode("UTF-8") if isinstance(obj, str) else obj


def to_str(obj) -> bytes:
    return obj.decode("UTF-8") if isinstance(obj, bytes) else obj


def determine_provider_aliases() -> list:
    """Return a list of providers (and aliases) configured in the *.tf files (if any)"""
    result = []
    for _file in glob.glob('*.tf'):
        try:
            with open(_file, 'r') as fp:
                obj = hcl2.load(fp)
            providers = obj.get("provider", [])
            providers = [providers] if not isinstance(providers, list) else providers
            aws_providers = [prov["aws"] for prov in providers if prov.get("aws")]
            result.extend(aws_providers)
        except Exception as e:
            print(f"Warning: Unable to extract providers from {_file}:", e)
    return result


def run_tf_exec(cmd, env):
    """Run terraform using os.exec - can be useful as it does not require any I/O
        handling for stdin/out/err. Does *not* allow us to perform any cleanup logic."""
    os.execvpe(cmd[0], cmd, env=env)


def run_tf_subprocess(cmd, env):
    """Run terraform in a subprocess - useful to perform cleanup logic at the end."""
    global PROCESS

    # register signal handlers
    import signal
    signal.signal(signal.SIGINT, signal_handler)

    PROCESS = subprocess.Popen(
        cmd, stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stdout)
    PROCESS.communicate()
    sys.exit(PROCESS.returncode)


def signal_handler(sig, frame):
    PROCESS.send_signal(sig)


def main(*args):
    env = dict(os.environ)
    cmd = (TF_CMD,) + args[1:]

    # create TF provider config file
    providers = determine_provider_aliases()
    config_file = create_provider_config_file(providers)

    # call terraform command
    try:
        if USE_EXEC:
            run_tf_exec(cmd, env)
        else:
            run_tf_subprocess(cmd, env)
    finally:
        os.remove(config_file)


def script_main():
    sys.exit(plac.call(main(*sys.argv)))

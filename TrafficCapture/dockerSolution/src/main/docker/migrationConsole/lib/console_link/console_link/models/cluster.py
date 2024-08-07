from typing import Any, Dict, Optional
from enum import Enum
import logging
import subprocess
from console_link.models.schema_tools import contains_one_of

import boto3
from cerberus import Validator
import requests
import requests.auth
from requests.auth import HTTPBasicAuth

requests.packages.urllib3.disable_warnings()  # ignore: type

logger = logging.getLogger(__name__)

AuthMethod = Enum("AuthMethod", ["NO_AUTH", "BASIC_AUTH", "SIGV4"])
HttpMethod = Enum("HttpMethod", ["GET", "POST", "PUT", "DELETE"])


NO_AUTH_SCHEMA = {
    "nullable": True,
}

BASIC_AUTH_SCHEMA = {
    "type": "dict",
    "schema": {
        "username": {
            "type": "string",
            "required": True,
        },
        "password": {
            "type": "string",
            "required": False,
        },
        "password_from_secret_arn": {
            "type": "string",
            "required": False,
        }
    },
    "check_with": contains_one_of({"password", "password_from_secret_arn"})
}

SIGV4_SCHEMA = {
    "nullable": True,
}

SCHEMA = {
    "cluster": {
        "type": "dict",
        "schema": {
            "endpoint": {"type": "string", "required": True},
            "allow_insecure": {"type": "boolean", "required": False},
            "no_auth": NO_AUTH_SCHEMA,
            "basic_auth": BASIC_AUTH_SCHEMA,
            "sigv4": SIGV4_SCHEMA
        },
        "check_with": contains_one_of({auth.name.lower() for auth in AuthMethod})
    }
}


class Cluster:
    """
    An elasticcsearch or opensearch cluster.
    """

    endpoint: str = ""
    aws_secret_arn: Optional[str] = None
    auth_type: Optional[AuthMethod] = None
    auth_details: Optional[Dict[str, Any]] = None
    allow_insecure: bool = False

    def __init__(self, config: Dict) -> None:
        logger.info(f"Initializing cluster with config: {config}")
        v = Validator(SCHEMA)
        if not v.validate({'cluster': config}):
            raise ValueError("Invalid config file for cluster", v.errors)

        self.endpoint = config["endpoint"]
        self.allow_insecure = config.get("allow_insecure", False) if self.endpoint.startswith(
            "https") else config.get("allow_insecure", True)
        if 'no_auth' in config:
            self.auth_type = AuthMethod.NO_AUTH
        elif 'basic_auth' in config:
            self.auth_type = AuthMethod.BASIC_AUTH
            self.auth_details = config["basic_auth"]
        elif 'sigv4' in config:
            self.auth_type = AuthMethod.SIGV4

    def _get_basic_auth_password(self) -> str:
        assert self.auth_type == AuthMethod.BASIC_AUTH
        assert self.auth_details is not None  # for mypy's sake
        if "password" in self.auth_details:
            return self.auth_details["password"]
        # Pull password from AWS Secrets Manager
        assert "password_from_secret_arn" in self.auth_details  # for mypy's sake
        client = boto3.client('secretsmanager')
        password = client.get_secret_value(SecretId=self.auth_details["password_from_secret_arn"])
        return password["SecretString"]

    def _generate_auth_object(self) -> requests.auth.AuthBase | None:
        if self.auth_type == AuthMethod.BASIC_AUTH:
            assert self.auth_details is not None  # for mypy's sake
            password = self._get_basic_auth_password()
            return HTTPBasicAuth(
                self.auth_details.get("username", None),
                password
            )
        elif self.auth_type is AuthMethod.NO_AUTH:
            return None
        raise NotImplementedError(f"Auth type {self.auth_type} not implemented")

    def call_api(self, path, method: HttpMethod = HttpMethod.GET, data=None, headers=None,
                 timeout=None, session=None, raise_error=True, **kwargs) -> requests.Response:
        """
        Calls an API on the cluster.
        """
        if session is None:
            session = requests.Session()
        
        auth = self._generate_auth_object()

        # Extract query parameters from kwargs
        params = kwargs.get('params', {})

        logger.info(f"Performing request: {method.name} {self.endpoint}{path}")
        r = session.request(
            method.name,
            f"{self.endpoint}{path}",
            verify=(not self.allow_insecure),
            params=params,
            auth=auth,
            data=data,
            headers=headers,
            timeout=timeout
        )
        logger.info(f"Received response: {r.status_code} {method.name} {self.endpoint}{path} - {r.text[:1000]}")
        if raise_error:
            r.raise_for_status()
        return r

    def execute_benchmark_workload(self, workload: str,
                                   workload_params='target_throughput:0.5,bulk_size:10,bulk_indexing_clients:1,'
                                                   'search_clients:1'):
        client_options = "verify_certs:false"
        if not self.allow_insecure:
            client_options += ",use_ssl:true"
        if self.auth_type == AuthMethod.BASIC_AUTH:
            if self.auth_details['password'] is not None:
                client_options += (f",basic_auth_user:{self.auth_details['username']},"
                                   f"basic_auth_password:{self.auth_details['password']}")
            else:
                raise NotImplementedError(f"Auth type {self.auth_type} with AWS Secret ARN is not currently support "
                                          f"for executing benchmark workloads")
        elif self.auth_type == AuthMethod.SIGV4:
            raise NotImplementedError(f"Auth type {self.auth_type} is not currently support for executing "
                                      f"benchmark workloads")
        # Note -- we should censor the password when logging this command
        logger.info(f"Running opensearch-benchmark with '{workload}' workload")
        command = (f"opensearch-benchmark execute-test --distribution-version=1.0.0 --target-host={self.endpoint} "
                   f"--workload={workload} --pipeline=benchmark-only --test-mode --kill-running-processes "
                   f"--workload-params={workload_params} --client-options={client_options}")
        logger.info(f"Executing command: {command}")
        subprocess.run(command, shell=True)

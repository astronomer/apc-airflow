# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from functools import cache
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

import jmespath
import jsonschema
import requests
import yaml
from kubernetes.client.api_client import ApiClient
from requests import Response
from rich.console import Console

api_client = ApiClient()

CHART_DIR = Path(__file__).resolve().parents[3] / "chart"

DEFAULT_KUBERNETES_VERSION = "1.32.0"
BASE_URL_SPEC = "https://raw.githubusercontent.com/yannh/kubernetes-json-schema/refs/heads/master"

GIT_ROOT_DIR = next(iter([x for x in Path(__file__).resolve().parents if (x / ".git").is_dir()]), None)
MY_DIR = Path(__file__).parent.resolve()

crd_lookup = {
    # https://raw.githubusercontent.com/kedacore/keda/v2.0.0/config/crd/bases/keda.sh_scaledobjects.yaml
    "keda.sh/v1alpha1::ScaledObject": f"{MY_DIR.as_posix()}/keda.sh_scaledobjects.yaml"
}


GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

console = Console(width=400, color_system="standard")


def log_github_rate_limit_error(response: Response) -> None:
    """
    Logs info about GitHub rate limit errors (primary or secondary).
    """
    if response.status_code not in (403, 429):
        return

    remaining = response.headers.get("x-rateLimit-remaining")
    reset = response.headers.get("x-rateLimit-reset")
    retry_after = response.headers.get("retry-after")

    try:
        message = response.json().get("message", "")
    except Exception:
        message = response.text or ""

    remaining_int = int(remaining) if remaining and remaining.isdigit() else None

    if reset and reset.isdigit():
        reset_dt = datetime.fromtimestamp(int(reset), tz=timezone.utc)
        reset_time = reset_dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    else:
        reset_time = "unknown"

    if remaining_int == 0:
        print(f"Primary rate limit exceeded. No requests remaining. Reset at {reset_time}.")
        return

    # Message for secondary looks like: "You have exceeded a secondary rate limit"
    if "secondary rate limit" in message.lower():
        if retry_after and retry_after.isdigit():
            print(f"Secondary rate limit exceeded. Retry after {retry_after} seconds.")
        else:
            print(f"Secondary rate limit exceeded. Please wait until {reset_time} or at least 60 seconds.")
        return

    print(f"Rate limit error. Status: {response.status_code}, Message: {message}")


@cache
def get_schema_k8s(api_version, kind, kubernetes_version):
    """Return a standalone k8s schema for use in validation."""
    # This function is mostly the same as astronomer/airflow-chart
    api_version = api_version.lower()
    kind = kind.lower()

    # replace the patch version with 0
    kubernetes_version = ".".join(kubernetes_version.split('.')[:2] + ['0'])

    if "/" in api_version:
        ext, _, api_version = api_version.partition("/")
        ext = ext.split(".")[0]
        schema_path = f"v{kubernetes_version}-standalone-strict/{kind}-{ext}-{api_version}.json"
    else:
        schema_path = f"v{kubernetes_version}-standalone-strict/{kind}-{api_version}.json"

    local_sp = Path(f"{GIT_ROOT_DIR}/k8s_schema/{schema_path}")
    if not local_sp.exists():
        if not local_sp.parent.is_dir():
            local_sp.parent.mkdir(parents=True)
        request = requests.get(f"{BASE_URL_SPEC}/{schema_path}", timeout=30)
        request.raise_for_status()
        local_sp.write_text(request.text)

    return json.loads(local_sp.read_text())


@cache
def get_schema_crd(api_version, kind):
    file = crd_lookup.get(f"{api_version}::{kind}")
    if not file:
        return None
    schema = yaml.safe_load(Path(file).read_text())
    return schema


@cache
def create_validator(api_version, kind, kubernetes_version):
    schema = get_schema_crd(api_version, kind)
    if not schema:
        schema = get_schema_k8s(api_version, kind, kubernetes_version)
    jsonschema.Draft7Validator.check_schema(schema)
    validator = jsonschema.Draft7Validator(schema)
    return validator


def validate_k8s_object(instance, kubernetes_version):
    # Skip PostgreSQL chart
    labels = jmespath.search("metadata.labels", instance)
    if "helm.sh/chart" in labels:
        chart = labels["helm.sh/chart"]
    else:
        chart = labels.get("chart")

    if chart and "postgresql" in chart:
        return

    validate = create_validator(instance.get("apiVersion"), instance.get("kind"), kubernetes_version)
    validate.validate(instance)


class HelmFailedError(subprocess.CalledProcessError):
    def __str__(self):
        return f"Helm command failed. Args: {self.args}\nStderr: \n{self.stderr.decode('utf-8')}"


def render_chart(
    name="release-name",
    values=None,
    show_only=None,
    chart_dir=None,
    kubernetes_version=DEFAULT_KUBERNETES_VERSION,
    namespace=None,
):
    """
    Function that renders a helm chart into dictionaries. For helm chart testing only
    """
    values = values or {}
    chart_dir = chart_dir or str(CHART_DIR)
    namespace = namespace or "default"
    with NamedTemporaryFile() as tmp_file:
        content = yaml.dump(values)
        tmp_file.write(content.encode())
        tmp_file.flush()
        command = [
            "helm",
            "template",
            name,
            chart_dir,
            "--values",
            tmp_file.name,
            "--kube-version",
            kubernetes_version,
            "--namespace",
            namespace,
        ]
        if show_only:
            for i in show_only:
                command.extend(["--show-only", i])
        result = subprocess.run(command, check=False, capture_output=True, cwd=chart_dir)
        if result.returncode:
            raise HelmFailedError(result.returncode, result.args, result.stdout, result.stderr)
        templates = result.stdout
        k8s_objects = yaml.full_load_all(templates)
        k8s_objects = [k8s_object for k8s_object in k8s_objects if k8s_object]  # type: ignore
        for k8s_object in k8s_objects:
            validate_k8s_object(k8s_object, kubernetes_version)
        return k8s_objects


def prepare_k8s_lookup_dict(k8s_objects) -> dict[tuple[str, str], dict[str, Any]]:
    """
    Helper to create a lookup dict from k8s_objects.
    The keys of the dict are the k8s object's kind and name
    """
    k8s_obj_by_key = {
        (k8s_object["kind"], k8s_object["metadata"]["name"]): k8s_object for k8s_object in k8s_objects
    }
    return k8s_obj_by_key


def render_k8s_object(obj, type_to_render):
    """
    Function that renders dictionaries into k8s objects. For helm chart testing only.
    """
    return api_client._ApiClient__deserialize_model(obj, type_to_render)

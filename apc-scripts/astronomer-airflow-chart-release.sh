#!/usr/bin/env bash

# This file is Not licensed to ASF
# SKIP LICENSE INSERTION

ROOT_DIRECTORY=$(pwd)
CHART_DIRECTORY=${ROOT_DIRECTORY}/chart
CHART_RELEASE_DIRECTORY=${ROOT_DIRECTORY}/chart-rel
export ROOT_DIRECTORY CHART_DIRECTORY CHART_RELEASE_DIRECTORY

if [[ ! -d "$CHART_DIRECTORY" ]]; then
  echo "chart directory does not exists ..."
  echo
  echo "Current Working Directory: "
  echo
  ls -ltr
fi

CHART_VERSION="$(awk '$1 ~ /^version/ {printf $2;exit;}' "$CHART_DIRECTORY"/Chart.yaml)"
export CHART_VERSION
export CHART_GH_RELEASE_TAG="oss-helm-chart/$CHART_VERSION"
export CHART_PUBLISH_REPO="https://github.com/astronomer/airflow/releases/download/${CHART_GH_RELEASE_TAG}"

# shellcheck disable=SC2153
export TAG=${GITHUB_REF/refs\/tags\//}
if [[ "$GITHUB_REF" != *"tags"* ]]; then
  export TAG=""
fi
echo "TAG: $TAG"
# shellcheck disable=SC2153
export BRANCH=${GITHUB_REF#refs/*/}
echo "BRANCH: $BRANCH"


function package_chart() {
    echo "Packaging chart ..."
    helm package chart --dependency-update "$CHART_DIRECTORY" --destination "$CHART_RELEASE_DIRECTORY"
}

# If the build is not a tag/release, build a dev version
if [[ -z ${TAG:=} ]]; then
    echo
    echo "Current Chart Version is: ${CHART_VERSION}"
    echo
    package_chart
elif [[ ${TAG:=} == "${BRANCH:=}" ]]; then
    echo
    # TODO: Release the chart
fi

ls -altr "${CHART_RELEASE_DIRECTORY}/"

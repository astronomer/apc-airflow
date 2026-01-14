#!/usr/bin/env bash

ROOT_DIRECTORY="$PWD"
CHART_DIRECTORY=${ROOT_DIRECTORY}/chart
CHART_RELEASE_DIRECTORY=${ROOT_DIRECTORY}/chart-rel

# Report and exit if there is no chart directory
if [[ ! -d "$CHART_DIRECTORY" ]]; then
  echo "ERROR: Directory ${CHART_DIRECTORY} does not exist..."
  echo
  echo "Root directory contents:"
  echo
  ls -ltr "${ROOT_DIRECTORY}"
  exit 1
fi

CHART_VERSION="$(awk '$1 ~ /^version/ {printf $2;exit;}' "$CHART_DIRECTORY"/Chart.yaml)"

echo
echo "Current Chart Version is: ${CHART_VERSION}"
echo
echo "Packaging chart ..."
echo
helm package chart --dependency-update "$CHART_DIRECTORY" --destination "$CHART_RELEASE_DIRECTORY"

ls -altr "${CHART_RELEASE_DIRECTORY}/"

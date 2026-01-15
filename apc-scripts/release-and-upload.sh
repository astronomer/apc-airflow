#!/usr/bin/env bash
set -x

CHART_VERSION=$(awk '/^version: / {print $2}' chart/Chart.yaml | tr -d '"')
RELEASE_NAME="oss-helm-chart/${CHART_VERSION}"

# Exit if we do NOT get a 404, indicating the release already exists
if curl -fsSL -o /dev/null "https://github.com/astronomer/apc-airflow/releases/tag/${RELEASE_NAME}" ; then
  echo "Release ${RELEASE_NAME} already exists. Exiting.  https://github.com/astronomer/apc-airflow/releases/tag/${RELEASE_NAME}"
  exit 1
fi

CHART_FILE="chart-rel/airflow-${CHART_VERSION}.tgz"
if [[ ! -f "$CHART_FILE" ]] ; then
  echo "Chart file $CHART_FILE does not exist."
  exit 1
fi

# Create release with auto-generated notes and upload CHART_FILE
gh repo set-default https://github.com/astronomer/apc-airflow
gh release create --generate-notes "${RELEASE_NAME}" "chart-rel/index.yaml" "${CHART_FILE}"

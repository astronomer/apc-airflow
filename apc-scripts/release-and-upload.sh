#!/usr/bin/env bash
set -x

app_version=$(awk '$1 == "airflowVersion:" {print $2}' chart/values.yaml | tr -d '"')

# Exit if we do NOT get a 404, indicating the release already exists
if curl -fsSL -o /dev/null "https://github.com/astronomer/apc-airflow/releases/tag/oss-helm-chart%2F${app_version}-astro" ; then
  echo "Release oss-helm-chart/${app_version}-astro already exists. Exiting.  https://github.com/astronomer/apc-airflow/releases/tag/oss-helm-chart%2F${app_version}-astro"
  exit 1
fi

CHART_FILE="chart-rel/airflow-${app_version}-dev.tgz"
if [[ ! -f "$CHART_FILE" ]] ; then
  echo "Chart file $CHART_FILE does not exist."
  exit 1
fi

# Create release with auto-generated notes and upload CHART_FILE
gh release create "$RELEASE_VERSION" \
  --generate-notes \
  "$CHART_FILE"

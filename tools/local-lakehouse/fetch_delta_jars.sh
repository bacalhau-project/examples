#!/usr/bin/env bash
set -euo pipefail
mkdir -p "$(dirname "$0")/spark-delta-jars"
cd "$(dirname "$0")"
PKG="io.delta:delta-spark_2.12:3.1.0"
mvn -q dependency:copy -DoutputDirectory=spark-delta-jars \
    -DincludeArtifactIds=$(cut -d: -f2 <<<"$PKG") \
    -DincludeGroupIds=$(cut -d: -f1 <<<"$PKG") \
    -DincludeVersionIds=$(cut -d: -f3 <<<"$PKG")
echo "Delta jars downloaded to spark-delta-jars/"

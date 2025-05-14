#!/usr/bin/env bash
set -e
JAR_DIR="$(dirname "$0")/jars"
mkdir -p "$JAR_DIR"
cd "$JAR_DIR"

curl -LO https://repo1.maven.org/maven2/io/delta/delta-spark_2.12/3.0.0/delta-spark_2.12-3.0.0.jar
curl -LO https://repo1.maven.org/maven2/org/apache/hadoop/hadoop-aws/3.3.6/hadoop-aws-3.3.6.jar
curl -LO https://repo1.maven.org/maven2/com/amazonaws/aws-java-sdk-bundle/1.12.592/aws-java-sdk-bundle-1.12.592.jar

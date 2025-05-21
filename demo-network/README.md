### Local Delta-Lake with Spark

Start the container:

    docker compose -f demo-network/docker-compose.yml up -d delta-lake

Jupyter-Lab is now on http://localhost:8888 and a fully-configured
PySpark shell can be opened with

    docker exec -it delta-lake \
      $SPARK_HOME/bin/pyspark --packages io.delta:${DELTA_PACKAGE_VERSION?}

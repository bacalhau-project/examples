# Use the specified image as the base
FROM opensearchproject/logstash-oss-with-opensearch-output-plugin:8.9.0

## Install any additional plugins here
RUN logstash-plugin install logstash-codec-csv

## Remove the default pipeline
RUN rm /usr/share/logstash/pipeline/*

## Add any additional setup commands here if needed
COPY filters /logstash/filters
COPY templates /logstash/templates
COPY pipeline /usr/share/logstash/pipeline

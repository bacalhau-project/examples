# Use the specified image as the base
FROM opensearchproject/logstash-oss-with-opensearch-output-plugin:8.9.0

# Add any additional setup commands here if needed
COPY filters /logstash/filters
COPY templates /logstash/templates
COPY pipeline /usr/share/logstash/pipeline


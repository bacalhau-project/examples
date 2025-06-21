WITH log_line AS (
    SELECT '127.0.0.1 user-identifier frank [10/Oct/2000:13:55:36 -0700] "GET /apache_pb.gif HTTP/1.0" 200 2326' AS log_entry
),
regex_pattern AS (
    SELECT '^(\S+) (\S+) (\S+) (\[[^\]]+\]) "([^"]+)" (\d+) (\d+)$' AS pattern
)
SELECT
    regexp_extract(log_entry, (SELECT pattern FROM regex_pattern), 1) AS ip,
    regexp_extract(log_entry, (SELECT pattern FROM regex_pattern), 2) AS user_identifier,
    regexp_extract(log_entry, (SELECT pattern FROM regex_pattern), 3) AS username,
    regexp_extract(log_entry, (SELECT pattern FROM regex_pattern), 4) AS timestamp,
    regexp_extract(log_entry, (SELECT pattern FROM regex_pattern), 5) AS raw_request,
    regexp_extract(log_entry, (SELECT pattern FROM regex_pattern), 6) AS status_code,
    regexp_extract(log_entry, (SELECT pattern FROM regex_pattern), 7) AS response_size,
    -- Split the request field
    regexp_extract(regexp_extract(log_entry, (SELECT pattern FROM regex_pattern), 5), '^(\S+) (\S+) (\S+)$', 1) AS http_method,
    regexp_extract(regexp_extract(log_entry, (SELECT pattern FROM regex_pattern), 5), '^(\S+) (\S+) (\S+)$', 2) AS request_string,
    regexp_extract(regexp_extract(log_entry, (SELECT pattern FROM regex_pattern), 5), '^(\S+) (\S+) (\S+)$', 3) AS http_version
FROM log_line;
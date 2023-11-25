-- /Users/alex/Documents/DuckDB/cli_0_9_1/duckdb -c ".read /Users/alex/Documents/DuckDB/scratch_work/bacalhau_log_parsing.sql" 
.timer on
create temp table logs as 
    from read_csv_auto('bacalhau_log_data.txt', delim=' ')
    select 
        column0 as ip,
        -- ignore column1, it's just a hyphen
        column2 as user,
        column3.replace('[','').replace(']','').strptime('%Y-%m-%dT%H:%M:%S.%f%z') as ts,
        column4 as http_type,
        column5 as route,
        column6 as http_spec,
        column7 as http_status,
        column8 as value
;
create temp table time_increments as 
    from generate_series(date_trunc('hour', current_timestamp) - interval '1 year', date_trunc('hour', current_timestamp) + interval '1 year', interval '5 minutes' ) t(ts)
    select
        ts as start_ts,
        ts + interval '5 minutes' as end_ts,
    where
        ts >= ((select min(ts) from logs) - interval '5 minutes')
        and ts <= ((select max(ts) from logs) + interval '5 minutes')
;
create temp table session_duration_and_count as 
with last_login as (
    from logs
    select 
        *,
        max(case when route = '/login' then ts end) over (partition by ip, user order by ts rows between unbounded preceding and current row) as last_login_ts,
)
from last_login
select
    *,
    -- Assuming the first event is always a login
    max(ts) over (partition by ip, user, last_login_ts) as last_txn_ts,
    last_txn_ts - last_login_ts as session_duration,
    sum(case route
        when '/login' then 1 
        when '/logout' then -1
        end) over (order by ts) as session_count,
;
from session_duration_and_count;

from time_increments increments
left join session_duration_and_count sessions
    on increments.start_ts <= sessions.ts
    and increments.end_ts > sessions.ts
select
    start_ts,
    end_ts,
    count(distinct ip) as distinct_ips,
    count(distinct user) as distinct_users,
    count(distinct route) as distinct_routes,
    min(coalesce(session_count, 0)) as min_sessions,
    avg(coalesce(session_count, 0)) as avg_sessions,
    max(coalesce(session_count, 0)) as max_sessions,
group by all
order by
    start_ts
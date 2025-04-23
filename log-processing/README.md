# Log Processing with Bacalhau

This example demonstrates how to use Bacalhau, an open-source distributed compute framework, to efficiently manage, process logs and query logs.

## Challenges in Traditional Log Vending
Organizations juggling high data volumes often face these hurdles:
 - **Volume vs. Value**: Log ingestion involves write-intensive operations, but only a minor fraction of these logs are accessed or deemed valuable.
 - **Real-time Needs**: For real-time applications such as threat detection and health checks, only specific metrics are pivotal. Real-time metric solutions tend to be costlier and harder to oversee. Hence, early aggregation and filtering of these metrics are essential for both cost savings and operational scalability.
 - **Operational Insights**: At times, operators require access to application and server logs for immediate troubleshooting. This access should be facilitated without connecting directly to the numerous production servers producing these logs.
 - **Archival Requirements**: Preserving raw logs is crucial for compliance, audits, and various analytical and operational improvement processes.

To address these varied needs, especially in real-time scenarios, many organizations resort to streaming all logs to a centralized platform or data warehouse. While this method can work, it often leads to spiraling costs and slower insights.

## Solution: Distributed Log Orchestration with Bacalhau

Bacalhau is a distributed compute framework that offers efficient log processing solutions, enhancing current platforms. Its strength lies in its adaptable job orchestration. Let's explore its multi-job approach.

### Job Types

#### 1. Daemon Jobs:

- **Purpose**: Bacalhau agents run continuously on the nodes doing the work (e.g., website, database, middleware, etc), auto-deployed by the orchestrator.

- **Function:** These jobs handle logs at the source, aggregate, and compress them. They then send aggregated logs periodically to platforms like Kafka or Kinesis, or suitable logging services. Every hour, raw logs intended for archiving or batch processing are compressed and moved to places like S3.

#### 2. Service Jobs:

- **Purpose**: Handle continuous intermediate processing like log aggregation, basic statistics, deduplication, and issue detection. They run on a specified number of nodes, with Bacalhau ensuring their optimal performance and health.

- **Function:** Continuous log processing and integration with logging services for instant insights, e.g., Splunk.

#### 3. Batch Jobs:

- **Purpose**: Executed on-demand on a designated number of nodes, with Bacalhau managing node selection, monitoring and failover.

- **Function:** Operates intermittently on data in S3, focusing on in-depth investigations without moving the data, turning nodes into a distributed data warehouse.

#### 4. Ops Jobs:

- **Purpose**: Similar to batch jobs but spanning all nodes matching job selection criteria.

- **Function:** Ideal for urgent investigations where time is critical. End users are granted limited, yet direct access to logs on host machines, avoiding any S3 transfer delays and ensuring rapid insights.

Bacalhau is designed for global reach and reliability. Here's a snapshot of its worldwide log solution.

1. **Local Log Transfers**: Daemon jobs swiftly send logs to close-by storages like regional S3 or MinIO. These jobs stay active, even without Bacalhau connection, safeguarding data during outages.

2. **Regional Log Handling**: Autonomous service jobs in each region channel logs can transmit to regional logging entities for localized insights, a global logging platform for an overarching perspective, or a combination of both.

3. **Smart Batch Operations**: Bacalhau guides batch jobs to nearby data sources, cutting network costs and streamlining global tasks.

4. **Ops Job Flexibility**: Based on permissions, operators can target specific hosts, regions, or the entire network for queries.

Rather than forwarding all logs to a monolithic platform, Bacalhau allows you to:
 - Deploy **daemon jobs** that continuously collect, filter, and compress logs right where they’re generated, allowing you to **fork at the source** for tailored processing paths
 - Send aggregated data to real-time analytics platforms for quick insights
 - Store full, raw logs in inexpensive storage (e.g., S3) for compliance, deep-dive, and batch analytics
 - Query logs directly on compute nodes for immediate troubleshooting
 - Scale quickly on multiple nodes, either on-prem or across different clouds, with minimal manual intervention
 - **Leverage idle or dedicated query fleets to process historical data** stored in cheap object storage, enabling flexible, on-demand analytics without tying up primary compute resources

**Key Advantages**:
 - Substantial bandwidth and cost savings
 - Flexible ingestion pipelines — use your favorite logging stack or data warehouse
 - Simplified troubleshooting with local or near-local query options
 - Straightforward job orchestration via Bacalhau’s CLI or APIs

## Run This Example

```
                   +--------------------------+
                   |      Docker Compose      |
                   +-------------+------------+
                                 |
   +-----------------------------+--------------------------------+  +---------------------+
   |                      Bacalhau Network                        |  |  Orchestrator Node  |
   |                                                              |  |   (Expanso Cloud)   |
   |  +----------------+  +----------------+  +----------------+  |  +----------+----------+
   |  | Compute Node 1 |  | Compute Node 2 |  | Compute Node 3 |  |             |
   |  +----------------+  +----------------+  +----------------+  +-------------+
   |             \              |              /                  |
   |              \             |             /                   |
   |               \            |            /                    |
   |          +-----v-----------v-----------v-----+               |
   |          |         Storage (MinIO)            |              |
   |          +-----------------+------------------+              |
   |                            |                                 |
   |                     +------v-------+                         |
   |                     |  OpenSearch  |                         |
   |                     +------+-------+                         |
   |                            |                                 |
   |               +------------v-----------+                     |     
   |               |  OpenSearch Dashboard  |                     |
   |               +------------------------+                     |
   |                                                              |
   +--------------------------------------------------------------+
```

### Prerequisites
- Docker and Docker Compose
- [Expanso Cloud](https://cloud.expanso.io) account
- [Bacalhau CLI](https://docs.bacalhau.org/getting-started/installation)

### 1. Create an Orchestrator
Use [Expanso Cloud](https://www.cloud.expanso.io/) to create a new Bacalhau network (a managed orchestrator node). Name it however you like. Once created, it will appear in the left-hand side menu bar or under **Networks**.

### 2. Spin Up and Connect Compute Node
1. Under _"+ Node"_ in your new network, obtain the token and NATS URL from the platform.
2. In this directory, update `compute.yaml` with the relevant token and NATS URL replacing all instances of `<TODO>`. If necessary, change the number of compute nodes you want to run under `services.compute.deploy.replicas` in `docker-compose.yml`.

3. We will be using the Bacalhau CLI throughout this example to interact with the network. Enable Bacalhau CLI usage for your network by choosing "_Enable CLI Access_" on the network overview page on Expanso Cloud. This will provide us with the API key environment variable to connect to the orchestrator.

4. Start the environment:
   ```bash
   docker compose up
   ```
   This command will spin up Bacalhau compute nodes, a storage (MinIO) node and OpenSearch nodes.

After a couple of moments you should see the compute nodes in your Expanso Cloud network. You can also run `bacalhau node list` to see the nodes connected to your network.

🎉 Congrats! You now have a Bacalhau network set up with compute nodes and storage.

### 3. Generate Logs

This [daemon](https://docs.bacalhau.org/cli-api/specifications/job/type#daemon-jobs) job will run on all compute nodes and generate logs for this example.

The generated logs follow a structured JSON schema that includes fields capturing detailed request metadata, response metadata and contextual details. Example log:

```
{
  "event": {
    "original": "{\"remote_addr\": \"5.210.15.164\", \"remote_user\": \"-\", \"time_local\": \"2025-04-08T21:58:08\", \"http_method\": \"GET\", \"request\": \"/image/64456/productModel/200x200\", \"http_version\": \"HTTP/1.1\", \"status\": 200, \"body_bytes_sent\": 6920, \"http_referer\": \"https://example.com\", \"http_user_agent\": \"Mozilla/5.0 ...\"}"
  },
  "status": 200,
  "remote_user": "-",
  "http_version": "HTTP/1.1",
  "http_referer": "https://example.com",
  "tags": [
    "raw_log"
  ],
  "http_method": "GET",
  "@timestamp": "2025-04-08T21:58:08.000Z",
  "remote_addr": "5.210.15.164",
  "log": {
    "file": {
      "path": "/app/logs/application.log"
    }
  },
  "request": "/image/64456/productModel/200x200",
  "host": {
    "name": "3acb60a09356"
  },
  "time_local": "2025-04-08T21:58:08",
  "body_bytes_sent": 6920,
  "http_user_agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 12_1_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/12.0 Mobile/15E148 Safari/604.1",
  "@version": "1"
}
```

#### Run with Expanso Cloud

In the Expanso Cloud dashboard, go to **Network > _YourNetwork_ > Jobs > New Job**, create a new job from file, use `generate-logs.yaml` and run it.  Once submitted you should be redirected to the Job page. Here you can see its status, history and executions. Under the executions tab you should see one execution per node.

#### Run with CLI
```bash
bacalhau run job jobs/generate-logs.yaml
```

### 4. Run the Logstash Job

Logstash is a powerful tool for processing and transforming logs. This is another [daemon](https://docs.bacalhau.org/cli-api/specifications/job/type#daemon-jobs) job that will:

- Collect and compress logs from the compute nodes and forward them every hour to the specified S3 bucket. This is great for archival and deep-dive analysis.
- Push aggregated metrics to OpenSearch every `AGGREGATE_DURATION` seconds.

You can learn more about our Logstash pipeline configuration and aggregation implementation in `logstash/`. These are a subset of the aggregated metrics published to OpenSearch:

- Request Counts: Grouped by HTTP status codes.
- Top IPs: Top 10 source IPs by request count.
- Geo Sources: Top 10 geographic locations by request count.
- User Agents: Top 10 user agents by request count.
- Popular APIs & Pages: Top 10 most-hit APIs and pages.
- Gone Pages: Top 10 requested but non-existent pages.
- Unauthorized IPs: Top 10 IPs failing authentication.
- Throttled IPs: Top 10 IPs getting rate-limited.
- Data Volume: Total data transmitted in bytes.

This gives you real-time insights into traffic patterns, performance issues, and potential security risks. All of this is visible through your OpenSearch dashboards.

#### Run with Expanso Cloud

In Expanso Cloud, go to **Network > _YourNetwork_ > Jobs**, create or upload the job `logstash.yaml` and run it.

#### Run with CLI
```bash
bacalhau run job jobs/logstash.yaml
```

After a few minutes, verify logs are being collected by checking your logs bucket at `localhost:9001` (username and password configured in `docker-compose.yml`) and your OpenSearch dashboard at `localhost:5601`.

View the logstash logs with:
```bash
bacalhau job logs <job_id>
```

### 5. Query Logs directly on Compute Node
In cases where you need to query logs immediately due to an incident or alert, Bacalhau [ops](https://docs.bacalhau.org/cli-api/specifications/job/type#ops-jobs) jobs can help you filter logs on the compute node itself since recent logs might not be available in the centralized storage yet.

#### Run with Expanso Cloud

Upload and run a job from the `jobs/queries/basic` directory. We will be running job `error-analysis.yaml` to filter logs for 404 errors right on the compute nodes.

#### Run with CLI
```bash
bacalhau run job jobs/queries/basic/error-analysis.yaml
```

#### Results

```bash
bacalhau job describe <job_id>
```
This will show you the head of the standard output of the job with the filtered results.

### 6. Querying historical logs

Historic log analysis often treads a fine line between accessibility and cost-effectiveness. Typically real-time metrics and aggregated data do the trick, but sometimes a deep dive into raw logs is necessary for comprehensive batch analysis or detailed troubleshooting. However, constantly streaming all raw logs to platforms like Splunk or ElasticSearch can be prohibitively expensive and operationally cumbersome.

To address this, we will use Bacalhau's batch jobs to query older logs that are no longer stored on the host itself but stored in MinIO. This allows us to run queries on the logs without needing to stream all logs to a centralized platform.

#### Run with Expanso Cloud

To streamline this process, we will first create a reusable job template in Expanso Cloud for repeated batch queries against historical data. Navigate to **Templates > New** on Expanso Cloud to begin. Upload the job `jobs/queries/deep-dive/top-referring-sites.yaml` to open it in the editor. On the right-hand side you'll see the variables detected in the template - namely `region` and `date`. Click 'Save' and name the template "_Top Referring Sites_".

To run a query using this template, go to **Network > _YourNetwork_ > Jobs > New Job** and select the template you just created. You'll be prompted to provide values for the variables before execution. For `region` use `us-east-1` and for `date` use whatever date you want to query or a range such as `2025-01-*`. If you're uncertain which dates to query, you can inspect available folders in MinIO by visiting `localhost:9001`.

#### Run with CLI
Using templates in the CLI is straightforward. All you need to do is run the following command, replacing the variables with your desired values:

```bash
bacalhau run job jobs/queries/deep-dive/top-referring-sites.yaml --template-vars "region=us-east-1,date=2025-*"
```

#### Results

Once the job has completed use the Bacalhau CLI to view the results:
```bash
bacalhau job describe <job_id>
```
This will show you the standard output of the job with the filtered results.

## Additional Resources
 - [__Job Types__](https://docs.bacalhau.org/cli-api/specifications/job/type) 
 - [__Save $2.5M Per Year by Managing Logs the AWS Way__](https://blog.bacalhau.org/p/save-25m-yoy-by-managing-logs-the?utm_source=publication-search)

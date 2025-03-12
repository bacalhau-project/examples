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
Rather than forwarding all logs to a monolithic platform, Bacalhau allows you to:
 - Deploy **daemon jobs** that continuously collect, filter, and compress logs right where they’re generated
 - Send aggregated data to real-time analytics platforms for quick insights
 - Store full, raw logs in inexpensive storage (e.g., S3) for compliance, deep-dive, and batch analytics
 - Query logs directly on compute nodes for immediate troubleshooting
 - Scale quickly on multiple nodes, either on-prem or across different clouds, with minimal manual intervention

**Key Advantages**:
 - Substantial bandwidth and cost savings
 - Flexible ingestion pipelines — use your favorite logging stack or data warehouse
 - Simplified troubleshooting with local or near-local query options
 - Straightforward job orchestration via Bacalhau’s CLI or APIs

## Run This Example

### Prerequisites
- Docker and Docker Compose
- [Expanso Cloud](https://cloud.expanso.io) account

### 1. Create an Orchestrator
Use [Expanso Cloud](https://www.cloud.expanso.io/) to create a new Bacalhau network (a managed orchestrator node). Name it however you like.

### 2. Spin Up and Connect Compute Node
1. Under _"+ Node"_ in your new network, obtain the token and NATS URL from the platform.
2. In this directory, update `compute.yaml` with the relevant token and NATS URL replacing all instances of `<TODO>`. If necessary, change the number of compute nodes you want to run under `services.compute.deploy.replicas` in `docker-compose.yml`.

3. Start the environment:
   ```bash
   docker compose up
   ```
   This command will spin up Bacalhau compute nodes, a storage (MinIO) node and OpenSearch nodes.

### 3. Generate Logs
In the Expanso Cloud dashboard, go to **Network > _YourNetwork_ > Jobs**, create a new job from file, use `generate-logs.yaml` and run it. This [daemon](https://docs.bacalhau.org/cli-api/specifications/job/type#daemon-jobs) job will run on all compute nodes and generate logs for this example. Once submitted you should be redirected to the Job page. Here you can see its status, history and executions. Under the executions tab you should see one execution per node.

### 4. Run the Logstash Job
In Expanso Cloud, go to **Network > _YourNetwork_ > Jobs**, create or upload the job `logstash.yaml` and run it. This is another [daemon](https://docs.bacalhau.org/cli-api/specifications/job/type#daemon-jobs) job that will collect logs, writing aggregated logs to OpenSearch, and storing raw logs in MinIO. After a few minutes, verify logs are being collected by checking your logs bucket at `localhost:9001` (username and password configured in `docker-compose.yml`) and your OpenSearch dashboard at `localhost:5601`.

### 5. Query Logs directly on Compute Node
In cases where you need to query logs immediately due to an incident or alert, Bacalhau [ops](https://docs.bacalhau.org/cli-api/specifications/job/type#ops-jobs) jobs can help you filter logs on the compute node itself since recent logs might not be available in the centralized storage yet.

Upload and run the job `query-logs.yaml` to filter logs for specific HTTP statuses (for example, 404 errors) right on the compute nodes. The results will be stored in MinIO.

## Additional Resources
 - [__Job Types__](https://docs.bacalhau.org/cli-api/specifications/job/type) 
 - [__Save $2.5M Per Year by Managing Logs the AWS Way__](https://blog.bacalhau.org/p/save-25m-yoy-by-managing-logs-the?utm_source=publication-search)

High-Scale Data Processing with Azure Cosmos DB and Expanso 

Demo Overview 

Duration: 25-30 minutes  

Target Audience: Developers working with distributed systems and data processing  

Primary Message: Demonstrate how to efficiently process and ingest data at scale using Expanso's distributed processing capabilities with Azure Cosmos DB as the backend. 

Introduction (3-4 minutes) 

Problem Statement 

Modern applications generate data across multiple regions, zones, and edge locations 

Traditional centralized processing creates high network costs and processing delays 

Organizations need efficient ways to process data where it's created before centralization 

Solution Overview 

Expanso provides distributed job orchestration across any location 

Azure Cosmos DB offers unlimited scale and multi-region support 

Combined solution enables efficient data processing at the edge with reliable central storage 

Technical Demo (15-20 minutes) 

Setup Phase (5 minutes) 

[Show terminal window split with Cosmos DB portal] 

PRESENTER: "Let me show you what we've set up for today's demo. We have 1000 spot nodes distributed across five Azure regions. Each node is running our lightweight Bacalhau agent, which you can see here in our dashboard." 

[Show Expanso dashboard with node distribution] 

PRESENTER: "Notice how each node is only using minimal resources - about 50MB of RAM and negligible CPU when idle. This is crucial because these agents can run alongside your existing workloads without interference." 

[Switch to Cosmos DB setup] 

PRESENTER: "On the Azure side, we've configured a Cosmos DB container optimized for high-throughput ingestion. Let's look at the key configuration:" 

[Show Python configuration code] 

from azure.cosmos import CosmosClient, PartitionKey 

 

client = CosmosClient(endpoint, credential) 

 

database = client.create_database_if_not_exists(id=DATABASE_NAME) 

 

# Autoscale enabled 

container = database.create_container_if_not_exists(id=CONTAINER_NAME, partition_key=PartitionKey(path="/region"), offer_throughput=10000) 

 

PRESENTER: "We've set up autoscaling throughput and partitioned by region to optimize for our distributed ingestion pattern." 

Live Demo Execution (10 minutes) 

[Show split screen: Bacalhau CLI, Python code, and monitoring dashboard] 

PRESENTER: "Let's kick off our distributed processing job. We'll be processing 50 million log entries, demonstrating both the speed of processing and the efficiency of our distributed approach." 

[Launch job with command] 

bacalhau job run --template python-cosmos 

PRESENTER: "Watch our real-time visualization as data begins flowing. Each dot represents a batch of 1000 records being processed and inserted into Cosmos DB." 

[Show live visualization dashboard with: 

Per-node throughput bars 

Global ingestion rate counter 

Network bandwidth savings gauge 

Cosmos DB RU consumption graph] 

PRESENTER: "Notice a few key things happening: 

Each node is processing roughly 1 million records 

Our RU consumption is staying within optimal ranges 

We're seeing about 85% reduction in network traffic compared to centralized processing 

Cosmos DB is auto-scaling to handle our throughput" 

[Show error handling in action] 

Results Analysis (5 minutes) 

[Switch to Cosmos DB Data Explorer] 

PRESENTER: "In just under a minute, we've processed and inserted 50 million records. Let's verify our data:" 

[Run aggregation query] 

SELECT c.region, 

COUNT(1) as record_count, 

AVG(c.processingTime) as avg_processing_ms 

FROM c GROUP BY c.region 

[ Back to Job Description] 

PRESENTER: Ok, that’s uploading raw data, but what about if we want to do some processing over the data before we move it. We can do that too, and make sure the data that lands on Cosmos is Schematized and Clean. 

[Show data cleaning job] As you can see here, we’re going to do some initial filtering and aggregation of the data. 

[Launch job with command] 

bacalhau job run --template python-cosmos-clean 

[Show uploads of the data] 

PRESENTER: "Now the power here isn't just the speed - it's that we've already performed initial aggregation and transformation at the edge, saving both compute costs and enabling immediate analytics on our data." 

[Show monitoring dashboard final stats] 

Total records processed: 50 million 

Total processing time: 51 seconds 

Average throughput: ~980,000 records/second 

Network bandwidth saved: 2.3 TB 

Cosmos DB RU utilization: 85% 

Key Takeaways (3-4 minutes) 

Benefits 

Reduced network costs through edge processing 

Improved processing speed with distributed execution 

Simplified management of distributed workloads 

Reliable data storage with Azure Cosmos DB 

Implementation Guidance 

Best practices for deployment 

Scaling considerations 

Resource optimization tips 

Call to Action 

Access demo repository on GitHub 

Try Expanso's free tier 

Create Azure Cosmos DB free account 

Documentation links for both platforms 

Technical Requirements 

Python SDK for Azure Cosmos DB 

Expanso deployment configuration 

Demo environment setup instructions 

Sample data processing code 
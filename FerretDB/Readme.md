setting-up-bacalhau-network-aws-spot - changed spot creation scripts to deploy different type of nodes (i.e. one FerretDB node on x86_64 and couple arm64 Bacalhau compute nodes)

[See here for details](setting-up-bacalhau-network-aws-spot/Readme.md)


Changelog:
 - instances changed from micro -> small (bit more RAM)
 - a node-info file now accessible for jobs (placed also in /bacalhau-data folder)
 - added generate_sensor_logs_job, a daemon job that will create sqlite database; its location and sensor name comes from host label variables
 - added simple script to grab data from sqlite and put it in FerretDB
 - job that should run data synchronization script

PROBLEM:
When submitting the job:
Error: code=400, message=models.Network: unknown type 'Host', internal=models.Network: unknown type 'Host'

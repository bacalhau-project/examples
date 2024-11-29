import boto3

client = boto3.client('ec2')

tag = { 'Key':'Bacalhau', 'Value':'Testinstance'}

response = client.describe_instances()

reservations = response['Reservations']

for reservation in reservations:
    instances = reservation['Instances']
    
    for instance in instances:
        if (tag in instance['Tags'] and 'running' in instance['State']['Name']):
            resourcs = boto3.resource('ec2')
            instanc = resourcs.Instance(instance['InstanceId'])
            instanc.terminate()

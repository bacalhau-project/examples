import * as cdk from 'aws-cdk-lib';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as search from 'aws-cdk-lib/aws-opensearchservice';
import * as secretsmanager from 'aws-cdk-lib/aws-secretsmanager';
import {readFileSync} from 'fs';

export interface BacalhauStackProps extends cdk.StackProps {
    readonly keyName: string; // SSH key pair name
}

export class BacalhauStack extends cdk.Stack {
    constructor(app: cdk.App, id: string, props: BacalhauStackProps) {
        super(app, id, props);

        const { keyName } = props;  // Destructure the keyName from the props

        // Create VPC
        const vpc = new ec2.Vpc(this, 'Vpc', {
            maxAzs: 3,
            ipAddresses: ec2.IpAddresses.cidr('10.1.0.0/16'),
            subnetConfiguration: [
                {
                    cidrMask: 24,
                    name: 'PublicSubnet',
                    subnetType: ec2.SubnetType.PUBLIC,
                },
                {
                    cidrMask: 24,
                    name: 'PrivateSubnet',
                    subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS,
                }
            ],
        });

        // Create Security Group for Bacalhau
        const sg = new ec2.SecurityGroup(this, 'SecurityGroup', {
            vpc,
            allowAllOutbound: true,
        });
        // Allow SSH access from anywhere
        sg.addIngressRule(ec2.Peer.anyIpv4(), ec2.Port.tcp(22));
        // Allow Bacalhau API access from anywhere
        sg.addIngressRule(ec2.Peer.anyIpv4(), ec2.Port.tcp(1234));
        // Allow IPFS swarm access internally
        sg.addIngressRule(ec2.Peer.ipv4(vpc.vpcCidrBlock), ec2.Port.tcp(1235));

        // Create IAM Role for the Orchestrator Nodes
        const orchestratorRole = new iam.Role(this, 'OrchestratorRole', {
            assumedBy: new iam.ServicePrincipal('ec2.amazonaws.com'),
            inlinePolicies: {
                'AllowEC2AttachVolume': new iam.PolicyDocument({
                    statements: [
                        new iam.PolicyStatement({
                            actions: [
                                'ec2:AttachVolume',
                                'ec2:DetachVolume',
                                'ec2:DescribeVolumes',
                            ],
                            resources: ['*'],
                            conditions: {
                                'StringEqualsIfExists': {
                                    'aws:RequestTag/aws:cloudformation:stack-id': this.stackId,
                                }
                            }
                        }),
                    ]
                }),
            }
        });

        // Create IAM Role for the Compute Nodes
        const computeRole = new iam.Role(this, 'ComputeRole', {
            assumedBy: new iam.ServicePrincipal('ec2.amazonaws.com'),
            inlinePolicies: {
                'AllowEC2AttachVolume': new iam.PolicyDocument({
                    statements: [
                        new iam.PolicyStatement({
                            actions: [
                                'ec2:AttachVolume',
                                'ec2:DetachVolume',
                                'ec2:DescribeVolumes',
                            ],
                            resources: ['*'],
                            conditions: {
                                'StringEqualsIfExists': {
                                    'aws:RequestTag/aws:cloudformation:stack-id': this.stackId,
                                }
                            }
                        }),
                    ]
                }),
            }
        });

        // Machine Image for Orchestrator and Compute Nodes
        const machineImage = new ec2.LookupMachineImage({
            name: 'ubuntu/images/hvm-ssd/ubuntu-focal-20.04-amd64-server-*',
            owners: ['099720109477'], // Canonical's owner ID for public Ubuntu images
        })

        // load contents of script
        const baseInstallScript = readFileSync('./init-scripts/install-node.sh', 'utf8');

        const orchestratorVolume = new ec2.Volume(this, 'OrchestratorVolume', {
            volumeName: 'OrchestratorVolume',
            availabilityZone: vpc.availabilityZones[0],
            size: cdk.Size.gibibytes(20),
            removalPolicy: cdk.RemovalPolicy.DESTROY,
        });

        // Create Orchestrator Node
        const orchestratorInstance = new ec2.Instance(this, 'OrchestratorNode', {
            vpc,
            vpcSubnets: {
                subnetType: ec2.SubnetType.PUBLIC,
            },
            instanceType: ec2.InstanceType.of(ec2.InstanceClass.T3, ec2.InstanceSize.MICRO),
            machineImage: machineImage,
            securityGroup: sg,
            role: orchestratorRole,
            keyName: keyName,
            userData: this.generateOrchestratorUserData(baseInstallScript, orchestratorVolume.volumeId),
            userDataCausesReplacement: true,
        });

        const orchestratorElasticIP = new ec2.CfnEIP(this, 'OrchestratorIP');
        new ec2.CfnEIPAssociation(this, 'OrchestratorIPAssociation', {
            eip: orchestratorElasticIP.ref,
            instanceId: orchestratorInstance.instanceId
        });

        // Create 3 Compute Nodes
        for (let i = 1; i <= 3; i++) {
            const availabilityZone = vpc.availabilityZones[i-1]

            const computeVolume = new ec2.Volume(this, `WebServerNode${i}Volume`, {
                volumeName: `WebServerNode${i}Volume`,
                availabilityZone: availabilityZone,
                size: cdk.Size.gibibytes(500),
                removalPolicy: cdk.RemovalPolicy.DESTROY,
            });

            const computeNode = new ec2.Instance(this, `WebServerNode${i}`, {
                vpc,
                availabilityZone: availabilityZone,
                vpcSubnets: {
                    subnetType: ec2.SubnetType.PUBLIC,
                },
                instanceType: ec2.InstanceType.of(ec2.InstanceClass.M7I, ec2.InstanceSize.LARGE),
                machineImage: machineImage,
                securityGroup: sg,
                role: computeRole,
                keyName: keyName,
                userData: this.generateComputeUserData(baseInstallScript, computeVolume.volumeId, orchestratorInstance.instancePrivateIp, i),
                userDataCausesReplacement: true,
            });

            new ec2.CfnEIPAssociation(this, `WebServerNode${i}IPAssociation`, {
                eip: new ec2.CfnEIP(this, `WebServerNode${i}IP`).ref,
                instanceId: computeNode.instanceId
            });
        }

        // openSearch master password
        const openSearchPassword = new secretsmanager.Secret(this, 'BacalhauOpenSearchMasterPassword', {
            description: 'Initial password for the OpenSearch master user',
        });

        // Create OpenSearch instance
        const openSearch = new search.Domain(this, 'BacalhauOpenSearch', {
            version: search.EngineVersion.OPENSEARCH_2_7,
            capacity: {
                dataNodeInstanceType: 't3.small.search',
            },
            ebs: {
                volumeSize: 20,
            },
            removalPolicy: cdk.RemovalPolicy.DESTROY, // For dev/test only
            useUnsignedBasicAuth: true, // For dev/test only
            fineGrainedAccessControl: {
                masterUserName: 'admin',
                masterUserPassword: openSearchPassword.secretValue,
            },
        });

        openSearch.grantIndexWrite('aggregated-*', computeRole)

        // Create S3 bucket
        const bucket = new s3.Bucket(this, 'Bucket', {
          removalPolicy: cdk.RemovalPolicy.DESTROY,  // For dev/test only
        });

        computeRole.addToPolicy(new iam.PolicyStatement({
            actions: ['s3:GetObject', 's3:GetObjectVersion', 's3:ListBucket', 's3:PutObject'],
            resources: [bucket.bucketArn, bucket.arnForObjects('*')],
        }))

        // Output the public IP address of the EC2 instance
        new cdk.CfnOutput(this, 'OrchestratorPublicIp', {
            value: `export BACALHAU_NODE_CLIENTAPI_HOST=${orchestratorInstance.instancePublicIp}`,
            description: 'Run this command to set the public IP address of the orchestrator instance as an environment variable.',
        });

        // Output the bucket name
        new cdk.CfnOutput(this, 'BucketName', {
            value: bucket.bucketName,
            description: 'The name of the S3 bucket.',
        });

        // Output the OpenSearch endpoint
        new cdk.CfnOutput(this, 'OpenSearchDashboard', {
            value: openSearch.domainEndpoint + '/_dashboards',
            description: 'The URL of the OpenSearch dashboard.',
        });

        // Output the OpenSearch master password
        new cdk.CfnOutput(this, 'OpenSearchMasterCredentials', {
            value: `aws secretsmanager get-secret-value --secret-id "${openSearchPassword.secretArn}" --query 'SecretString' --output text`,
            description: 'Run this command to get the OpenSearch master password.',
        });
    }

    private generateOrchestratorUserData(baseScript: string, volumeId: string): ec2.UserData {
        return ec2.UserData.custom(`#!/bin/bash
export BACALHAU_VERSION='v1.1.2'
export TARGET_PLATFORM='linux_amd64'
export VOLUME_ID='${volumeId}'
${baseScript}
`);
    }

    private generateComputeUserData(baseScript: string, volumeId: string, orchestratorIp: string, i: number): ec2.UserData {
        return ec2.UserData.custom(`#!/bin/bash
export BACALHAU_VERSION='v1.1.2'
export TARGET_PLATFORM='linux_amd64'
export VOLUME_ID='${volumeId}'
export BACALHAU_ORCHESTRATOR_IP='${orchestratorIp}'
export BACALHAU_LABELS='service=web-server,name=web-server-${i}'
${baseScript}
`);
    }
}

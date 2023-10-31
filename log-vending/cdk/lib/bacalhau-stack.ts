import * as cdk from 'aws-cdk-lib';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as search from 'aws-cdk-lib/aws-opensearchservice';
import * as secretsmanager from 'aws-cdk-lib/aws-secretsmanager';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as custom from 'aws-cdk-lib/custom-resources';
import * as logs from 'aws-cdk-lib/aws-logs';
import {readFileSync} from 'fs';

export interface BacalhauStackProps extends cdk.StackProps {
    readonly bacalhauVersion: string; // Bacalhau version
    readonly targetPlatform: string; // Bacalhau target platform
    readonly orchestratorInstanceType: string; // EC2 instance type for the orchestrator
    readonly webServerInstanceType: string; // EC2 instance type for compute nodes
    readonly webServerInstanceCount: number; // Number of compute nodes
    readonly openSearchInstanceType: string; // OpenSearch instance type
    readonly keyName: string; // SSH key pair name
}

export class BacalhauStack extends cdk.Stack {
    private readonly props: BacalhauStackProps
    private vpc: ec2.Vpc;
    private orchestratorInstance: ec2.Instance;
    private computeRole: iam.Role;
    private machineImage: ec2.LookupMachineImage;

    constructor(app: cdk.App, id: string, props: BacalhauStackProps) {
        super(app, id, props);

        this.props = props;
        this.createVPC();
        this.setupMachineImage();

        // load contents of script
        const baseInstallScript = readFileSync('./init-scripts/install-node.sh', 'utf8');
        this.createOrchestratorInstance(baseInstallScript)

        this.computeRole = this.createEC2Role("ComputeRole")
        this.createComputeInstances(baseInstallScript);

        this.createOpenSearchDomain();
        this.createS3Bucket();
    }


    private createVPC() {
        // Create VPC
        this.vpc = new ec2.Vpc(this, 'Vpc', {
            maxAzs: 3, // Max availability zones
            ipAddresses: ec2.IpAddresses.cidr('10.1.0.0/16'), // CIDR block
            subnetConfiguration: [ // Subnet configuration
                { cidrMask: 24, name: 'PublicSubnet', subnetType: ec2.SubnetType.PUBLIC },
                { cidrMask: 24, name: 'PrivateSubnet', subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS }
            ],
        });
    }

    // Machine Image for Orchestrator and Compute Nodes
    private setupMachineImage() {
        this.machineImage = new ec2.LookupMachineImage({
            name: 'ubuntu/images/hvm-ssd/ubuntu-focal-20.04-amd64-server-*',
            owners: ['099720109477'], // Canonical's owner ID for public Ubuntu images
        })
    }

    // Create Security Group for Bacalhau instances
    private createSecurityGroup(id: string) {
        const securityGroup = new ec2.SecurityGroup(this, id, {
            vpc: this.vpc,
            allowAllOutbound: true,
        });
        // Allow SSH access from anywhere
        securityGroup.addIngressRule(ec2.Peer.anyIpv4(), ec2.Port.tcp(22));
        // Allow Bacalhau API access from anywhere
        securityGroup.addIngressRule(ec2.Peer.anyIpv4(), ec2.Port.tcp(1234));
        // Allow IPFS swarm access internally
        securityGroup.addIngressRule(ec2.Peer.ipv4(this.vpc.vpcCidrBlock), ec2.Port.tcp(1235));
        return securityGroup;
    }

    // Creates an Orchestrator Node EC2 instance
    private createOrchestratorInstance(baseInstallScript: string) {
        // Create Orchestrator Volume
        const orchestratorVolume = new ec2.Volume(this, 'OrchestratorVolume', {
            volumeName: 'OrchestratorVolume',
            availabilityZone: this.vpc.availabilityZones[0],
            size: cdk.Size.gibibytes(20),
            removalPolicy: cdk.RemovalPolicy.DESTROY,
        });

        // Create Orchestrator Node
        const orchestratorInstance = new ec2.Instance(this, 'OrchestratorNode', {
            vpc: this.vpc,
            vpcSubnets: {
                subnetType: ec2.SubnetType.PUBLIC,
            },
            instanceType: new ec2.InstanceType(this.props.orchestratorInstanceType),
            machineImage: this.machineImage,
            securityGroup: this.createSecurityGroup("OrchestratorSecurityGroup"),
            role: this.createEC2Role("OrchestratorRole"),
            keyName: this.props.keyName,
            userData: this.generateOrchestratorUserData(baseInstallScript, orchestratorVolume.volumeId),
            userDataCausesReplacement: true,
        });

        // Create Elastic IP for Orchestrator
        const orchestratorElasticIP = new ec2.CfnEIP(this, 'OrchestratorIP');
        new ec2.CfnEIPAssociation(this, 'OrchestratorIPAssociation', {
            allocationId: orchestratorElasticIP.attrAllocationId,
            instanceId: orchestratorInstance.instanceId
        });
        this.orchestratorInstance = orchestratorInstance;

        // Output the public IP address of the EC2 instance
        new cdk.CfnOutput(this, 'OrchestratorPublicIp', {
            value: orchestratorInstance.instancePublicIp,
            description: 'The public IP address of the Orchestrator instance.',
        });
    }

    // Creates 3 Compute Node EC2 instances
    private createComputeInstances(baseInstallScript: string) {
        const securityGroup = this.createSecurityGroup("ComputeSecurityGroup");

        // Create 3 Compute Nodes
        for (let i = 1; i <= this.props.webServerInstanceCount; i++) {
            const availabilityZone = this.vpc.availabilityZones[i - 1]

            // Create Compute Volume
            const computeVolume = new ec2.Volume(this, `WebServerNode${i}Volume`, {
                volumeName: `WebServerNode${i}Volume`,
                availabilityZone: availabilityZone,
                size: cdk.Size.gibibytes(100),
                removalPolicy: cdk.RemovalPolicy.DESTROY,
            });

            // Create Compute Node
            const computeNode = new ec2.Instance(this, `WebServerNode${i}`, {
                vpc: this.vpc,
                availabilityZone: availabilityZone,
                vpcSubnets: {
                    subnetType: ec2.SubnetType.PUBLIC,
                },
                blockDevices: [
                    {
                        deviceName: '/dev/sda1',
                        volume: ec2.BlockDeviceVolume.ebs(20),  // root volume
                    },
                ],
                instanceType: new ec2.InstanceType(this.props.webServerInstanceType),
                machineImage: this.machineImage,
                securityGroup: securityGroup,
                role: this.computeRole,
                keyName: this.props.keyName,
                userData: this.generateComputeUserData(baseInstallScript, computeVolume.volumeId, this.orchestratorInstance.instancePrivateIp, i),
                userDataCausesReplacement: true,
            });

            // Create Elastic IP for Compute Node
            new ec2.CfnEIPAssociation(this, `WebServerNode${i}IPAssociation`, {
                allocationId: new ec2.CfnEIP(this, `WebServerNode${i}IP`).attrAllocationId,
                instanceId: computeNode.instanceId
            });
        }
    }

    // Creates an IAM role for EC2 instances
    private createEC2Role(id: string) {
        return new iam.Role(this, id, {
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
    }


    // Creates an OpenSearch Domain
    private createOpenSearchDomain() {
        // openSearch master password
        const openSearchPassword = new secretsmanager.Secret(this, 'BacalhauOpenSearchMasterPassword', {
            description: 'Initial password for the OpenSearch master user',
        });

        // Create OpenSearch instance
        const openSearch = new search.Domain(this, 'BacalhauOpenSearch', {
            version: search.EngineVersion.openSearch('2.9'),
            capacity: {
                dataNodeInstanceType: this.props.openSearchInstanceType,
            },
            ebs: {
                volumeSize: 100,
            },
            removalPolicy: cdk.RemovalPolicy.DESTROY, // For dev/test only
            useUnsignedBasicAuth: true, // For dev/test only
            fineGrainedAccessControl: {
                masterUserName: 'admin',
                masterUserPassword: openSearchPassword.secretValue,
            },
        });

        // Allow compute instances to access OpenSearch
        openSearch.grantWrite(this.computeRole)


        // Define Lambda function to initialize OpenSearch dashboard, index patterns, and visualizations
        const openSearchInitFunc = new lambda.Function(this, 'OpenSearchInit', {
            runtime: lambda.Runtime.PYTHON_3_9,
            code: lambda.Code.fromAsset('lambda/dashboard-init', {
                bundling: {
                    image: lambda.Runtime.PYTHON_3_9.bundlingImage,
                    command: [
                        'bash',
                        '-c',
                        'pip install -r requirements.txt -t /asset-output && cp -au . /asset-output',
                    ],
                },
            }),
            handler: 'handler.lambda_handler',
            environment: {
                OPENSEARCH_ENDPOINT: 'https://' + openSearch.domainEndpoint,
                SECRET_ARN: openSearchPassword.secretArn,
                COMPUTE_ROLE_ARN: this.computeRole.roleArn,
            },
            timeout: cdk.Duration.seconds(300),
            initialPolicy: [
                new iam.PolicyStatement({
                    actions: ['secretsmanager:GetSecretValue'],
                    resources: [openSearchPassword.secretArn],
                }),
            ],
        });

        const openSearchInitResourceProvider = new custom.Provider(this, 'OpenSearchInitResourceProvider', {
            onEventHandler: openSearchInitFunc,
            logRetention: logs.RetentionDays.ONE_DAY,
        });

        new cdk.CustomResource(this, "OpenSearchInitResource", {
            serviceToken: openSearchInitResourceProvider.serviceToken,
            resourceType: "Custom::OpenSearchInitResource",
        });

        // Output the OpenSearch endpoint
        new cdk.CfnOutput(this, 'OpenSearchEndpoint', {
            value: `https://${openSearch.domainEndpoint}:443`,
            description: 'The endpoint of the OpenSearch domain.',
        });

        // Output the OpenSearch dashboard URL
        new cdk.CfnOutput(this, 'OpenSearchDashboard', {
            value: `https://${openSearch.domainEndpoint}/_dashboards`,
            description: 'The URL of the OpenSearch dashboard.',
        });

        // Output the OpenSearch master password
        new cdk.CfnOutput(this, 'OpenSearchPasswordRetriever', {
            value: `aws secretsmanager get-secret-value --secret-id "${openSearchPassword.secretArn}" --query 'SecretString' --output text`,
            description: 'Run this command to get the OpenSearch master password.',
        });
    }


    // Creates an S3 bucket for raw access logs
    private createS3Bucket() {
        // Create S3 bucket
        const bucket = new s3.Bucket(this, 'Bucket', {
            removalPolicy: cdk.RemovalPolicy.DESTROY,  // For dev/test only
            autoDeleteObjects: true,
        });

        // Allow compute instances to access S3 bucket
        this.computeRole.addToPolicy(new iam.PolicyStatement({
            actions: ['s3:PutObject'],
            resources: [bucket.bucketArn, bucket.arnForObjects('*')],
        }))

        // Output the bucket name
        new cdk.CfnOutput(this, 'BucketName', {
            value: bucket.bucketName,
            description: 'The name of the S3 bucket.',
        });
    }

    private generateOrchestratorUserData(baseScript: string, volumeId: string): ec2.UserData {
        return ec2.UserData.custom(`#!/bin/bash
export BACALHAU_VERSION='${this.props.bacalhauVersion}'
export TARGET_PLATFORM='${this.props.targetPlatform}'
export VOLUME_ID='${volumeId}'
${baseScript}
`);
    }

    private generateComputeUserData(baseScript: string, volumeId: string, orchestratorIp: string, i: number): ec2.UserData {
        return ec2.UserData.custom(`#!/bin/bash
export BACALHAU_VERSION='${this.props.bacalhauVersion}'
export TARGET_PLATFORM='${this.props.targetPlatform}'
export VOLUME_ID='${volumeId}'
export BACALHAU_ORCHESTRATOR_IP='${orchestratorIp}'
export BACALHAU_LABELS='service=web-server,name=web-server-${i}'
${baseScript}
`);
    }
}

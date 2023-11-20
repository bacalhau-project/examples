#!/usr/bin/env node
import * as cdk from 'aws-cdk-lib';
import {BacalhauStack} from '../lib/bacalhau-stack';

const app = new cdk.App();
const keyName = app.node.tryGetContext('keyName');
const bacalhauVersion = app.node.tryGetContext('bacalhauVersion') || 'v1.1.4';
const targetPlatform = app.node.tryGetContext('targetPlatform') || 'linux_amd64';
const orchestratorInstanceType = app.node.tryGetContext('orchestratorInstanceType') || 't3.micro';
const webServiceInstanceType = app.node.tryGetContext('webServiceInstanceType') || 't3.large';
const webServiceInstanceCount = app.node.tryGetContext('webServiceInstanceCount') || 3;
const computeServiceInstanceType = app.node.tryGetContext('computeServiceInstanceType') || 't3.large';
const computeServiceInstanceCount = app.node.tryGetContext('computeServiceInstanceCount') || 0;
const openSearchInstanceType = app.node.tryGetContext('openSearchInstanceType') || 't3.small.search';

new BacalhauStack(app, 'BacalhauLogOrchestration', {
    env: {account: process.env.CDK_DEFAULT_ACCOUNT, region: process.env.CDK_DEFAULT_REGION},
    bacalhauVersion: bacalhauVersion,
    targetPlatform: targetPlatform,
    orchestratorInstanceType: orchestratorInstanceType,
    webServiceInstanceType: webServiceInstanceType,
    webServiceInstanceCount: webServiceInstanceCount,
    computeServiceInstanceType: computeServiceInstanceType,
    computeServiceInstanceCount: computeServiceInstanceCount,
    openSearchInstanceType: openSearchInstanceType,
    keyName: keyName,
});
#!/usr/bin/env node
import * as cdk from 'aws-cdk-lib';
import {BacalhauStack} from '../lib/bacalhau-stack';

const app = new cdk.App();
const keyName = app.node.tryGetContext('keyName');
const bacalhauVersion = app.node.tryGetContext('bacalhauVersion') || 'v1.1.3';
const targetPlatform = app.node.tryGetContext('targetPlatform') || 'linux_amd64';
const orchestratorInstanceType = app.node.tryGetContext('orchestratorInstanceType') || 't3.micro';
const webServerInstanceType = app.node.tryGetContext('webServerInstanceType') || 't3.large';
const webServerInstanceCount = app.node.tryGetContext('webServerInstanceCount') || 3;
const openSearchInstanceType = app.node.tryGetContext('openSearchInstanceType') || 't3.small.search';

new BacalhauStack(app, 'BacalhauLogOrchestration', {
    env: {account: process.env.CDK_DEFAULT_ACCOUNT, region: process.env.CDK_DEFAULT_REGION},
    bacalhauVersion: bacalhauVersion,
    targetPlatform: targetPlatform,
    orchestratorInstanceType: orchestratorInstanceType,
    webServerInstanceType: webServerInstanceType,
    webServerInstanceCount: webServerInstanceCount,
    openSearchInstanceType: openSearchInstanceType,
    keyName: keyName,
});
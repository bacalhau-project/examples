#!/usr/bin/env node
import * as cdk from 'aws-cdk-lib';
import { BacalhauStack } from '../lib/bacalhau-stack';

const app = new cdk.App();
const keyName = app.node.tryGetContext('keyName') || 'bacalhau-keypair';

new BacalhauStack(app, 'BacalhauLogVending', {
  env: { account: process.env.CDK_DEFAULT_ACCOUNT, region: process.env.CDK_DEFAULT_REGION },
  keyName: keyName,
});
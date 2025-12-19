[![Deploy Lambda and S3](https://github.com/siliconshells/AWS_ETL/actions/workflows/deploy.yml/badge.svg)](https://github.com/siliconshells/AWS_ETL/actions/workflows/deploy.yml)

## AWS Extract Transform and Load eCFR API data
This is a challenge from MedLaunch Concepts.

This repository contains code to deploy an AWS Lambda function that extracts data from the eCFR API, processes it using Amazon Bedrock, and stores the results in an S3 bucket. The deployment is automated using Terraform and GitHub Actions.

### How to use it
1. Clone this repository.
2. Create an IAM user in your AWS account with programmatic access. You should use the Principle of Least Privilege, but for the sake of testing, please ensure you give the following permissions to the user on which you create the access key:
- AmazonBedrockFullAccess
- AmazonS3FullAccess
- AWSLambda_FullAccess
- IAMFullAccess

3. Generate an access key for the IAM user.
4. Set the following secrets under Repository Secrets:
- AWS_ACCESS_KEY_ID
- AWS_SECRET_ACCESS_KEY

5. Push the code to GitHub and that's it, the AWS resources will be created and the Lambda function invoked.


### Other information
1. During CI/CD, the following resources will be created
- Lambda function - medlaunch-regulations-processor
- S3 bucket - medlaunch-regulations-data
- IAM role and policies for Lambda function

2. AWS resources
- Lambda
- Bedrock
- S3 Bucket

3. Deployment tools
- Terraform
- GitHub Actions
- AWS CLI
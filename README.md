# AWS Lambda Python Data Science Cold Start Evaluation

Comparing cold starts for packaging methods and Python versions.

## Rationale

Lambda ZIP packaging limits (250 MB, including all layers) presents a common challenge for Python data science workloads. Here is an example of the typical installation sizes for these modules:

|**Library** |**Size** | 
|-- |-- |
|`numpy` | 34M |
|`numpy.libs` | 34M |
|`pandas` | 61M |
|`botocore` | 82M |
|`pyarrow` | 125M |

This gives a total of 332M before any other libraries are added.

Common workarounds to this are:
1. Using container image packaging, providing a much more liberal package size of 10MB
2. Stripping non-essential parts of packages before deployment. This includes stripping debug symbols from shared libraries (`.so`), removing unit tests and documentation, and removing the `.pyc` precompiled bytecode
3. Using Lambda Layers for these dependencies. Layers still count towards the restrictive 250MB limit, but layer providers can handle the stripping and minimisation of packages so you don't have to.

Common concerns about these approaches include assumptions about the releative cold start overhead of each one. The CDK project in this repository is designed to compare this for each approach using a realistic workload.

## Pros and Cons of various packaging approach

|**Method** |**Pros** |**Cons** |
|-- |-- |-- |
|**ZIP** | ⬆️ Use native runtime dependency bundling |⬇️ 250MB limit |
| |⬆️ Packaging and deployment can be slower | ⬇️ ZIP archive is not optimised for fast rebuild when a subset has changed |
| | | |
|**ZIP with Layers** |⬆️ Packaging optimisation handled by layer provider | ⬇️ 250MB limit |
| |⬆️ Deployment faster when dependencies are unchanged | ⬇️ No semantic versioning |
| | | ⬇️ Less control over dependency versions |
| | | ⬇️ Reliant on provider to continue maintenance |
| | |
|**Container Image** |⬆️ 10 GB limit | ⬇️ Runtime security and maintenance is your responsibility |
| |⬆️ Easier if you have existing container infrastructure  | ⬇️ Added complexity of container repository |
| |⬆️ Mature container ecosystem and tooling |
| | | ⬇️ _Perceived additional cold start_ ❓ Let's validate this assumption!|

## What this project provides
This stack deploys a matrix of Lambda Functions with a simulated Data Science workload, including common dependencies:
 - PyArrow
 - Pandas
 - Numpy
 - AWS Lambda Powertools
 - X-Ray SDK

Three different packaging methods are evaluated:

 1. Zip packaging with `pip` package bundling
 2. Zip packaging with layers for heavy dependencies:
    1. [aws-sdk-pandas](https://aws-sdk-pandas.readthedocs.io/en/3.4.1/install.html#aws-lambda-layer) layer for `pandas`, `pyarrow`, `numpy` 
    2. [aws-lambda-powertools](https://docs.powertools.aws.dev/lambda/python/latest/#install) layer, providing Powertools for AWS Lambda (Python)
 3. Docker/OCI Container image packaging

## Installation

```bash
npm install
cdk deploy
```

## Running a test

The stack deploys multiple Lambda functions, all of which are triggered by a single SQS queue. A script is provided to send messages in bulk to this queue. Invoke with:

```bash
./scripts/send-messages.py <NUMBER_OF_MESSAGES>
```

For example:
```bash
./scripts/send-messages.py 10000
```

## Monitoring results
This stack provides a CloudWatch dashboard for monitoring execution duration, invocations and cold starts.





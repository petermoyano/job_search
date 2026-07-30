# Production Deployment

## AWS Resources

- Region: `sa-east-1`
- ECR repository: `job-search-api`
- ECS cluster: `default`
- ECS service: `job-search-api`
- ECS task definition family: `default-job-search-api`
- Container name: `Main`
- Public API:
  `https://jo-4d640afb7d8a498ba98b7048af302d6c.ecs.sa-east-1.on.aws`
- CloudWatch log group: `/aws/ecs/default/job-search-api-c8bf`

`TAVILY_API_KEY` remains in AWS Secrets Manager. The task definition stores only
the secret ARN, never the secret value.

## Automatic Deployments

`.github/workflows/deploy.yml` runs for every push to `main`:

1. Install the frozen dependency set from `uv.lock`.
2. Run Ruff and Pytest.
3. Obtain temporary AWS credentials through GitHub OIDC.
4. Build the Docker image and tag it with the full Git commit SHA.
5. Push the immutable image to ECR.
6. Render and register a new ECS task definition revision.
7. Deploy the revision to the existing ECS service and wait for stability.
8. Verify the production health endpoint and frontend CORS preflight.

The workflow can also be started manually from GitHub's Actions tab with
`workflow_dispatch`. Production deployments are serialized so two ECS
deployments cannot run concurrently.

The IAM role is `job-search-github-deploy`. Its trust and permissions policies
are stored under `deploy/iam/` for review and reproducibility. The trust policy
allows only the `production` GitHub environment in
`petermoyano/job_search` to obtain temporary credentials.

The source-controlled ECS task definition is
`deploy/ecs-task-definition.json`. Changes to environment variables, CPU,
memory, logging, or secret references should be committed there instead of
being edited only in the AWS console.

## Monitoring Deployments

Use GitHub's **Actions** tab to inspect tests, the Docker build, and AWS
deployment logs.

In AWS, open **Amazon ECS**, select region `sa-east-1`, then navigate to:

`Clusters` -> `default` -> `Services` -> `job-search-api` -> `Deployments`

That page shows the new task-definition revision, canary traffic shift,
circuit-breaker status, rollback status, and final deployment result.

Use **Amazon ECR** -> `job-search-api` -> `Images` to match the deployed image
tag to a Git commit SHA. Runtime application logs are under **CloudWatch Logs**
in `/aws/ecs/default/job-search-api-c8bf`.

## Rollback

ECS already has its deployment circuit breaker and automatic rollback enabled.
Each deployment uses a unique Git SHA image tag, so a previous version can also
be restored by deploying an earlier task-definition revision or image tag.

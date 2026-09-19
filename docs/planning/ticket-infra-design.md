## Question

How should the AWS CDK infrastructure (ECS Fargate, RDS Postgres, VPC) be structured based on the `aws-cdk` skill to avoid the "deadly embrace" and ensure clean, isolated deployments for our backend and workers?

**Labels**: `wayfinder:research`, `closed`

## Resolution

Based on the `aws-cdk` skill guidelines, we should structure our infrastructure using separate L2-based stacks based on their statefulness and lifecycle. This ensures clean, isolated deployments and avoids cross-stack reference deadlocks (the "deadly embrace").

### 1. Stack Separation (Lifecycle-based)
Break the infrastructure into three distinct stacks to enforce a one-way dependency flow:
*   **`NetworkStack`**: Contains the foundational L2 `ec2.Vpc` and associated subnets/NAT gateways.
*   **`DatabaseStack`**: Contains stateful resources like the L2 `rds.DatabaseInstance` or `rds.DatabaseCluster` (Postgres). 
*   **`ComputeStack`** (or `AppStack`): Contains stateless compute such as `ecs.Cluster`, `ecs.FargateTaskDefinition`, and `ecs.FargateService` for both the backend and Celery workers. 

**Dependency Flow**: `ComputeStack` -> `DatabaseStack` -> `NetworkStack`. This ensures that stateless compute can be rapidly torn down or refactored without threatening the stateful database or network.

### 2. Avoiding the "Deadly Embrace"
A deadly embrace occurs when Stack A exports a value that Stack B imports via strong references (`Fn::ImportValue`), locking the resources.
*   **Weak References**: Set your application to default to weak references for cross-stack wiring by adding `{ "context": { "@aws-cdk/core:defaultCrossStackReferences": "weak" } }` in `cdk.json`.
*   **SSM Parameter Store**: For decoupled lookups, use SSM Parameter Store to pass resource ARNs or endpoints (e.g., RDS endpoint) between stacks. This entirely breaks hard CloudFormation coupling.
*   **IAM Grants**: Always use L2 `grant*()` methods (e.g., `db.secret.grantRead(fargateTaskRole)`) to automatically manage permission boundaries without manual policy writing.

### 3. L2 Construct Structure Details
*   **VPC**: Use `new ec2.Vpc(this, 'Vpc', {...})`.
*   **RDS**: Use `new rds.DatabaseInstance(...)` with `removalPolicy: cdk.RemovalPolicy.RETAIN` for production to prevent accidental data loss.
*   **ECS Fargate**: Use `new ecs.Cluster(...)` and `new ecs_patterns.ApplicationLoadBalancedFargateService(...)` or base `ecs.FargateService(...)` for the workers.

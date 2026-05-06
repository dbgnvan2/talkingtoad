# Docker Container Security Best Practices

Docker containers are now used in 85% of organizations (Gartner, 2023). Security is critical when running containerized applications in production.

## Scanning Images for Vulnerabilities

Use tools like Trivy or Snyk to scan your images:

```bash
trivy image myapp:latest
snyk container test myapp:latest
```

These tools automatically detect known vulnerabilities in dependencies. Perform scans during CI/CD pipeline execution.

## Running as Non-Root User

Containers should run as unprivileged users. The root user inside a container can access all host resources if the container is compromised.

Create a non-root user in your Dockerfile:

```dockerfile
RUN useradd -m appuser
USER appuser
```

This is a critical security control.

## Environment Variables vs Secrets

Never store secrets like API keys or database passwords in environment variables. Use secret management tools:
- Kubernetes Secrets (for Kubernetes deployments)
- AWS Secrets Manager
- HashiCorp Vault

Environment variables are visible in running process listings and logs. Secrets managers provide encrypted storage and audit logging.

## Resource Limits

Set memory and CPU limits to prevent resource exhaustion attacks. In docker-compose:

```yaml
services:
  app:
    image: myapp:latest
    mem_limit: 512m
    cpus: 0.5
```

## Image Scanning Should Happen

Regular image scanning is important. New vulnerabilities are discovered continuously. Most organizations scan weekly or on every build.

Network isolation and firewall rules also matter for security.

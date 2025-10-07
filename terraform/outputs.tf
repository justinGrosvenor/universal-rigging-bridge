output "repository_url" {
  description = "ECR repository URL"
  value       = aws_ecr_repository.service.repository_url
}

output "load_balancer_dns" {
  description = "Public DNS name of the application load balancer"
  value       = aws_lb.this.dns_name
}

output "cluster_id" {
  description = "ECS cluster ID"
  value       = aws_ecs_cluster.this.id
}

output "service_name" {
  description = "ECS service name"
  value       = aws_ecs_service.this.name
}
output "artifact_bucket" {
  description = "S3 bucket for rig artifacts"
  value       = aws_s3_bucket.artifacts.bucket
}


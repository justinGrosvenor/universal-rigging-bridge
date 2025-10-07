variable "project_name" {
  description = "Name prefix for all infrastructure resources"
  type        = string
  default     = "rig-transformer"
}

variable "aws_region" {
  description = "AWS region to deploy into"
  type        = string
  default     = "us-east-1"
}

variable "container_image" {
  description = "ECR image URI (including tag) to deploy. Defaults to the repository created in this stack with the :latest tag."
  type        = string
  default     = null
}

variable "container_port" {
  description = "Port exposed by the application container"
  type        = number
  default     = 8000
}

variable "desired_count" {
  description = "Number of tasks to run in the ECS service"
  type        = number
  default     = 1
}

variable "cpu" {
  description = "Task CPU units for Fargate"
  type        = number
  default     = 1024
}

variable "memory" {
  description = "Task memory (MB) for Fargate"
  type        = number
  default     = 2048
}

variable "load_balancer_cidrs" {
  description = "List of CIDR blocks allowed to reach the public load balancer"
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "tags" {
  description = "Common tags to apply to all resources"
  type        = map(string)
  default     = {}
}

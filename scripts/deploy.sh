#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd "${SCRIPT_DIR}/.." && pwd)

IMAGE_NAME=${IMAGE_NAME:-rig-transformer}
IMAGE_TAG=${IMAGE_TAG:-$(cd "${REPO_ROOT}" && git rev-parse --short HEAD)}
AWS_REGION=${AWS_REGION:-us-east-1}
TF_VARS_FILE=${TF_VARS_FILE:-}

cd "${REPO_ROOT}"

docker build -t "${IMAGE_NAME}:${IMAGE_TAG}" .

pushd terraform >/dev/null
terraform init -input=false

if [[ -n "${TF_VARS_FILE}" && -f "${TF_VARS_FILE}" ]]; then
  TF_VARS_ARG=(-var-file "${TF_VARS_FILE}")
else
  TF_VARS_ARG=()
fi

terraform apply -auto-approve -target=aws_ecr_repository.service "${TF_VARS_ARG[@]}"

REPO_URL=$(terraform output -raw repository_url)

aws ecr get-login-password --region "${AWS_REGION}" \
  | docker login --username AWS --password-stdin "${REPO_URL}"

docker tag "${IMAGE_NAME}:${IMAGE_TAG}" "${REPO_URL}:${IMAGE_TAG}"
docker push "${REPO_URL}:${IMAGE_TAG}"

export TF_VAR_container_image="${REPO_URL}:${IMAGE_TAG}"

terraform apply -auto-approve "${TF_VARS_ARG[@]}"

terraform output
popd >/dev/null

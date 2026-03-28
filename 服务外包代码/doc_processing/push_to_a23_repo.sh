#!/usr/bin/env bash
set -euo pipefail

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_REPO_URL="${TARGET_REPO_URL:-https://github.com/ZhuoGLx/A23_DocumentUnderstandingSystem.git}"
TARGET_BRANCH="${TARGET_BRANCH:-master}"
TARGET_SUBDIR="${TARGET_SUBDIR:-Code/doc_processing}"
COMMIT_MESSAGE="${COMMIT_MESSAGE:-feat: update doc_processing}"
WORK_ROOT="${WORK_ROOT:-$(mktemp -d /tmp/a23-doc-processing.XXXXXX)}"
CLONE_DIR="${WORK_ROOT}/repo"
TOKEN="${GH_TOKEN:-${GITHUB_TOKEN:-}}"

if [[ -z "${TOKEN}" ]]; then
  echo "缺少 GitHub Token。请先执行: export GH_TOKEN=你的PAT" >&2
  exit 1
fi

if ! command -v git >/dev/null 2>&1; then
  echo "未找到 git，请先安装 git。" >&2
  exit 1
fi

if ! command -v rsync >/dev/null 2>&1; then
  echo "未找到 rsync，请先安装 rsync。" >&2
  exit 1
fi

AUTH_HEADER="AUTHORIZATION: basic $(printf 'x-access-token:%s' "${TOKEN}" | base64 | tr -d '\n')"

echo "克隆目标仓库到临时目录: ${CLONE_DIR}"
git -c "http.https://github.com/.extraheader=${AUTH_HEADER}" \
  clone --branch "${TARGET_BRANCH}" --single-branch "${TARGET_REPO_URL}" "${CLONE_DIR}"

mkdir -p "${CLONE_DIR}/${TARGET_SUBDIR}"

echo "同步当前项目到 ${TARGET_SUBDIR}"
rsync -av --delete \
  --exclude '__pycache__/' \
  --exclude '*.py[cod]' \
  --exclude '.DS_Store' \
  --exclude 'outputs/' \
  --exclude '.git/' \
  "${SOURCE_DIR}/" \
  "${CLONE_DIR}/${TARGET_SUBDIR}/"

git -C "${CLONE_DIR}" add "${TARGET_SUBDIR}"

if git -C "${CLONE_DIR}" diff --cached --quiet; then
  echo "目标仓库中没有检测到新的代码变更，无需提交。"
  echo "临时目录保留在: ${WORK_ROOT}"
  exit 0
fi

git -C "${CLONE_DIR}" commit -m "${COMMIT_MESSAGE}"

echo "推送到 origin/${TARGET_BRANCH}"
git -C "${CLONE_DIR}" -c "http.https://github.com/.extraheader=${AUTH_HEADER}" \
  push origin "${TARGET_BRANCH}"

echo "完成。临时目录保留在: ${WORK_ROOT}"

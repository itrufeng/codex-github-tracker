#!/usr/bin/env bash
set -euo pipefail

PACKAGE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MANAGED_MARKER=".feature-workflow-managed"
MANAGED_DIRS=("feature-create" "feature-continue" "feature-done" "_feature-workflow")

usage() {
  cat <<'EOF'
用法：
  ./install.sh install [--global | --project PATH]
  ./install.sh uninstall [--global | --project PATH] [--repo PATH ...]

安装目标：
  --global           安装到 $HOME/.agents/skills（默认）。
  --project PATH     解析 PATH 的 Git 根目录，并使用 <repo>/.agents/skills。

卸载数据清理：
  --repo PATH        同时删除 PATH/.codex/feature-workflow.json 和 Git 本地待处理
                     功能状态。需要删除用户配置的每个仓库都可以重复指定一次。
EOF
}

fail() {
  printf '错误：%s\n' "$*" >&2
  exit 1
}

[[ $# -ge 1 ]] || { usage; exit 2; }
ACTION="$1"
shift
[[ "$ACTION" == "install" || "$ACTION" == "uninstall" ]] || fail "第一个参数必须是 install 或 uninstall"

SKILLS_DIR=""
PROJECT_ROOT=""
TARGET_MODE=""
REPOS=()
REPO_COUNT=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --global)
      [[ -z "$TARGET_MODE" ]] || fail "--global 和 --project 只能选择一个"
      TARGET_MODE="global"
      SKILLS_DIR="$HOME/.agents/skills"
      shift
      ;;
    --project)
      [[ -z "$TARGET_MODE" ]] || fail "--global 和 --project 只能选择一个"
      [[ $# -ge 2 && -n "$2" ]] || fail "--project 需要路径"
      [[ -d "$2" ]] || fail "项目路径不存在：$2"
      PROJECT_ROOT="$(git -C "$2" rev-parse --show-toplevel 2>/dev/null)" || fail "不是 Git 仓库：$2"
      TARGET_MODE="project"
      SKILLS_DIR="$PROJECT_ROOT/.agents/skills"
      shift 2
      ;;
    --codex-dir)
      fail "--codex-dir 已由 --project 取代；请直接传入项目路径"
      ;;
    --repo)
      [[ "$ACTION" == "uninstall" ]] || fail "--repo 只能与 uninstall 一起使用"
      [[ $# -ge 2 && -n "$2" ]] || fail "--repo 需要路径"
      REPOS[$REPO_COUNT]="$2"
      REPO_COUNT=$((REPO_COUNT + 1))
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      fail "未知参数：$1"
      ;;
  esac
done

if [[ -z "$SKILLS_DIR" ]]; then
  TARGET_MODE="global"
  SKILLS_DIR="$HOME/.agents/skills"
fi
[[ -n "$SKILLS_DIR" && "$SKILLS_DIR" != "/" ]] || fail "技能目录不安全"

if [[ "$ACTION" == "install" ]]; then
  mkdir -p "$SKILLS_DIR"
  SKILLS_DIR="$(cd "$SKILLS_DIR" && pwd)"
else
  if [[ -d "$SKILLS_DIR" ]]; then
    SKILLS_DIR="$(cd "$SKILLS_DIR" && pwd)"
  fi
fi

if [[ "$ACTION" == "uninstall" && "$TARGET_MODE" == "project" ]]; then
  REPOS[$REPO_COUNT]="$PROJECT_ROOT"
  REPO_COUNT=$((REPO_COUNT + 1))
fi

is_managed_name() {
  local candidate="$1" name
  for name in "${MANAGED_DIRS[@]}"; do
    [[ "$candidate" == "$name" ]] && return 0
  done
  return 1
}

safe_remove_managed_dir() {
  local target="$1" name parent
  name="$(basename "$target")"
  parent="$(dirname "$target")"
  is_managed_name "$name" || fail "拒绝删除不受管理的目录名：$target"
  [[ "$parent" == "$SKILLS_DIR" ]] || fail "拒绝删除所选技能目录之外的目录：$target"
  [[ ! -L "$target" ]] || fail "拒绝删除符号链接：$target"
  [[ -f "$target/$MANAGED_MARKER" ]] || fail "拒绝删除没有管理标记的目录：$target"
  rm -rf -- "$target"
}

install_skills() {
  local name source target stage
  for name in "${MANAGED_DIRS[@]}"; do
    source="$PACKAGE_DIR/$name"
    target="$SKILLS_DIR/$name"
    [[ -d "$source" ]] || fail "套件目录缺失：$source"
    if [[ -e "$target" || -L "$target" ]]; then
      [[ ! -L "$target" ]] || fail "目标是符号链接：$target"
      [[ -f "$target/$MANAGED_MARKER" ]] || fail "目标已存在，但不受本安装器管理：$target"
    fi
  done
  for name in "${MANAGED_DIRS[@]}"; do
    source="$PACKAGE_DIR/$name"
    target="$SKILLS_DIR/$name"
    stage="$(mktemp -d "$SKILLS_DIR/.feature-workflow-install.XXXXXX")"
    cp -R "$source/." "$stage/"
    touch "$stage/$MANAGED_MARKER"
    if [[ -e "$target" ]]; then
      safe_remove_managed_dir "$target"
    fi
    mv "$stage" "$target"
  done
  printf '功能开发工作流技能已安装到：%s\n' "$SKILLS_DIR"
}

purge_repo_data() {
  local requested="$1" repo_root git_dir config state continue_state
  [[ -d "$requested" ]] || fail "仓库路径不存在：$requested"
  repo_root="$(git -C "$requested" rev-parse --show-toplevel 2>/dev/null)" || fail "不是 Git 仓库：$requested"
  git_dir="$(git -C "$repo_root" rev-parse --absolute-git-dir)"
  config="$repo_root/.codex/feature-workflow.json"
  state="$git_dir/codex-feature-create.json"
  continue_state="$git_dir/codex-feature-continue.json"
  if [[ -f "$config" ]]; then
    rm -f -- "$config"
    rmdir "$repo_root/.codex" 2>/dev/null || true
    printf '已删除仓库配置：%s\n' "$config"
  fi
  if [[ -f "$state" ]]; then
    rm -f -- "$state"
    printf '已删除待处理的功能状态：%s\n' "$state"
  fi
  if [[ -f "$continue_state" ]]; then
    rm -f -- "$continue_state"
    printf '已删除待处理的继续开发状态：%s\n' "$continue_state"
  fi
}

uninstall_skills() {
  local name target repo index
  if [[ -d "$SKILLS_DIR" ]]; then
    for name in "${MANAGED_DIRS[@]}"; do
      target="$SKILLS_DIR/$name"
      if [[ -e "$target" || -L "$target" ]]; then
        safe_remove_managed_dir "$target"
        printf '已移除：%s\n' "$target"
      fi
    done
  fi
  index=0
  while [[ $index -lt $REPO_COUNT ]]; do
    repo="${REPOS[$index]}"
    purge_repo_data "$repo"
    index=$((index + 1))
  done
  if [[ $REPO_COUNT -eq 0 ]]; then
    printf '未提供 --repo 路径；没有删除仓库本地配置。\n'
  fi
  printf '卸载完成。\n'
}

if [[ "$ACTION" == "install" ]]; then
  install_skills
else
  uninstall_skills
fi

#!/usr/bin/env python3
"""为功能开发技能提供确定性的 GitHub 议题和项目工作流。"""

from __future__ import annotations

import argparse
import hashlib
import json
import secrets
import shutil
import subprocess
import sys
import unicodedata
from pathlib import Path


class WorkflowError(RuntimeError):
    pass


def run(*args: str) -> str:
    result = subprocess.run(args, text=True, capture_output=True)
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip() or "命令执行失败"
        raise WorkflowError(f"{' '.join(args[:3])}: {detail}")
    return result.stdout.strip()


def run_json(*args: str):
    output = run(*args)
    try:
        return json.loads(output)
    except json.JSONDecodeError as exc:
        raise WorkflowError(f"{' '.join(args[:3])} 返回了无效 JSON") from exc


def linked_projects(gh: str, repo: str) -> tuple[str, list[dict]]:
    repo_owner, repo_name = repo.split("/", 1)
    query = """query($owner:String!,$name:String!,$after:String){viewer{login} repository(owner:$owner,name:$name){projectsV2(first:100,after:$after){nodes{id number title url closed owner{... on User{login} ... on Organization{login}}} pageInfo{hasNextPage endCursor}}}}"""
    projects: list[dict] = []
    viewer = ""
    cursor = None
    while True:
        command = [gh, "api", "graphql", "-f", f"query={query}", "-f", f"owner={repo_owner}", "-f", f"name={repo_name}"]
        if cursor is not None:
            command.extend(["-f", f"after={cursor}"])
        data = run_json(*command)["data"]
        viewer = data["viewer"]["login"]
        connection = data["repository"]["projectsV2"]
        projects.extend(connection["nodes"])
        page = connection["pageInfo"]
        if not page["hasNextPage"]:
            break
        cursor = page["endCursor"]
    return viewer, projects


def project_candidates(projects: list[dict]) -> str:
    return "; ".join(
        f"{item.get('owner', {}).get('login', '?')}/#{item.get('number')} {item.get('title')!r}"
        for item in projects
    ) or "无"


def resolve_project(gh: str, repo: str, config: dict) -> tuple[str, int]:
    if "project_owner" in config:
        raise WorkflowError("project_owner 不可配置；本工作流始终使用 @me，请删除该配置")
    configured = config.get("project_number")
    if configured is not None and (not isinstance(configured, int) or configured < 1):
        raise WorkflowError("project_number 必须是正整数")
    viewer, projects = linked_projects(gh, repo)
    personal = [item for item in projects if item.get("owner", {}).get("login") == viewer]
    if configured is not None:
        matches = [item for item in personal if item.get("number") == configured]
        if len(matches) != 1:
            raise WorkflowError(
                f"project_number {configured} 没有精确对应一个已关联 {repo} 且由 {viewer} 拥有的项目；"
                f"关联候选项：{project_candidates(projects)}"
            )
        selected = matches[0]
    else:
        open_projects = [item for item in personal if not item.get("closed")]
        if len(open_projects) != 1:
            reason = "没有" if not open_projects else "存在多个"
            raise WorkflowError(
                f"{repo} 关联的、由 @me 拥有且仍开放的项目{reason}；"
                f"关联候选项：{project_candidates(projects)}。"
                "关联多个个人项目时，请在 .codex/feature-workflow.json 中设置 project_number"
            )
        selected = open_projects[0]
    if selected.get("closed"):
        raise WorkflowError(f"所选项目 #{selected['number']} 已关闭")
    return "@me", selected["number"]


def context():
    if not shutil.which("git"):
        raise WorkflowError("PATH 中找不到 git")
    gh = shutil.which("gh")
    if not gh:
        raise WorkflowError("PATH 中找不到 gh CLI")
    root = Path(run("git", "rev-parse", "--show-toplevel"))
    git_dir = Path(run("git", "rev-parse", "--absolute-git-dir"))
    run(gh, "auth", "status")
    repo = run_json(gh, "repo", "view", "--json", "nameWithOwner")["nameWithOwner"]
    config_path = root / ".codex" / "feature-workflow.json"
    config = {}
    if config_path.is_file():
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise WorkflowError(f"配置文件无效：{config_path}") from exc
        if not isinstance(config, dict):
            raise WorkflowError(f"配置必须是 JSON 对象：{config_path}")
    owner, number = resolve_project(gh, repo, config)
    names = {
        "field": config.get("status_field", "Status"),
        "ready": config.get("ready_status", "Ready"),
        "progress": config.get("in_progress_status", "In progress"),
        "review": config.get("in_review_status", "In review"),
        "done": config.get("done_status", "Done"),
    }
    if not all(isinstance(value, str) and value for value in names.values()):
        raise WorkflowError("状态字段名和状态名称必须是非空字符串")
    return gh, root, git_dir, repo, owner, number, names


def issue_for_state(gh: str, repo: str, owner: str, number: int, state: dict) -> dict:
    if state.get("repo") != repo or state.get("project_owner") != owner or state.get("project_number") != number:
        raise WorkflowError("待处理的议题状态不属于当前仓库或项目")
    return run_json(gh, "issue", "view", str(state["issue_number"]), "--repo", repo, "--json", "number,title,url,state")


def ensure_issue_open(gh: str, repo: str, issue: dict) -> None:
    if issue.get("state") == "OPEN":
        return
    run(gh, "issue", "reopen", str(issue["number"]), "--repo", repo)
    issue["state"] = "OPEN"


def ensure_issue_closed(gh: str, repo: str, issue: dict) -> None:
    if issue.get("state") == "CLOSED":
        return
    run(gh, "issue", "close", str(issue["number"]), "--repo", repo, "--reason", "completed")
    issue["state"] = "CLOSED"


def project_metadata(gh: str, owner: str, number: int, field_name: str):
    project = run_json(gh, "project", "view", str(number), "--owner", owner, "--format", "json")
    fields_data = run_json(gh, "project", "field-list", str(number), "--owner", owner, "--limit", "100", "--format", "json")
    fields = fields_data.get("fields", []) if isinstance(fields_data, dict) else fields_data
    matches = [field for field in fields if field.get("name") == field_name]
    if len(matches) != 1:
        raise WorkflowError(f"项目必须恰好包含一个名为 {field_name!r} 的字段")
    return project["id"], matches[0]


def find_project_item(gh: str, owner: str, number: int, issue_url: str) -> dict | None:
    data = run_json(gh, "project", "item-list", str(number), "--owner", owner, "--limit", "1000", "--format", "json")
    items = data.get("items", []) if isinstance(data, dict) else data
    matches = [item for item in items if item.get("content", {}).get("url") == issue_url]
    if len(matches) > 1:
        raise WorkflowError(f"议题在项目 {owner}/{number} 中出现多次：{issue_url}")
    return matches[0] if matches else None


def project_item(gh: str, owner: str, number: int, issue_url: str) -> dict:
    item = find_project_item(gh, owner, number, issue_url)
    if item is None:
        raise WorkflowError(f"议题不在项目 {owner}/{number} 中：{issue_url}")
    return item


def add_project_item(gh: str, owner: str, number: int, issue_url: str) -> dict:
    item = run_json(
        gh,
        "project",
        "item-add",
        str(number),
        "--owner",
        owner,
        "--url",
        issue_url,
        "--format",
        "json",
    )
    if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not item["id"]:
        raise WorkflowError("gh project item-add 没有返回项目项标识符")
    return item


def ensure_project_item(gh: str, owner: str, number: int, issue_url: str) -> dict:
    return find_project_item(gh, owner, number, issue_url) or add_project_item(gh, owner, number, issue_url)


def current_single_select(gh: str, item_id: str, field_id: str) -> str | None:
    query = "query($id:ID!){node(id:$id){... on ProjectV2Item{fieldValues(first:100){nodes{... on ProjectV2ItemFieldSingleSelectValue{name field{... on ProjectV2SingleSelectField{id}}}}}}}}"
    data = run_json(gh, "api", "graphql", "-f", f"query={query}", "-f", f"id={item_id}")
    nodes = data["data"]["node"]["fieldValues"]["nodes"]
    values = [node.get("name") for node in nodes if node.get("field", {}).get("id") == field_id]
    if len(values) > 1:
        raise WorkflowError("项目项在所配置的状态字段中存在多个值")
    return values[0] if values else None


def project_status(gh: str, owner: str, number: int, item_id: str, field_name: str) -> str | None:
    _, field = project_metadata(gh, owner, number, field_name)
    return current_single_select(gh, item_id, field["id"])


def set_status(gh: str, owner: str, number: int, issue_url: str, names: dict, target: str, expected: str | None, item_id: str | None = None):
    project_id, field = project_metadata(gh, owner, number, names["field"])
    if item_id is None:
        item_id = project_item(gh, owner, number, issue_url)["id"]
    current = current_single_select(gh, item_id, field["id"])
    if current == target:
        return
    if expected is not None and current != expected:
        raise WorkflowError(f"预期项目状态为 {expected!r}，实际为 {current!r}")
    options = [option for option in field.get("options", []) if option.get("name") == target]
    if len(options) != 1:
        raise WorkflowError(f"状态字段必须恰好包含一个名为 {target!r} 的选项")
    run(gh, "project", "item-edit", "--id", item_id, "--project-id", project_id, "--field-id", field["id"], "--single-select-option-id", options[0]["id"])


def text_width(value: str) -> int:
    return sum(2 if unicodedata.east_asian_width(character) in {"W", "F"} else 1 for character in value)


def pad_text(value: str, width: int) -> str:
    return value + " " * (width - text_width(value))


def issue_table(issue: dict, status: str) -> str:
    rows = [("标题", issue["title"]), ("列名", status), ("地址", issue["url"])]
    label_width = max(text_width(label) for label, _ in rows)
    value_width = max(text_width(value) for _, value in rows)
    border = f"+{'-' * (label_width + 2)}+{'-' * (value_width + 2)}+"
    lines = [border]
    lines.extend(f"| {pad_text(label, label_width)} | {pad_text(value, value_width)} |" for label, value in rows)
    lines.append(border)
    return "\n".join(lines)


def state_path(git_dir: Path) -> Path:
    return git_dir / "codex-feature-create.json"


def continue_state_path(git_dir: Path) -> Path:
    return git_dir / "codex-feature-continue.json"


def load_state(git_dir: Path) -> dict:
    path = state_path(git_dir)
    if not path.is_file():
        raise WorkflowError("没有找到待处理的 feature-create 议题状态")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WorkflowError(f"待处理状态无效：{path}") from exc


def strip_invocation(value: str, invocation: str) -> str:
    candidate = value.lstrip()
    prefix = f"${invocation}"
    if candidate.startswith(prefix) and (len(candidate) == len(prefix) or candidate[len(prefix)].isspace()):
        return candidate[len(prefix):].lstrip()
    return value


def request_text(path_value: str, invocation: str) -> str:
    path = Path(path_value)
    if not path.is_file():
        raise WorkflowError("请求文件必须存在并包含完整请求")
    value = strip_invocation(path.read_text(encoding="utf-8"), invocation)
    if not value.strip():
        raise WorkflowError("请求文件必须存在并包含完整请求")
    return value


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def pending_issue(gh: str, repo: str, state: dict, request: str) -> dict:
    required = {
        "repo": str,
        "issue_number": int,
        "issue_url": str,
        "summary": str,
        "project_owner": str,
        "project_number": int,
    }
    for key, expected_type in required.items():
        if not isinstance(state.get(key), expected_type):
            raise WorkflowError(f"待处理的 feature-create 状态包含无效字段 {key!r}")
    issue = run_json(
        gh,
        "issue",
        "view",
        str(state["issue_number"]),
        "--repo",
        repo,
        "--json",
        "number,title,body,url,state,assignees",
    )
    if issue.get("number") != state["issue_number"] or issue.get("url") != state["issue_url"]:
        raise WorkflowError("待处理的议题编号或网址已与 GitHub 不一致")
    if issue.get("state") != "OPEN":
        raise WorkflowError("待处理的议题已不再开放")
    issue_body = issue.get("body", "")
    legacy_prefixed_body = issue_body != request and strip_invocation(issue_body, "feature-create") == request
    request_hash = sha256_text(request)
    stored_hash = state.get("request_sha256")
    if stored_hash is not None and stored_hash != request_hash and not legacy_prefixed_body:
        raise WorkflowError("待处理的 feature-create 属于其他请求")
    if issue_body != request and not legacy_prefixed_body:
        raise WorkflowError("待处理的议题正文与本次功能请求不完全一致")
    if legacy_prefixed_body:
        run(gh, "issue", "edit", str(state["issue_number"]), "--repo", repo, "--body", request)
    state["request_sha256"] = request_hash
    return issue


def ensure_self_assigned(gh: str, repo: str, issue: dict) -> str:
    viewer = run_json(gh, "api", "user").get("login")
    if not isinstance(viewer, str) or not viewer:
        raise WorkflowError("GitHub 当前用户缺少有效 login")
    assignees = issue.get("assignees", [])
    if not isinstance(assignees, list):
        raise WorkflowError("Issue assignees 响应无效")
    if viewer not in {assignee.get("login") for assignee in assignees if isinstance(assignee, dict)}:
        run(gh, "issue", "edit", str(issue["number"]), "--repo", repo, "--add-assignee", "@me")
    return viewer


def issue_comments(gh: str, repo: str, issue_number: int) -> list[dict]:
    pages = run_json(
        gh,
        "api",
        f"repos/{repo}/issues/{issue_number}/comments",
        "--paginate",
        "--slurp",
    )
    if not isinstance(pages, list):
        raise WorkflowError("议题评论响应无效")
    comments: list[dict] = []
    for page in pages:
        if not isinstance(page, list):
            raise WorkflowError("议题评论分页数据无效")
        comments.extend(page)
    return comments


def continue_comment(gh: str, repo: str, issue_number: int, body: str, operation_id: str) -> dict:
    marker = f"<!-- codex-feature-continue:{operation_id} -->"
    expected_body = f"{body}\n\n{marker}"
    matches = [comment for comment in issue_comments(gh, repo, issue_number) if marker in comment.get("body", "")]
    if len(matches) > 1:
        raise WorkflowError("多条议题评论包含同一个待处理继续开发标记")
    if matches:
        if matches[0].get("body") != expected_body:
            raise WorkflowError("待处理继续开发评论标记对应的内容不符合预期")
        return matches[0]
    return run_json(
        gh,
        "api",
        f"repos/{repo}/issues/{issue_number}/comments",
        "--method",
        "POST",
        "-f",
        f"body={expected_body}",
    )


def command_create(args):
    gh, _, git_dir, repo, owner, number, names = context()
    summary = " ".join(args.summary.split())
    if not summary:
        raise WorkflowError("摘要不能为空")
    body = request_text(args.request_file, "feature-create")
    pending = state_path(git_dir)
    if pending.exists():
        state = load_state(git_dir)
        if state.get("repo") != repo or state.get("project_owner") != owner or state.get("project_number") != number:
            raise WorkflowError("待处理的议题状态不属于当前仓库或项目")
        issue = pending_issue(gh, repo, state, body)
        if issue.get("title") != state["summary"]:
            raise WorkflowError(f"待处理的议题标题不符合预期：{issue.get('title')!r}")
        state["assignee"] = ensure_self_assigned(gh, repo, issue)
        item_id = state.get("project_item_id")
        if not isinstance(item_id, str) or not item_id:
            item_id = ensure_project_item(gh, owner, number, state["issue_url"])["id"]
            state["project_item_id"] = item_id
        if state.get("ready_set") is not True:
            set_status(gh, owner, number, state["issue_url"], names, names["ready"], None, item_id)
            state["ready_set"] = True
            state.pop("backlog_set", None)
            pending.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        set_status(gh, owner, number, state["issue_url"], names, names["progress"], None, item_id)
        pending.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({**state, "project_status": names["progress"], "action": "resumed"}, ensure_ascii=False))
        return
    issue_url = run(
        gh,
        "issue",
        "create",
        "--repo",
        repo,
        "--title",
        summary,
        "--body",
        body,
        "--assignee",
        "@me",
    )
    issue_number = int(issue_url.rstrip("/").rsplit("/", 1)[-1])
    state = {
        "repo": repo,
        "issue_number": issue_number,
        "issue_url": issue_url,
        "summary": summary,
        "project_owner": owner,
        "project_number": number,
        "request_sha256": sha256_text(body),
        "assignee": "@me",
    }
    pending.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    item = add_project_item(gh, owner, number, issue_url)
    state["project_item_id"] = item["id"]
    pending.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    set_status(gh, owner, number, issue_url, names, names["ready"], None, item["id"])
    state["ready_set"] = True
    pending.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    set_status(gh, owner, number, issue_url, names, names["progress"], None, item["id"])
    print(json.dumps({**state, "project_status": names["progress"], "action": "created"}, ensure_ascii=False))


def command_continue(args):
    gh, _, git_dir, repo, owner, number, names = context()
    body = request_text(args.request_file, "feature-continue")
    path = continue_state_path(git_dir)
    action = "started"
    if path.exists():
        action = "resumed"
        try:
            state = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise WorkflowError(f"待处理的继续开发状态无效：{path}") from exc
        issue = issue_for_state(gh, repo, owner, number, state)
        if state.get("request_sha256") != sha256_text(body):
            raise WorkflowError("待处理的继续开发状态属于其他请求")
        if not isinstance(state.get("operation_id"), str) or not state["operation_id"]:
            raise WorkflowError("待处理的继续开发状态包含无效 operation_id")
    else:
        state = load_state(git_dir)
        issue = issue_for_state(gh, repo, owner, number, state)
        state = {
            **state,
            "request_sha256": sha256_text(body),
            "operation_id": secrets.token_hex(16),
        }
        path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ensure_issue_open(gh, repo, issue)
    comment = continue_comment(gh, repo, issue["number"], body, state["operation_id"])
    set_status(gh, owner, number, issue["url"], names, names["progress"], None)
    print(
        json.dumps(
            {
                **issue,
                "comment_id": comment.get("id"),
                "project_status": names["progress"],
                "issue_state": issue["state"],
                "action": action,
            },
            ensure_ascii=False,
        )
    )


def command_review(_args):
    gh, _, git_dir, repo, owner, number, names = context()
    pending = continue_state_path(git_dir)
    if pending.exists():
        try:
            state = json.loads(pending.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise WorkflowError(f"待处理的继续开发状态无效：{pending}") from exc
        expected = {
            "repo": repo,
            "project_owner": owner,
            "project_number": number,
        }
        if any(state.get(key) != value for key, value in expected.items()):
            raise WorkflowError("待处理的继续开发状态属于其他请求、议题或项目")
    else:
        state = load_state(git_dir)
    issue = issue_for_state(gh, repo, owner, number, state)
    set_status(gh, owner, number, issue["url"], names, names["review"], None)
    if pending.exists():
        pending.unlink()
    print(
        json.dumps(
            {**issue, "project_status": names["review"], "table": issue_table(issue, names["review"])},
            ensure_ascii=False,
        )
    )


def command_done(_args):
    gh, _, git_dir, repo, owner, number, names = context()
    pending = state_path(git_dir)
    issue = issue_for_state(gh, repo, owner, number, load_state(git_dir))
    set_status(gh, owner, number, issue["url"], names, names["done"], None)
    ensure_issue_closed(gh, repo, issue)
    pending.unlink()
    print(
        json.dumps(
            {
                **issue,
                "project_status": names["done"],
                "issue_state": issue["state"],
                "local_state": "cleared",
                "table": issue_table(issue, names["done"]),
            },
            ensure_ascii=False,
        )
    )


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    sub = result.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create")
    create.add_argument("--summary", required=True)
    create.add_argument("--request-file", required=True)
    create.set_defaults(handler=command_create)
    cont = sub.add_parser("continue")
    cont.add_argument("--request-file", required=True)
    cont.set_defaults(handler=command_continue)
    review = sub.add_parser("review")
    review.set_defaults(handler=command_review)
    done = sub.add_parser("done")
    done.set_defaults(handler=command_done)
    return result


def main() -> int:
    try:
        args = parser().parse_args()
        args.handler(args)
        return 0
    except (WorkflowError, KeyError, ValueError, OSError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

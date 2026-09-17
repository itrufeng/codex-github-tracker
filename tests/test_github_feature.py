from __future__ import annotations

import importlib.util
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).parents[1] / "_feature-workflow" / "github_feature.py"
SPEC = importlib.util.spec_from_file_location("github_feature", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
github_feature = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(github_feature)


class WorkflowIssueStateTests(unittest.TestCase):
    def test_create_accepts_summary_longer_than_thirty_characters(self):
        summary = "这是一个已经经过提炼但长度明显超过三十个字符的清晰 Issue title 摘要"
        names = {"ready": "Ready", "progress": "In progress"}

        with tempfile.TemporaryDirectory() as directory:
            git_dir = Path(directory)
            output = io.StringIO()
            with (
                patch.object(github_feature, "context", return_value=("gh", Path.cwd(), git_dir, "o/r", "@me", 4, names)),
                patch.object(github_feature, "request_text", return_value="新功能"),
                patch.object(github_feature, "run", return_value="https://example.test/issues/2") as run,
                patch.object(github_feature, "add_project_item", return_value={"id": "item-2"}),
                patch.object(github_feature, "set_status"),
                redirect_stdout(output),
            ):
                github_feature.command_create(type("Args", (), {"summary": summary, "request_file": "request.txt"})())

        self.assertGreater(len(summary), 30)
        self.assertEqual(run.call_args.args[6], summary)
        self.assertEqual(json.loads(output.getvalue())["summary"], summary)

    def test_create_rejects_empty_summary(self):
        names = {"ready": "Ready", "progress": "In progress"}

        with tempfile.TemporaryDirectory() as directory:
            with (
                patch.object(github_feature, "context", return_value=("gh", Path.cwd(), Path(directory), "o/r", "@me", 4, names)),
                self.assertRaisesRegex(github_feature.WorkflowError, "摘要不能为空"),
            ):
                github_feature.command_create(type("Args", (), {"summary": "  \n ", "request_file": "request.txt"})())

    def test_create_explicitly_moves_from_ready_to_in_progress(self):
        transitions = []
        names = {"ready": "Ready", "progress": "In progress"}

        def record_status(_gh, _owner, _number, _url, _names, target, expected, _item_id):
            transitions.append((target, expected))

        with tempfile.TemporaryDirectory() as directory:
            git_dir = Path(directory)
            output = io.StringIO()
            with (
                patch.object(github_feature, "context", return_value=("gh", Path.cwd(), git_dir, "o/r", "@me", 4, names)),
                patch.object(github_feature, "request_text", return_value="新功能"),
                patch.object(github_feature, "run", return_value="https://example.test/issues/2") as run,
                patch.object(github_feature, "add_project_item", return_value={"id": "item-2"}),
                patch.object(github_feature, "set_status", side_effect=record_status),
                redirect_stdout(output),
            ):
                github_feature.command_create(type("Args", (), {"summary": "新功能", "request_file": "request.txt"})())

            state = json.loads(github_feature.state_path(git_dir).read_text(encoding="utf-8"))

        self.assertEqual(transitions, [("Ready", None), ("In progress", None)])
        run.assert_called_once_with(
            "gh",
            "issue",
            "create",
            "--repo",
            "o/r",
            "--title",
            "新功能",
            "--body",
            "新功能",
            "--assignee",
            "@me",
        )
        self.assertEqual(state["assignee"], "@me")
        self.assertIs(state["ready_set"], True)
        self.assertEqual(json.loads(output.getvalue())["project_status"], "In progress")

    def test_create_migrates_legacy_backlog_marker_through_ready(self):
        transitions = []
        names = {"ready": "Ready", "progress": "In progress"}
        issue = {
            "number": 2,
            "title": "新功能",
            "body": "新功能",
            "url": "https://example.test/issues/2",
            "state": "OPEN",
        }

        def record_status(_gh, _owner, _number, _url, _names, target, expected, _item_id):
            transitions.append((target, expected))

        with tempfile.TemporaryDirectory() as directory:
            git_dir = Path(directory)
            state = {
                "repo": "o/r",
                "issue_number": 2,
                "issue_url": issue["url"],
                "summary": "新功能",
                "project_owner": "@me",
                "project_number": 4,
                "project_item_id": "item-2",
                "backlog_set": True,
            }
            github_feature.state_path(git_dir).write_text(json.dumps(state), encoding="utf-8")
            output = io.StringIO()
            with (
                patch.object(github_feature, "context", return_value=("gh", Path.cwd(), git_dir, "o/r", "@me", 4, names)),
                patch.object(github_feature, "request_text", return_value="新功能"),
                patch.object(github_feature, "pending_issue", return_value=issue),
                patch.object(github_feature, "ensure_self_assigned", return_value="octocat") as assign,
                patch.object(github_feature, "set_status", side_effect=record_status),
                redirect_stdout(output),
            ):
                github_feature.command_create(type("Args", (), {"summary": "新功能", "request_file": "request.txt"})())

            migrated = json.loads(github_feature.state_path(git_dir).read_text(encoding="utf-8"))

        self.assertEqual(transitions, [("Ready", None), ("In progress", None)])
        assign.assert_called_once_with("gh", "o/r", issue)
        self.assertEqual(migrated["assignee"], "octocat")
        self.assertIs(migrated["ready_set"], True)
        self.assertNotIn("backlog_set", migrated)
        self.assertEqual(json.loads(output.getvalue())["action"], "resumed")

    def test_ensure_self_assigned_only_edits_when_viewer_is_missing(self):
        issue = {"number": 2, "assignees": [{"login": "someone-else"}]}

        with (
            patch.object(github_feature, "run_json", return_value={"login": "octocat"}),
            patch.object(github_feature, "run") as run,
        ):
            login = github_feature.ensure_self_assigned("gh", "o/r", issue)

        self.assertEqual(login, "octocat")
        run.assert_called_once_with(
            "gh", "issue", "edit", "2", "--repo", "o/r", "--add-assignee", "@me"
        )

        issue["assignees"].append({"login": "octocat"})
        with (
            patch.object(github_feature, "run_json", return_value={"login": "octocat"}),
            patch.object(github_feature, "run") as run,
        ):
            github_feature.ensure_self_assigned("gh", "o/r", issue)

        run.assert_not_called()

    def test_issue_table_contains_title_column_and_url(self):
        issue = {"title": "功能", "url": "https://example.test/1"}

        table = github_feature.issue_table(issue, "In review")

        self.assertIn("| 标题 | 功能", table)
        self.assertIn("| 列名 | In review", table)
        self.assertIn("| 地址 | https://example.test/1", table)
        self.assertEqual(len({github_feature.text_width(line) for line in table.splitlines()}), 1)

    def test_done_moves_project_item_before_closing_issue(self):
        events = []
        issue = {"number": 1, "title": "功能", "url": "https://example.test/1", "state": "OPEN"}
        names = {"done": "Done"}

        def record_status(*_args):
            events.append("status")

        def record_run(*args):
            events.append(args)
            return ""

        with tempfile.TemporaryDirectory() as directory:
            git_dir = Path(directory)
            pending = github_feature.state_path(git_dir)
            pending.write_text("{}", encoding="utf-8")
            output = io.StringIO()
            with (
                patch.object(github_feature, "context", return_value=("gh", Path.cwd(), git_dir, "o/r", "@me", 4, names)),
                patch.object(github_feature, "load_state", return_value={}),
                patch.object(github_feature, "issue_for_state", return_value=issue),
                patch.object(github_feature, "set_status", side_effect=record_status),
                patch.object(github_feature, "run", side_effect=record_run),
                redirect_stdout(output),
            ):
                github_feature.command_done(None)

            self.assertFalse(pending.exists())

        self.assertEqual(events[0], "status")
        self.assertEqual(events[1], ("gh", "issue", "close", "1", "--repo", "o/r", "--reason", "completed"))
        self.assertEqual(
            json.loads(output.getvalue()),
            {
                **issue,
                "project_status": "Done",
                "issue_state": "CLOSED",
                "local_state": "cleared",
                "table": github_feature.issue_table(issue, "Done"),
            },
        )

    def test_done_does_not_close_an_already_closed_issue_again(self):
        issue = {"number": 1, "title": "功能", "url": "https://example.test/1", "state": "CLOSED"}
        names = {"done": "Done"}

        with tempfile.TemporaryDirectory() as directory:
            git_dir = Path(directory)
            pending = github_feature.state_path(git_dir)
            pending.write_text("{}", encoding="utf-8")
            with (
                patch.object(github_feature, "context", return_value=("gh", Path.cwd(), git_dir, "o/r", "@me", 4, names)),
                patch.object(github_feature, "load_state", return_value={}),
                patch.object(github_feature, "issue_for_state", return_value=issue),
                patch.object(github_feature, "set_status"),
                patch.object(github_feature, "run") as run,
                redirect_stdout(io.StringIO()),
            ):
                github_feature.command_done(None)

            self.assertFalse(pending.exists())

        run.assert_not_called()

    def test_done_preserves_local_state_when_closing_fails(self):
        issue = {"number": 1, "title": "功能", "url": "https://example.test/1", "state": "OPEN"}
        names = {"done": "Done"}

        with tempfile.TemporaryDirectory() as directory:
            git_dir = Path(directory)
            pending = github_feature.state_path(git_dir)
            pending.write_text("{}", encoding="utf-8")
            with (
                patch.object(github_feature, "context", return_value=("gh", Path.cwd(), git_dir, "o/r", "@me", 4, names)),
                patch.object(github_feature, "load_state", return_value={}),
                patch.object(github_feature, "issue_for_state", return_value=issue),
                patch.object(github_feature, "set_status"),
                patch.object(github_feature, "run", side_effect=github_feature.WorkflowError("关闭失败")),
                self.assertRaises(github_feature.WorkflowError),
            ):
                github_feature.command_done(None)

            self.assertTrue(pending.exists())

    def test_continue_reopens_before_commenting_and_moving_project_item(self):
        events = []
        issue = {"number": 1, "title": "功能", "url": "https://example.test/1", "state": "CLOSED"}
        names = {"progress": "In progress"}

        def record_run(*args):
            events.append(args)
            return ""

        def record_comment(*_args):
            events.append("comment")
            return {"id": 2}

        def record_status(*_args):
            events.append("status")

        with tempfile.TemporaryDirectory() as directory:
            git_dir = Path(directory)
            output = io.StringIO()
            with (
                patch.object(github_feature, "context", return_value=("gh", Path.cwd(), git_dir, "o/r", "@me", 4, names)),
                patch.object(github_feature, "request_text", return_value="继续开发"),
                patch.object(github_feature, "load_state", return_value={"issue_number": 1}),
                patch.object(github_feature, "issue_for_state", return_value=issue),
                patch.object(github_feature, "continue_comment", side_effect=record_comment),
                patch.object(github_feature, "set_status", side_effect=record_status),
                patch.object(github_feature, "run", side_effect=record_run),
                redirect_stdout(output),
            ):
                github_feature.command_continue(type("Args", (), {"request_file": "request.txt"})())

        self.assertEqual(events[0], ("gh", "issue", "reopen", "1", "--repo", "o/r"))
        self.assertEqual(events[1:], ["comment", "status"])
        payload = json.loads(output.getvalue())
        self.assertEqual(payload["project_status"], "In progress")
        self.assertEqual(payload["issue_state"], "OPEN")

    def test_review_returns_issue_table(self):
        issue = {"number": 1, "title": "功能", "url": "https://example.test/1", "state": "OPEN"}
        names = {"review": "In review"}

        with tempfile.TemporaryDirectory() as directory:
            git_dir = Path(directory)
            github_feature.state_path(git_dir).write_text("{}", encoding="utf-8")
            output = io.StringIO()
            with (
                patch.object(github_feature, "context", return_value=("gh", Path.cwd(), git_dir, "o/r", "@me", 4, names)),
                patch.object(github_feature, "load_state", return_value={}),
                patch.object(github_feature, "issue_for_state", return_value=issue),
                patch.object(github_feature, "set_status"),
                redirect_stdout(output),
            ):
                github_feature.command_review(None)

        payload = json.loads(output.getvalue())
        self.assertEqual(payload["project_status"], "In review")
        self.assertEqual(payload["table"], github_feature.issue_table(issue, "In review"))


if __name__ == "__main__":
    unittest.main()

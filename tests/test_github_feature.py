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
    def test_done_moves_project_item_before_closing_issue(self):
        events = []
        issue = {"number": 1, "title": "功能", "url": "https://example.test/1", "state": "OPEN"}
        names = {"done": "Done"}

        def record_status(*_args):
            events.append("status")

        def record_run(*args):
            events.append(args)
            return ""

        output = io.StringIO()
        with (
            patch.object(github_feature, "context", return_value=("gh", Path.cwd(), Path.cwd(), "o/r", "@me", 4, names)),
            patch.object(github_feature, "load_state", return_value={}),
            patch.object(github_feature, "issue_for_state", return_value=issue),
            patch.object(github_feature, "set_status", side_effect=record_status),
            patch.object(github_feature, "run", side_effect=record_run),
            redirect_stdout(output),
        ):
            github_feature.command_done(None)

        self.assertEqual(events[0], "status")
        self.assertEqual(events[1], ("gh", "issue", "close", "1", "--repo", "o/r", "--reason", "completed"))
        self.assertEqual(
            json.loads(output.getvalue()),
            {**issue, "project_status": "Done", "issue_state": "CLOSED"},
        )

    def test_done_does_not_close_an_already_closed_issue_again(self):
        issue = {"number": 1, "title": "功能", "url": "https://example.test/1", "state": "CLOSED"}
        names = {"done": "Done"}

        with (
            patch.object(github_feature, "context", return_value=("gh", Path.cwd(), Path.cwd(), "o/r", "@me", 4, names)),
            patch.object(github_feature, "load_state", return_value={}),
            patch.object(github_feature, "issue_for_state", return_value=issue),
            patch.object(github_feature, "set_status"),
            patch.object(github_feature, "run") as run,
            redirect_stdout(io.StringIO()),
        ):
            github_feature.command_done(None)

        run.assert_not_called()

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


if __name__ == "__main__":
    unittest.main()

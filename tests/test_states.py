import unittest

from pet_tracker import states as S


def sess(sid="a", status="idle", last=0.0):
    return {"session_id": sid, "status": status, "last_activity": last}


class HookEvents(unittest.TestCase):
    def setUp(self):
        self.st = S.SessionStates()

    def ev(self, name, t, **kw):
        return self.st.apply(dict(hook_event_name=name, session_id="a", cwd="/repo", **kw), t)

    def state(self, t, status="busy"):
        return self.st.merge([sess(status=status)], t)[0]

    def test_permission_prompt_keeps_tool_detail(self):
        self.ev("UserPromptSubmit", 1)
        self.ev("PreToolUse", 2, tool_name="Bash", tool_input={"command": "git push origin main"})
        self.ev("Notification", 3, notification_type="permission_prompt", message="Claude needs your permission")
        s = self.state(4)
        self.assertEqual((s["state"], s["wait_kind"], s["tool"], s["detail"]),
                         ("wait", "permission", "Bash", "git push origin main"))

    def test_post_tool_use_clears_wait(self):
        self.ev("PreToolUse", 1, tool_name="Bash", tool_input={"command": "ls"})
        self.ev("Notification", 2, notification_type="permission_prompt")
        self.ev("PostToolUse", 3, tool_name="Bash")
        self.assertEqual(self.state(4)["state"], "run")

    def test_ask_user_question_is_wait_question(self):
        self.ev("PreToolUse", 1, tool_name="AskUserQuestion",
                tool_input={"questions": [{"question": "Dùng Postgres hay SQLite?"}]})
        s = self.state(2)
        self.assertEqual((s["state"], s["wait_kind"], s["detail"]), ("wait", "question", "Dùng Postgres hay SQLite?"))

    def test_stop_is_done_until_seen(self):
        self.ev("Stop", 1, last_assistant_message="Đã sửa xong   test.\n")
        s = self.state(2, status="idle")
        self.assertEqual((s["state"], s["last_msg"]), ("done", "Đã sửa xong test."))
        self.st.mark_seen("a", 3)
        self.assertEqual(self.state(4, status="idle")["state"], "idle")

    def test_done_expires(self):
        self.ev("Stop", 0)
        self.assertEqual(self.state(S.DONE_TTL + 5, status="idle")["state"], "idle")

    def test_idle_prompt_does_not_hide_done(self):
        self.ev("Stop", 1)
        self.ev("Notification", 2, notification_type="idle_prompt")
        self.assertEqual(self.state(3, status="idle")["state"], "done")

    def test_relative_file_path(self):
        self.ev("PreToolUse", 1, tool_name="Edit", tool_input={"file_path": "/repo/src/Hero.tsx"})
        self.assertEqual(self.state(2)["detail"], "src/Hero.tsx")

    def test_todo_progress(self):
        todos = [{"content": "a", "status": "completed"}, {"content": "b", "status": "in_progress"},
                 {"content": "c", "status": "pending"}]
        self.ev("PreToolUse", 1, tool_name="TodoWrite", tool_input={"todos": todos})
        s = self.state(2)
        self.assertEqual((s["todo"], s["detail"]), ((1, 3), "b"))

    def test_missed_stop_falls_back_to_poll(self):
        self.ev("UserPromptSubmit", 1)
        self.assertEqual(self.state(1 + S.RUN_STALE + 1, status="idle")["state"], "idle")

    def test_session_end_and_unknown_events(self):
        self.ev("UserPromptSubmit", 1)
        self.assertFalse(self.ev("SubagentStart", 2))
        self.assertTrue(self.ev("SessionEnd", 3))
        self.assertNotIn("a", self.st.rec)

    def test_long_detail_is_cut(self):
        self.ev("PreToolUse", 1, tool_name="Bash", tool_input={"command": "x" * 500})
        self.assertLessEqual(len(self.state(2)["detail"]), S.DETAIL_MAX)


class PollFallback(unittest.TestCase):
    def test_busy_then_idle_is_done(self):
        st = S.SessionStates()
        self.assertEqual(st.merge([sess(status="busy")], 1)[0]["state"], "run")
        self.assertEqual(st.merge([sess(status="idle")], 2)[0]["state"], "done")
        self.assertEqual(st.merge([sess(status="idle")], 3)[0]["state"], "done")

    def test_dead_sessions_are_forgotten(self):
        st = S.SessionStates()
        st.merge([sess("a", "busy"), sess("b", "busy")], 1)
        st.merge([sess("a", "busy")], 2)
        self.assertNotIn("b", st.polled)


class Ordering(unittest.TestCase):
    def test_sort_and_counts(self):
        st = S.SessionStates()
        st.apply({"hook_event_name": "Notification", "session_id": "w", "notification_type": "permission_prompt"}, 1)
        st.apply({"hook_event_name": "Stop", "session_id": "d"}, 1)
        out = st.merge([sess("i", "idle", 9), sess("d", "idle", 5), sess("r", "busy", 1), sess("w", "busy", 0)], 2)
        self.assertEqual([s["session_id"] for s in out], ["w", "r", "d", "i"])
        self.assertEqual(S.counts(out), {"wait": 1, "run": 1, "done": 1, "idle": 1})
        self.assertEqual(S.headline(out, 50, 85), "wait")
        self.assertEqual(S.headline(out[1:], 90, 85), "quota")
        self.assertEqual(S.headline(out[3:], 10, 85), "idle")


if __name__ == "__main__":
    unittest.main()

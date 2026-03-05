import os
import sys
import time
import signal
import subprocess
import unittest
from pathlib import Path
import requests


class WebUiE2ESmokeTest(unittest.TestCase):
    project_root = Path(__file__).resolve().parents[2]
    base_url = "http://127.0.0.1:8086"

    def start_server(self, password: str | None):
        env = os.environ.copy()
        if password is None:
            env.pop("WEB_UI_PASSWORD", None)
        else:
            env["WEB_UI_PASSWORD"] = password
        proc = subprocess.Popen(
            [sys.executable, "web_ui.py"],
            cwd=str(self.project_root),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            preexec_fn=os.setsid,
        )
        for _ in range(60):
            try:
                requests.get(self.base_url + "/login", timeout=0.2)
                return proc
            except Exception:
                time.sleep(0.1)
        self.stop_server(proc)
        self.fail("Web UI server did not become ready")

    def stop_server(self, proc: subprocess.Popen):
        if proc.poll() is not None:
            return
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            proc.wait(timeout=3)
        except Exception:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except Exception:
                pass

    def test_homepage_redirect_when_auth_enabled(self):
        proc = self.start_server("secret")
        try:
            response = requests.get(self.base_url + "/", allow_redirects=False, timeout=2)
            self.assertEqual(response.status_code, 303)
            self.assertEqual(response.headers.get("location"), "/login")
        finally:
            self.stop_server(proc)

    def test_homepage_access_without_auth(self):
        proc = self.start_server(None)
        try:
            response = requests.get(self.base_url + "/", timeout=2)
            self.assertEqual(response.status_code, 200)
            self.assertIn("Fanbox Extractor", response.text)
        finally:
            self.stop_server(proc)

    def test_first_screen_response_under_two_seconds(self):
        proc = self.start_server(None)
        try:
            start = time.perf_counter()
            response = requests.get(self.base_url + "/", timeout=2)
            elapsed = time.perf_counter() - start
            self.assertEqual(response.status_code, 200)
            self.assertLess(elapsed, 2.0)
        finally:
            self.stop_server(proc)

    def test_browser_user_agent_matrix(self):
        agents = {
            "chrome": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "firefox": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.0; rv:132.0) Gecko/20100101 Firefox/132.0",
            "safari": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15",
            "edge": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
        }
        proc = self.start_server(None)
        try:
            for _, user_agent in agents.items():
                response = requests.get(self.base_url + "/", headers={"User-Agent": user_agent}, timeout=2)
                self.assertEqual(response.status_code, 200)
                self.assertIn("Fanbox Extractor", response.text)
        finally:
            self.stop_server(proc)


if __name__ == "__main__":
    unittest.main()

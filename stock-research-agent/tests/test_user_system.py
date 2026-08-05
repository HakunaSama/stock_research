import io
import os
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image


class UserSystemIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        os.environ["STOCK_DATA_DIR"] = cls.temp.name
        os.environ.pop("STOCK_DB_PATH", None)
        from webapp.app import app

        cls.client_context = TestClient(app)
        cls.client = cls.client_context.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.client_context.__exit__(None, None, None)
        cls.temp.cleanup()

    def test_profile_avatar_and_session_lifecycle(self):
        email = "profile@example.com"
        password = "StrongPass-2026"
        with patch("webapp.emailer.send_code", side_effect=lambda _email, _purpose, code, _ttl: code):
            code_response = self.client.post(
                "/api/auth/send-code", json={"email": email, "purpose": "register"}
            )
        self.assertEqual(code_response.status_code, 200)
        code = code_response.json()["dev_code"]

        registered = self.client.post(
            "/api/auth/register",
            json={"email": email, "code": code, "password": password, "username": "profile_user"},
            headers={"user-agent": "Test Browser macOS"},
        )
        self.assertEqual(registered.status_code, 200, registered.text)
        self.assertEqual(registered.json()["display_name"], "profile_user")

        denied = self.client.patch(
            "/api/auth/profile",
            json={"username": "renamed_user", "display_name": "研究员", "bio": "价值投资"},
        )
        self.assertEqual(denied.status_code, 400)

        updated = self.client.patch(
            "/api/auth/profile",
            json={
                "username": "renamed_user",
                "display_name": "研究员",
                "bio": "价值投资",
                "current_password": password,
            },
        )
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertEqual(updated.json()["display_name"], "研究员")

        image_buffer = io.BytesIO()
        Image.new("RGB", (900, 600), (130, 71, 255)).save(image_buffer, format="PNG")
        avatar = self.client.put(
            "/api/auth/avatar",
            content=image_buffer.getvalue(),
            headers={"content-type": "image/png"},
        )
        self.assertEqual(avatar.status_code, 200, avatar.text)
        avatar_url = avatar.json()["avatar_url"]
        self.assertTrue(avatar_url.endswith(".webp"))
        avatar_file = self.client.get(avatar_url)
        self.assertEqual(avatar_file.status_code, 200)
        self.assertEqual(avatar_file.headers["content-type"], "image/webp")

        second = TestClient(self.client.app)
        login = second.post(
            "/api/auth/login",
            json={"account": "renamed_user", "password": password},
            headers={"user-agent": "Second Device Windows Chrome"},
        )
        self.assertEqual(login.status_code, 200, login.text)
        sessions = self.client.get("/api/auth/sessions")
        self.assertEqual(sessions.status_code, 200)
        self.assertEqual(len(sessions.json()), 2)
        self.assertEqual(sum(1 for row in sessions.json() if row["current"]), 1)

        revoked = self.client.post("/api/auth/sessions/revoke-others")
        self.assertEqual(revoked.status_code, 200)
        self.assertEqual(len(self.client.get("/api/auth/sessions").json()), 1)
        self.assertEqual(second.get("/api/auth/me").status_code, 401)
        second.close()

        removed = self.client.delete("/api/auth/avatar")
        self.assertEqual(removed.status_code, 200)
        self.assertEqual(removed.json()["avatar_url"], "")
        self.assertEqual(self.client.get(avatar_url).status_code, 404)


if __name__ == "__main__":
    unittest.main()

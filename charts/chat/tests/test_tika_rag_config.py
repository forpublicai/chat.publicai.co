#!/usr/bin/env python3
"""Regression tests for chat chart Tika version pinning and OpenWebUI RAG config sync."""

import importlib.util
import os
import re
import subprocess
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

import yaml


REPO_ROOT = Path(__file__).resolve().parents[3]
CHAT_CHART = REPO_ROOT / "charts" / "chat"
SYNC_SCRIPT = CHAT_CHART / "scripts" / "sync-openwebui-config.py"


def render_chat_chart(env_values_relpath: str) -> list[dict]:
    cmd = [
        "helm",
        "template",
        "chat",
        str(CHAT_CHART),
        "-f",
        str(CHAT_CHART / "values.yaml"),
        "-f",
        str(REPO_ROOT / env_values_relpath),
    ]
    res = subprocess.run(cmd, check=True, capture_output=True, text=True)
    return [doc for doc in yaml.safe_load_all(res.stdout) if doc]


def env_map(container: dict) -> dict[str, str | None]:
    return {entry["name"]: entry.get("value") for entry in container.get("env", [])}


class TestChatTikaAndRagHelmConfig(unittest.TestCase):
    ENV_FILES = [
        "argo/environments/prod/chat-values.yaml",
        "argo/environments/staging/chat-values.yaml",
    ]

    def test_tika_image_pinned_and_matches_openwebui_and_syncer(self):
        for env_file in self.ENV_FILES:
            with self.subTest(env=env_file):
                docs = render_chat_chart(env_file)

                tika_deploy = next(
                    d for d in docs if d.get("kind") == "Deployment" and d["metadata"]["name"] == "tika"
                )
                tika_image = tika_deploy["spec"]["template"]["spec"]["containers"][0]["image"]
                self.assertNotIn("latest", tika_image, f"Tika image must be pinned, got {tika_image}")

                match = re.search(r":(\d+)\.", tika_image)
                self.assertIsNotNone(match, f"Expected semver tag on Tika image, got {tika_image}")
                tika_major = match.group(1)

                ow_deploy = next(
                    d for d in docs if d.get("kind") == "Deployment" and d["metadata"]["name"] == "openwebui"
                )
                ow_env = env_map(ow_deploy["spec"]["template"]["spec"]["containers"][0])
                self.assertEqual(ow_env.get("CONTENT_EXTRACTION_ENGINE"), "tika")
                self.assertEqual(ow_env.get("TIKA_SERVER_URL"), "http://tika-service:9998")
                self.assertEqual(
                    ow_env.get("TIKA_SERVER_VERSION"),
                    tika_major,
                    f"OpenWebUI TIKA_SERVER_VERSION must match Tika major version ({tika_major})",
                )

                sync_job = next(
                    d for d in docs if d.get("kind") == "Job" and d["metadata"]["name"].endswith("-config-syncer")
                )
                sync_env = env_map(sync_job["spec"]["template"]["spec"]["containers"][0])
                self.assertEqual(
                    sync_env.get("TIKA_SERVER_VERSION"),
                    tika_major,
                    f"config-syncer TIKA_SERVER_VERSION must match Tika major version ({tika_major})",
                )

    def test_external_reranker_url_includes_rerank_path(self):
        for env_file in self.ENV_FILES:
            with self.subTest(env=env_file):
                docs = render_chat_chart(env_file)
                ow_deploy = next(
                    d for d in docs if d.get("kind") == "Deployment" and d["metadata"]["name"] == "openwebui"
                )
                ow_env = env_map(ow_deploy["spec"]["template"]["spec"]["containers"][0])
                self.assertEqual(
                    ow_env.get("RAG_EXTERNAL_RERANKER_URL"),
                    "http://litellm-service.platform.svc.cluster.local:4000/v1/rerank",
                )


class TestSyncOpenWebUIConfig(unittest.TestCase):
    def _load_sync_module(self):
        # Provide lightweight stub for psycopg2 when running in environments without it installed
        fake_psycopg2 = types.ModuleType("psycopg2")
        fake_extras = types.ModuleType("psycopg2.extras")

        class FakeJson:
            def __init__(self, adapted):
                self.adapted = adapted

        fake_extras.Json = FakeJson
        fake_psycopg2.extras = fake_extras

        with mock.patch.dict(sys.modules, {"psycopg2": fake_psycopg2, "psycopg2.extras": fake_extras}):
            spec = importlib.util.spec_from_file_location("sync_openwebui_config", SYNC_SCRIPT)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module

    def test_sync_config_upserts_tika_server_version_and_reranker_url(self):
        mod = self._load_sync_module()

        upserts: dict[str, object] = {}

        class FakeCursor:
            def execute(self, sql, params=None):
                if "INSERT INTO config" in sql and params:
                    key, json_wrapper, _now = params
                    upserts[key] = json_wrapper.adapted

            def close(self):
                pass

        class FakeConn:
            def cursor(self):
                return FakeCursor()

            def commit(self):
                pass

            def close(self):
                pass

        env = {
            "DATABASE_URL": "postgresql://stub/openwebui",
            "LITELLM_ENDPOINT": "http://litellm-service.platform.svc.cluster.local:4000/v1",
            "TIKA_SERVER_VERSION": "4",
            "MODELS_CONFIG_FILE": "/nonexistent/models.yaml",
        }
        with mock.patch.dict(os.environ, env, clear=True):
            with mock.patch.object(mod, "wait_for_database_and_tables", return_value=FakeConn()):
                mod.sync_config()

        self.assertEqual(upserts.get("rag.tika_server_version"), "4")
        self.assertEqual(
            upserts.get("rag.external_reranker_url"),
            "http://litellm-service.platform.svc.cluster.local:4000/v1/rerank",
        )


if __name__ == "__main__":
    unittest.main()

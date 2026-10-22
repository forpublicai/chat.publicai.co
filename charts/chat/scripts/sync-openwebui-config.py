#!/usr/bin/env python3
import os
import sys
import time
import json
import yaml
import psycopg2
from psycopg2.extras import Json

def wait_for_database_and_tables(db_url, timeout=180):
    """
    Waits for PostgreSQL to be ready and for OpenWebUI's Alembic migrations
    to have created the essential tables (config, model).
    This ensures that on fresh/staging installations, the syncer does not fail
    if it starts while OpenWebUI is still initializing.
    """
    print("Waiting for database connection and OpenWebUI tables (config, model) to be ready...")
    start_time = time.time()
    last_err = None
    while time.time() - start_time < timeout:
        try:
            conn = psycopg2.connect(db_url)
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT 
                        to_regclass('public.config') IS NOT NULL AND 
                        to_regclass('public.model') IS NOT NULL
                """)
                row = cur.fetchone()
                if row and row[0]:
                    print("Database connection and tables are ready.")
                    return conn
            conn.close()
        except Exception as e:
            last_err = e
        time.sleep(3)
    raise TimeoutError(f"Timed out waiting for database and tables to be ready after {timeout}s: {last_err}")

def sync_config():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("DATABASE_URL is not set, skipping config sync.")
        return

    litellm_endpoint = os.environ.get("LITELLM_ENDPOINT", "http://litellm-service.platform.svc.cluster.local:4000/v1")
    litellm_api_key = os.environ.get("LITELLM_API_KEY")
    default_model = os.environ.get("DEFAULT_MODEL", "swiss-ai/apertus-v1.5-70b")
    config_file = os.environ.get("MODELS_CONFIG_FILE", "/config/models.yaml")

    conn = wait_for_database_and_tables(db_url)
    cur = conn.cursor()

    now = int(time.time())

    # 1. Synchronize connection settings and RAG defaults in config table
    print(f"Syncing connection settings to LiteLLM endpoint: {litellm_endpoint}")
    config_updates = {
        "openai.api_base_urls": [litellm_endpoint],
        "openai.api_configs": {
            "0": {
                "enable": True,
                "tags": [],
                "prefix_id": "",
                "model_ids": [],
                "connection_type": "local",
                "auth_type": "bearer"
            }
        },
        "rag.openai.api_base_url": litellm_endpoint,
        "rag.external_reranker_url": litellm_endpoint,
        "rag.embedding_engine": "openai",
        "rag.embedding_model": "Cohere/Cohere-embed-multilingual-v3.0",
        "rag.reranking_engine": "external",
        "rag.reranking_model": "Cohere/rerank-v3.5",
        "ui.default_models": default_model,
        "ui.default_pinned_models": default_model,
        "task.model.default": default_model,
        "task.model.external": default_model
    }

    if litellm_api_key:
        print("Configuring LiteLLM API key for OpenAI and RAG connections.")
        config_updates["openai.api_keys"] = [litellm_api_key]
        config_updates["rag.openai.api_key"] = litellm_api_key
        config_updates["rag.external_reranker_api_key"] = litellm_api_key

    for key, val in config_updates.items():
        cur.execute("""
            INSERT INTO config (key, value, updated_at)
            VALUES (%s, %s, %s)
            ON CONFLICT (key) DO UPDATE
            SET value = EXCLUDED.value, updated_at = EXCLUDED.updated_at
        """, (key, Json(val), now))

    # 2. Synchronize models table with declarative model definitions
    if os.path.exists(config_file):
        with open(config_file, "r") as f:
            doc = yaml.safe_load(f)
        models = doc.get("models", [])
        print(f"Loaded {len(models)} declared chat models from {config_file}")

        # Fetch active admin user for ownership attribution (or fallback to 'system' on blank DB)
        admin_user_id = "system"
        try:
            cur.execute("SELECT id FROM \"user\" WHERE role = 'admin' ORDER BY created_at ASC LIMIT 1")
            admin_row = cur.fetchone()
            if admin_row:
                admin_user_id = admin_row[0]
                # Reassign any models previously set to 'system' to this newly registered admin
                cur.execute("UPDATE model SET user_id = %s WHERE user_id = 'system'", (admin_user_id,))
        except Exception as e:
            print(f"Notice: Could not query admin user (falling back to 'system'): {e}")

        active_model_ids = []
        for m in models:
            mid = m["id"]
            name = m["name"]
            base_id = m.get("base_model_id")
            meta = m.get("meta", {})
            params = m.get("params", {})
            active_model_ids.append(mid)

            cur.execute("""
                INSERT INTO model (id, user_id, base_model_id, name, meta, params, is_active, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, true, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name,
                    base_model_id = EXCLUDED.base_model_id,
                    meta = EXCLUDED.meta,
                    params = EXCLUDED.params,
                    is_active = true,
                    updated_at = EXCLUDED.updated_at
            """, (mid, admin_user_id, base_id, name, json.dumps(meta), json.dumps(params), now, now))
            print(f"  ✓ Upserted model: {mid} ({name})")

        # Ensure private RAG models (chat-private) are in DB as is_active = false so they never appear in user dropdowns
        private_rag_models = [
            ("Cohere/Cohere-embed-multilingual-v3.0", "Cohere Multilingual Embeddings"),
            ("Cohere/rerank-v3.5", "Cohere Reranker")
        ]
        for p_id, p_name in private_rag_models:
            cur.execute("""
                INSERT INTO model (id, user_id, base_model_id, name, meta, params, is_active, created_at, updated_at)
                VALUES (%s, %s, NULL, %s, %s, '{}', false, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    is_active = false,
                    meta = EXCLUDED.meta,
                    updated_at = EXCLUDED.updated_at
            """, (p_id, admin_user_id, p_name, json.dumps({"hidden": True, "capabilities": None}), now, now))

        # Deactivate any legacy/undeclared models so users only see the declared chat models
        if active_model_ids:
            cur.execute("""
                UPDATE model
                SET is_active = false, updated_at = %s
                WHERE id NOT IN %s AND is_active = true
            """, (now, tuple(active_model_ids)))
            deactivated_count = cur.rowcount
            if deactivated_count > 0:
                print(f"Deactivated {deactivated_count} undeclared/legacy models in database.")

    conn.commit()
    cur.close()
    conn.close()
    print("Database sync completed successfully.")

    # 3. Invalidate Redis model caches so changes take effect immediately
    redis_url = os.environ.get("REDIS_URL")
    if redis_url:
        try:
            import redis
            print("Connecting to Redis to clear cached model listings...")
            r = redis.Redis.from_url(redis_url)
            pattern = "*models*"
            keys = r.keys(pattern)
            if keys:
                r.delete(*keys)
                print(f"Cleared {len(keys)} model cache keys in Redis.")
            else:
                print("No model cache keys found in Redis.")
        except Exception as e:
            print(f"Notice: Redis cache invalidation error (non-fatal): {e}")

if __name__ == "__main__":
    sync_config()

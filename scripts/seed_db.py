"""Seeds the local Postgres with a ready-to-use admin account, a couple of
regular user accounts, and some sample chats — so a fresh `docker compose up`
doesn't require clicking through OpenWebUI's signup wizard by hand.

Matches the real schema of the pinned OpenWebUI version (v0.11.3): a `user`
row and an `auth` row share one id, passwords are plain bcrypt (matching
`open_webui.utils.auth.get_password_hash`), and `chat.chat` is a JSON blob
holding OpenWebUI's own history-tree shape (parentId/childrenIds chains) —
fully pre-written here, since no model is guaranteed to be reachable locally.

Idempotent by email: safe to run on every `docker compose up` without
duplicating rows. Pass --reset to delete and recreate the seeded accounts
(and only the seeded accounts — never touches any other data).
"""

import argparse
import os
import time
import uuid

import bcrypt
import psycopg2
from psycopg2.extras import Json

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/openwebui"
)

SEEDED_USERS = [
    {"email": "admin@local.test", "password": "admin123", "name": "Local Admin", "role": "admin"},
    {"email": "user1@local.test", "password": "user123", "name": "Sample User One", "role": "user"},
    {"email": "user2@local.test", "password": "user123", "name": "Sample User Two", "role": "user"},
]

# (email, [chat titles]) -- only regular users get sample chats, matching
# what was actually asked for; the admin account is for admin access itself.
SAMPLE_CHATS = {
    "user1@local.test": ["Trip planning", "Recipe ideas"],
    "user2@local.test": ["Debugging a script", "Book recommendations"],
}


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def sample_chat_blob(title: str) -> dict:
    """A minimal, two-message OpenWebUI chat: one user turn, one assistant
    reply, wired together the same way `history.messages` links real chats."""
    now = int(time.time())
    user_msg_id = str(uuid.uuid4())
    assistant_msg_id = str(uuid.uuid4())

    user_message = {
        "id": user_msg_id,
        "parentId": None,
        "childrenIds": [assistant_msg_id],
        "role": "user",
        "content": f"Can you help me with: {title.lower()}?",
        "timestamp": now,
        "models": ["sample-model"],
    }
    assistant_message = {
        "id": assistant_msg_id,
        "parentId": user_msg_id,
        "childrenIds": [],
        "role": "assistant",
        "content": f"Sure — here's some sample seeded content for \"{title}\".",
        "model": "sample-model",
        "modelName": "sample-model",
        "timestamp": now,
        "done": True,
    }

    return {
        "title": title,
        "models": ["sample-model"],
        "history": {
            "currentId": assistant_msg_id,
            "messages": {
                user_msg_id: user_message,
                assistant_msg_id: assistant_message,
            },
        },
        "messages": [user_message, assistant_message],
        "tags": [],
        "timestamp": now,
        "files": [],
    }


def delete_seeded(cur) -> None:
    emails = [u["email"] for u in SEEDED_USERS]
    cur.execute(
        'DELETE FROM chat WHERE user_id IN (SELECT id FROM "user" WHERE email = ANY(%s))',
        (emails,),
    )
    cur.execute("DELETE FROM auth WHERE email = ANY(%s)", (emails,))
    cur.execute('DELETE FROM "user" WHERE email = ANY(%s)', (emails,))


def seed_user(cur, email: str, password: str, name: str, role: str) -> str | None:
    cur.execute('SELECT id FROM "user" WHERE email = %s', (email,))
    existing = cur.fetchone()
    if existing:
        print(f"  {email} already exists, skipping")
        return None

    user_id = str(uuid.uuid4())
    now = int(time.time())

    cur.execute(
        """
        INSERT INTO "user" (
            id, email, name, role, profile_image_url,
            last_active_at, updated_at, created_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (user_id, email, name, role, "/user.png", now, now, now),
    )
    cur.execute(
        "INSERT INTO auth (id, email, password, active) VALUES (%s, %s, %s, %s)",
        (user_id, email, hash_password(password), True),
    )
    print(f"  created {email} ({role})")
    return user_id


def seed_chats(cur, user_id: str, titles: list[str]) -> None:
    now = int(time.time())
    for title in titles:
        chat_id = str(uuid.uuid4())
        blob = sample_chat_blob(title)
        cur.execute(
            """
            INSERT INTO chat (id, user_id, title, chat, created_at, updated_at, archived, pinned)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            # archived/pinned default to False only at the SQLAlchemy ORM layer,
            # not as a real column default -- a raw insert leaves them NULL,
            # and the chat-list query's `WHERE archived = False` silently
            # excludes NULL rows (SQL's three-valued logic), so they must be
            # set explicitly here.
            (chat_id, user_id, title, Json(blob), now, now, False, False),
        )
    print(f"    + {len(titles)} sample chat(s)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reset", action="store_true",
        help="Delete the seeded accounts (and their chats) before recreating them.",
    )
    args = parser.parse_args()

    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    with conn, conn.cursor() as cur:
        if args.reset:
            print("Resetting seeded accounts...")
            delete_seeded(cur)

        print("Seeding accounts...")
        for user in SEEDED_USERS:
            user_id = seed_user(cur, **user)
            if user_id and user["email"] in SAMPLE_CHATS:
                seed_chats(cur, user_id, SAMPLE_CHATS[user["email"]])

    conn.close()
    print("Done.")


if __name__ == "__main__":
    main()

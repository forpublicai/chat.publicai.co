"""Delete Cognito registrations that remain unconfirmed after 24 hours."""

import json
import os
from datetime import datetime, timedelta, timezone


def expired(user, cutoff):
    created = user.get("UserCreateDate")
    return (
        user.get("UserStatus") == "UNCONFIRMED"
        and created is not None
        and created < cutoff
    )


def cleanup(client, pool_id, now=None):
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(hours=24)
    deleted = 0
    pages = client.get_paginator("list_users").paginate(
        UserPoolId=pool_id,
        Filter='cognito:user_status = "UNCONFIRMED"',
        Limit=60,
    )
    for page in pages:
        for user in page.get("Users", []):
            if not expired(user, cutoff):
                continue
            sub = next(
                (item["Value"] for item in user.get("Attributes", []) if item["Name"] == "sub"),
                None,
            )
            if not sub:
                continue
            try:
                # ListUsers can be stale. Recheck immediately before deletion.
                current = client.admin_get_user(UserPoolId=pool_id, Username=sub)
                if expired(current, cutoff):
                    # An immutable ID cannot target a new signup with the same email.
                    client.admin_delete_user(UserPoolId=pool_id, Username=sub)
                    deleted += 1
            except client.exceptions.UserNotFoundException:
                continue
    return deleted


def handler(event, context):
    import boto3

    deleted = cleanup(boto3.client("cognito-idp"), os.environ["USER_POOL_ID"])
    print(json.dumps({"deleted": deleted}))
    return {"deleted": deleted}

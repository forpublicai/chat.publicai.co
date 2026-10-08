import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock

from cleanup import cleanup


NOW = datetime(2026, 9, 21, tzinfo=timezone.utc)


class UserNotFound(Exception):
    pass


def user(sub="original-id", hours=25, status="UNCONFIRMED"):
    return {
        "UserStatus": status,
        "UserCreateDate": NOW - timedelta(hours=hours),
        "Username": "person@example.com",
        "Attributes": [{"Name": "sub", "Value": sub}],
    }


class CleanupTests(unittest.TestCase):
    def setUp(self):
        self.client = Mock()
        self.client.exceptions = SimpleNamespace(UserNotFoundException=UserNotFound)
        self.client.get_paginator.return_value.paginate.return_value = [{"Users": [user()]}]
        self.client.admin_get_user.return_value = user()

    def run_cleanup(self):
        return cleanup(self.client, "test-pool", now=NOW)

    def test_deletes_old_registration_by_immutable_id(self):
        self.assertEqual(self.run_cleanup(), 1)
        self.client.get_paginator.assert_called_once_with("list_users")
        self.client.get_paginator.return_value.paginate.assert_called_once_with(
            UserPoolId="test-pool", Filter='cognito:user_status = "UNCONFIRMED"', Limit=60
        )
        self.client.admin_get_user.assert_called_once_with(
            UserPoolId="test-pool", Username="original-id"
        )
        self.client.admin_delete_user.assert_called_once_with(
            UserPoolId="test-pool", Username="original-id"
        )

    def test_processes_all_pages_including_empty_pages(self):
        self.client.get_paginator.return_value.paginate.return_value = [
            {}, {"Users": [user("first-id")]}, {"Users": []}, {"Users": [user("last-id")]}
        ]
        self.assertEqual(self.run_cleanup(), 2)
        self.assertEqual(
            [call.kwargs["Username"] for call in self.client.admin_delete_user.call_args_list],
            ["first-id", "last-id"],
        )

    def test_skips_recent_confirmed_or_incomplete_records_without_rechecking(self):
        for candidate in [
            user(hours=23), user(hours=24), user(status="CONFIRMED"),
            {**user(), "UserCreateDate": None}, {**user(), "Attributes": []},
        ]:
            with self.subTest(candidate=candidate):
                self.client.get_paginator.return_value.paginate.return_value = [
                    {"Users": [candidate]}
                ]
                self.assertEqual(self.run_cleanup(), 0)
        self.client.admin_get_user.assert_not_called()
        self.client.admin_delete_user.assert_not_called()

    def test_rechecks_status_and_age_before_deleting(self):
        for current in [user(status="CONFIRMED"), user(hours=1), user(hours=24)]:
            with self.subTest(current=current):
                self.client.admin_get_user.return_value = current
                self.assertEqual(self.run_cleanup(), 0)
        self.client.admin_delete_user.assert_not_called()

    def test_missing_account_is_harmless_and_processing_continues(self):
        self.client.get_paginator.return_value.paginate.return_value = [
            {"Users": [user("missing-id"), user()]}
        ]
        self.client.admin_get_user.side_effect = [UserNotFound(), user()]
        self.assertEqual(self.run_cleanup(), 1)
        self.client.admin_delete_user.assert_called_once_with(
            UserPoolId="test-pool", Username="original-id"
        )

    def test_account_disappearing_before_delete_is_harmless(self):
        self.client.admin_delete_user.side_effect = UserNotFound()
        self.assertEqual(self.run_cleanup(), 0)

    def test_failed_status_check_prevents_deletion(self):
        self.client.admin_get_user.side_effect = RuntimeError("Cognito unavailable")
        with self.assertRaises(RuntimeError):
            self.run_cleanup()
        self.client.admin_delete_user.assert_not_called()

    def test_delete_failure_is_reported(self):
        self.client.admin_delete_user.side_effect = RuntimeError("Access denied")
        with self.assertRaises(RuntimeError):
            self.run_cleanup()


if __name__ == "__main__":
    unittest.main()

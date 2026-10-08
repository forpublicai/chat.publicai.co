# Cognito registration cleanup

An hourly Lambda deletes Cognito registrations that are still `UNCONFIRMED`
more than 24 hours after creation. This lets users with expired verification
links sign up again with the same email address ([issue #44](https://github.com/forpublicai/chat.publicai.co/issues/44)).

The Lambda paginates through unconfirmed users, skips recent registrations,
and rechecks each candidate with `AdminGetUser` immediately before deletion.
Reads and deletions use the account's immutable `sub`. Accounts confirmed since
the list was fetched are kept; accounts already removed are skipped.

## Deployment and validation

Both `terraform/11-cognito.tf` (staging) and `terraform_publicai/11-cognito.tf`
(production) use this module. Deploy through the existing Terraform workflows.
Applying enables the hourly job, including cleanup of existing registrations.
Under normal operation, registrations become eligible after 24 hours and are
removed on the next hourly run. The production pool remains externally managed.

Run the offline checks from the repository root:

```bash
python3 -B -m unittest discover -s modules/cognito-cleanup -v
terraform fmt -check -recursive modules/cognito-cleanup
terraform -chdir=terraform init -backend=false -lockfile=readonly
terraform -chdir=terraform validate
terraform -chdir=terraform_publicai init -backend=false -lockfile=readonly
terraform -chdir=terraform_publicai validate
```

Before production, test with a disposable pool in staging: leave one registration
unconfirmed for more than 24 hours, confirm another, and create a recent one.
Verify that only the old unconfirmed registration is deleted and that its email
can sign up again. The normal staging pool auto-confirms permitted signups, so
it cannot exercise expiry without separate test registrations.

## Operations and limitations

- The Lambda logs the number deleted. Its log group retains logs for 30 days.
  Check Lambda `Errors` and `Duration` during rollout. Service errors fail the
  invocation; retries and later hourly runs recheck remaining accounts. Very
  large backlogs may exceed the five-minute execution limit and need attention.
- Account age is measured from creation. A resent verification link does not
  extend it. Confirmation between the final read and deletion can still race
  with cleanup because Cognito has no conditional delete operation.
- Lambda and CloudWatch usage apply. `AdminGetUser` counts candidates toward
  Cognito monthly active users and can affect billing; it is called only for
  old unconfirmed candidates. See [AWS's API documentation](https://docs.aws.amazon.com/cognito-user-identity-pools/latest/APIReference/API_AdminGetUser.html).
- To pause cleanup, set the EventBridge rule's `state` to `DISABLED` and apply.
  An invocation already running may finish. Deleted registrations cannot be
  restored; users must sign up again.

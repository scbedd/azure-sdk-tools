# Replacement for `check-enforcer`

Hey copilot. We have a `github action` that is triggered on every new check update for a given PR. It's role is to watch all the checks that are fired. If _any_ of them fail, then a status for the `check-enforcer` check is posted with `failure` to the PR.

We then set `check-enforcer` in our branch protection rules for the `main` branch as a `required` check.

Well, we are are RETIRING check enforcer. However, this repo is a hodgepodge of different tools, so we really do need some sort of generic `any triggered check cannot fail` enforcement for PRs in this repo.

I'm thinking we do the following -- instead.

Every check that CAN be triggered on a PR (use `tools/test-proxy/ci.yml` as an example here), should add a new `template: ` call.

This call will do the following:

1. Check the active `check` state of the PR that this was submitted for.
2. If there are checks that are not in a `completed` state, post "in-progress" for a check named `All Checks Pass` using gh api to the PR
3. If there are ANY triggered checks that are failed (eg cancelled or error), post `failed` `All Checks Pass` using gh api to the PR.


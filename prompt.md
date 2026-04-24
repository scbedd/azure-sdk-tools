Hey copilot. We have a `github action` that is triggered on every new check update for a given PR. It's role is to watch all the checks that are fired. If _any_ of them fail, then a status for the `check-enforcer` check is posted with `failure` to the PR.

We then set `check-enforcer` in our branch protection rules for the `main` branch as a `required` check.

Well, we are are RETIRING check enforcer. However, this repo is a hodgepodge of different tools, so we really do need some sort of generic `any triggered check cannot fail` enforcement for PRs in this repo.

I'm thinking we do the following -- instead.

First, pull in `research-into-azdo-triggering.md` into your context.

Once you have that, I want you to dig into what it would take to have every one of our `pr` triggered builds ALSO trigger a single global job using `pipeline completion` triggers. THAT job will check the _other_ checks for the status of the repo (minus itself) and ITS status will be the status of the other checks on the build. We can NEVER post success until all other checks but _that_ pipeline is the one that is running.

Here is a walkthrough of a scenario.

User submits a PR to `azure-sdk-tools` (this) repo. It is touching the following files:

- tools/pipeline-generator/Azure.Sdk.Tools.PipelineGenerator/Program.cs
- tools/test-proxy/Azure.Sdk.Tools.TestProxy/Playback.cs

Given the `pr:` triggers configured in multiple `ci.yml` files through this repo, we know that those two files being touched will trigger THESE two `ci.yml` associated build definitions:

- tools/test-proxy/ci.yml
- tools/pipeline-generator/ci.yml

This is what happens _right now_. NOW, what I want you to help me plan the changeset for. We want to add a NEW `public` ci job in the repo. This job will be triggered on the COMPLETION of each build definition associated wih those ci.yml files.

In our azdo project, they correspond to:

- [test-proxy](https://dev.azure.com/azure-sdk/public/_build?definitionId=2892)
- [pipeline-generator](https://dev.azure.com/azure-sdk/public/_build?definitionId=641)

So, when they trigger, they should trigger a new job. `Handle Status Checks`. That job does not exist. I want you to plan the YML that would be within it.

The GOAL is very very straightforward:

- When triggered, get the completion status of all checks posted to github for that PR + sha combination
- If there are any that are `in progress` or errored OTHER THAN SELF (because `Handle Status Checks` IS what we're setting from this job), exit with red check completion.
  - If there are are none (again other than self) that are in-progress, and none errored, complete with success.

We will make this `Handle STatus Checks` "meta"-check the sole `required` check in the repo. 

Write the plan into `plan.md` at the root of this repo.
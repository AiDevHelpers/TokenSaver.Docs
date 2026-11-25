# Branch and submodule workflow

The `mcp` superproject has two submodules: `TokenSaver` and `Common`, plus `SimpleModelServer`. This repo
is the orchestration layer. Each submodule is its own git repo with its own history. The superproject
pins one commit per submodule.

## Rule: one branch name across all repos

All four repos (superproject, `TokenSaver`, `Common`, `SimpleModelServer`) use the same working branch
name, and that branch is `wip`. Keep them in step:

- **Go to wip:** switch every repo to `wip`, not just one.
- **Push a branch:** push it in every repo that has it, and push the submodules first.
- **Merge:** merge into `wip` in every repo.

A branch name that exists in only some repos is a drift. Fix it before doing more work.

## Pushing order

1. Push each submodule's `wip` (`TokenSaver`, `Common`, `SimpleModelServer`).
2. Update the superproject pointer to the pushed commit and commit it.
3. Push the superproject `wip`.

The pointer must name a commit that exists on the remote. Pushing the superproject first leaves a pointer
that other clones can't fetch.

## Pointer updates

After a submodule commit:

```bash
cd /f/source/mcp
git add TokenSaver          # or Common, SimpleModelServer
git commit -m "Update TokenSaver pointer for <change>"
git push origin HEAD
```

## Merging wip into the working branch

When `wip` moves ahead, fast-forward first. If the branches have diverged, merge in each repo and resolve
the submodule pointer to a commit on `wip`:

```bash
git merge --ff-only origin/wip              # when the branch is only behind
git merge --no-edit <other-branch>          # when both have commits
git update-index --cacheinfo 160000,$(git -C TokenSaver rev-parse HEAD),TokenSaver   # pointer conflict
```

Check the merge before committing: all pointers must match each submodule's `HEAD`, and each
submodule's commits must be on its remote.

## Cleaning up

Delete a branch only after it is merged into `wip` and pushed. Delete the local and remote copies together.
Other branches in the repos (for example `master`, `main`, and feature branches of other work) are not
part of this workflow and stay as they are.

## Checklist

- [ ] Every repo is on `wip` and tracks `origin/wip`.
- [ ] Every submodule's `HEAD` is pushed.
- [ ] The superproject pointers match the submodules' `HEAD`.
- [ ] The superproject `wip` is pushed.

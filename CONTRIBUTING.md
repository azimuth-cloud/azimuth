# Contributing

Documentation fixes, bug reports and code changes are all welcome.
Please check the [issues](https://github.com/azimuth-cloud/azimuth/issues) and [pull requests](https://github.com/azimuth-cloud/azimuth/pulls) before opening a new one.

This repository contains the API, UI and portal Helm chart.
See the [Azimuth organization overview](https://github.com/azimuth-cloud) to find other components.

## Making a contribution

1. Fork the repository and create a branch for your change.
2. Follow the [local development guide](./docs/local-development.md) to install dependencies and check your changes.
   You don't need a cloud account for API tests or UI builds.
   For testing with a running deployment, the guide links to the OpenStack and Tilt setup.
3. Update the docs and tests where needed.
4. Open a pull request explaining the problem, what you changed and how you tested it.
   Mention any integration checks you ran too.

## Local checks

Once you've followed the setup in the [development guide](./docs/local-development.md), run the checks for the parts you changed:

| Change | Check |
| --- | --- |
| API / Python | From the repository root: `uv run --locked tox -e py314,ruff,codespell` |
| UI | From `ui/`: `yarn install --immutable` and `yarn build` |
| Helm templates or values | Run the chart checks below and review any snapshot changes. |
| Documentation | Check links and examples. If you change a command, try running it. |

> [!NOTE]
> Running `uv run tox` also runs `autofix`, which rewrites source files.
> The command above selects just the test and lint environments, so it won't apply fixes.

## CI and fork pull requests

The [Python workflow](./.github/workflows/tox.yaml) runs unit tests and linting.
The [chart workflow](./.github/workflows/helm-lint.yaml) runs chart linting, manifest validation and snapshot checks.
See those files for when each workflow runs.
You can also run the checks locally using the commands on this page.

The [integration workflow](./.github/workflows/test-pr.yaml) provisions an Azimuth deployment using cloud credentials.
For PRs from a fork the PR checks won't run, PRs should be made against a feature branch.
Once merged to an internal branch by a maintainer a second PR will be raised to merge into the default branch and run the full test suite.
This means fork PRs can't complete that workflow.
Include your local check results in the PR, and mention any integration testing that still needs to be done.
Once approved, an internal team member will merge your fork into a feature branch inside the organization and will then complete the testing process to merge into the default branch.

## Helm chart checks and snapshots

From the repository root, with Helm and Docker installed and Docker running:

```sh
helm lint chart -f chart/ci/lint-values.yaml
docker run -i --rm -v "$(pwd):/apps" helmunittest/helm-unittest chart
```

CI uses the Helm [unittest](https://github.com/helm-unittest/helm-unittest) plugin to check for changes to rendered manifests using snapshots.
If the changes are expected, update the snapshots:

```sh
docker run -i --rm -v "$(pwd):/apps" helmunittest/helm-unittest chart -u
```

Review the diff in `chart/tests/__snapshot__/`, commit the expected changes and rerun the command without `-u`.
The chart workflow also validates rendered manifests against Kubernetes schemas.
See the workflow for the full commands.

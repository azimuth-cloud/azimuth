# Setting up a local development environment

You can run the API tests and Python checks, and build the UI locally without OpenStack or Kubernetes.
For testing login, cloud resources and how the components work together, you'll need a running Azimuth deployment.
The Tilt setup for that is covered below.

## Get the code

Clone the repository, or use your fork if you're planning to send a PR:

```sh
git clone https://github.com/azimuth-cloud/azimuth.git
cd azimuth
```

Run these commands from the repository root unless noted otherwise.

## Checks without a cloud

### API tests and Python checks

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and Git.
[pyproject.toml](../pyproject.toml) requires Python 3.12 or newer.
The commands here use Python 3.14, matching [.python-version](../.python-version).
uv can download it if you don't have it installed.

Install the dependencies from the lockfile into `.venv`:

```sh
uv sync --locked
```

Run the unit tests, Ruff lint and formatting checks, and codespell:

```sh
uv run --locked tox -e py314,ruff,codespell
```

The test environments are in [tox.toml](../tox.toml).
Tox runs the tests from `api/` with `DJANGO_SETTINGS_MODULE=tests.settings`.
These [settings](../api/tests/settings.py) skip Kubernetes configuration and use a placeholder OpenStack endpoint.
They're only for tests, so they won't give you a working API to use with the UI.

> [!WARNING]
> Running `uv run tox` also runs `autofix`, which changes source files.
> The command above just checks them.

The API gets its runtime settings from [api/etc/azimuth](../api/etc/azimuth) and the Helm chart.
To run it against a cloud, follow the [Tilt setup](#integration-development-with-openstack-and-tilt) below.

### UI build

Use Node.js 24, the same version as [ui/Dockerfile](../ui/Dockerfile).
You'll also need [Corepack](https://yarnpkg.com/corepack).
Some Node.js installations include it by default.
If yours doesn't, follow the Corepack install instructions.

Enable Corepack and switch to `ui/` before running Yarn so it picks up the project settings:

```sh
corepack enable
cd ui
yarn --version
yarn install --immutable
yarn build
cd ..
```

[ui/package.json](../ui/package.json) pins Yarn 4 in `packageManager` (currently `yarn@4.18.0`).
Corepack picks up that version.
The external development guide still mentions Yarn Classic, but this checkout needs Yarn 4.
`--immutable` prevents changes to [ui/yarn.lock](../ui/yarn.lock) during installation.

Build output goes in `ui/dist/`.
You don't need a running API for this.
There are no separate UI lint or unit-test scripts in `ui/package.json`.

## Integration development with OpenStack and Tilt

The [Azimuth development guide](https://azimuth-config.readthedocs.io/en/stable/developing/) in `azimuth-config` walks through setting up your own development instance and Tilt.
You'll need:

* An OpenStack project with enough quota and an application credential.
* An Azimuth configuration checkout and a running development instance.
* Tilt, Docker or Podman, kubectl and Helm, plus the deployment prerequisites in that guide.
* A container registry accessible to both your machine and the development instance.
* The Node.js and Yarn setup above for local UI development.

Keep this checkout next to your configuration checkout so Tilt can find it:

```text
workspace/
├── azimuth/
└── myorg-azimuth-config/
```

Once you've configured and activated the environment using that guide, run this from the **configuration repository**:

```sh
./bin/tilt-up
```

The settings in [tilt-component.yaml](../tilt-component.yaml) tell Tilt to forward the API to port 8000 and start the UI at `http://localhost:3000`.
[ui/webpack.dev.js](../ui/webpack.dev.js) proxies `/api`, `/auth` and `/static` to `http://127.0.0.1:8000`.

If you've already forwarded the API and Tilt isn't running the UI, you can start it yourself from this checkout:

```sh
cd ui
yarn serve
```

The UI needs a configured API and its backing services for login and cloud operations.
See [CONTRIBUTING.md](../CONTRIBUTING.md) for chart checks and how CI handles fork PRs.

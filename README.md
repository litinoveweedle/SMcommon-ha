# Sequent Home Assistant common library

Shared configuration, entity, and setup code for Sequent Microsystems Home
Assistant custom integrations. The card integrations supply their own domains,
entity maps, hardware APIs, and translations.

The package runs inside Home Assistant and uses its Python APIs. It is tested
with Home Assistant 2026.11; it does not install Home Assistant itself.

## Development and release

Build and install the package in the Python environment used for testing:

```sh
python -m pip install .
```

Install Home Assistant and the integrations' other requirements separately.
For local development, an editable install (`python -m pip install -e .`)
can be used instead.

### Tests and CI

With Python 3.14, install the test dependencies and build and install a wheel:

```sh
python -m pip install build 'homeassistant==2026.11.1' 'pytest-homeassistant==2026.11.1' 'SMioplus>=1.0.0' 'SMmultiio>=1.0.0'
python -m build --wheel
python -m pip install --no-deps dist/*.whl
SMIOPLUS_REPO=/path/to/SMioplus-ha SMMULTIIO_REPO=/path/to/SMmultiio-ha \
  python -m pytest -p no:respx --asyncio-mode=auto -o asyncio_default_fixture_loop_scope=function -q tests
```

The coexistence test requires both checkout paths; it is skipped if neither is
set. Tests simulate hardware and do not require a card. CI builds the wheel and
tests it against pinned commits of both card integrations, using the tests
present at those commits. Each card's CI similarly builds a pinned commit of
this library. Update these checkout refs when coordinating releases or
integration changes; the card workflows also check the built wheel against
their manifest dependency pins.

The integrations currently pin `sequent-ha-common==0.1.0`. Publish that
version to PyPI before releasing integrations that require it; otherwise
Home Assistant cannot install the dependency. When releasing a newer version,
update and test the pins in both integrations together so they can coexist in
the same Home Assistant installation.

The shared datetime platform treats card RTC fields as UTC. It reads the RTC
periodically but never synchronizes it automatically; use Home Assistant's
`datetime.set_value` action or an automation to set it.

### Publishing a release

The GitHub Actions workflow uses PyPI Trusted Publishing; no API token is
needed. Before the first release:

1. Put this library in a GitHub repository and enable GitHub Actions.
2. Create a GitHub Actions environment named `pypi`. Configure required
   reviewers and deployment restrictions where available.
3. In [PyPI publishing settings](https://pypi.org/manage/account/publishing/),
   add a pending publisher for project `sequent-ha-common`, using the actual
   GitHub repository owner and name, workflow `publish-to-pypi.yml`, and
   environment `pypi`. If the project already exists, add the publisher in its
   PyPI project settings instead.

Set the version in `pyproject.toml`, then publish a GitHub release with a tag
matching that version, for example `v0.1.0`. The workflow builds a wheel and
source distribution from that tag, tests the wheel's entity and migration
behavior, and publishes them after the `pypi`
environment's configured approvals. A pending publisher does not reserve the
project name before the first successful upload.

PyPI does not allow replacing an uploaded release file. For a subsequent fix,
publish a new version and update both integrations' pins together.

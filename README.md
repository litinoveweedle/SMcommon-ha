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
set. Tests simulate hardware and do not require a card. CI builds one wheel and
tests it against all 16 card integrations at the current `master` heads, as well
as running the shared and coexistence tests. Card drivers are installed from
their manifests, but their shared-library pins are excluded so CI tests the
wheel under development. Moving branch heads make results non-reproducible
unless the checkout commits are recorded. Each card's own CI installs the
published library from PyPI using its manifest dependency pin.

The integrations pin `sequent-ha-common==0.0.2`. Publish this version to PyPI
before deploying the integrations; otherwise Home Assistant cannot install the
dependency. Update and test all installed integrations' pins together so they
can coexist in the same Home Assistant installation.

The shared datetime platform treats card RTC fields as UTC. It reads the RTC
periodically but never synchronizes it automatically; use Home Assistant's
`datetime.set_value` action or an automation to set it.

### Select entities

For a card with selectable settings, add a `select` section to its entity map:

```python
"select": {
    "type": {
        "chan_no": 8,
        "com": {"get": "get_sensor_type", "set": "set_sensor_type"},
        "option_map": {"B": 0, "K": 3},
    },
},
```

Option labels must be non-empty strings and their driver values must be unique
and hashable. The getter returns a mapped value; the setter accepts one. Both
module APIs (stack argument) and class APIs (constructed with a stack) are
supported, with or without a channel argument. Invalid readings are logged and
shown as unknown; Home Assistant polls the entity for changes.

The card integration must provide its own `select.py` platform wrapper, as with
the other platforms:

```python
from sequent_ha_common.select import async_setup_entry as shared_setup
from . import CARD

async def async_setup_entry(hass, entry, async_add_entities):
    await shared_setup(hass, entry, async_add_entities, CARD)
```

Publish a new library version before requiring select support from PyPI.

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
publish a new version and update the integrations' pins together.

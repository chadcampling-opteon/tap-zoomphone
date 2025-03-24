# tap-zoomphone

`tap-zoomphone` is a Singer tap for Zoom Phone APIs.

Currently supported streams are:
* users
* sms_sessions
* call_history
* call_history_path

Built with the [Meltano Tap SDK](https://sdk.meltano.com) for Singer Taps.

## Configuration

### Accepted Config Options

## Capabilities

* `catalog`
* `state`
* `discover`
* `about`
* `stream-maps`
* `schema-flattening`
* `batch`

## Supported Python Versions

* 3.9
* 3.10
* 3.11
* 3.12
* 3.13

## Settings

| Setting | Required | Default | Description |
|:--------|:--------:|:-------:|:------------|
| client_id | True     | None    | The Client ID for the account_credentials oAuth flow |
| client_secret | True     | None    | The Client Secret for the account_credentials oAuth flow |
| account_id | True     | None    | Required for auth token creation |
| start_date | False    | None    | The earliest record date to sync |
| stream_maps | False    | None    | Config object for stream maps capability. For more information check out [Stream Maps](https://sdk.meltano.com/en/latest/stream_maps.html). |
| stream_map_config | False    | None    | User-defined config values to be used within map expressions. |
| faker_config | False    | None    | Config for the [`Faker`](https://faker.readthedocs.io/en/master/) instance variable `fake` used within map expressions. Only applicable if the plugin specifies `faker` as an additional dependency (through the `singer-sdk` `faker` extra or directly). |
| faker_config.seed | False    | None    | Value to seed the Faker generator for deterministic output: https://faker.readthedocs.io/en/master/#seeding-the-generator |
| faker_config.locale | False    | None    | One or more LCID locale strings to produce localized output for: https://faker.readthedocs.io/en/master/#localization |
| flattening_enabled | False    | None    | 'True' to enable schema flattening and automatically expand nested properties. |
| flattening_max_depth | False    | None    | The max depth to flatten schemas. |
| batch_config | False    | None    | Configuration for BATCH message capabilities. |
| batch_config.encoding | False    | None    | Specifies the format and compression of the batch files. |
| batch_config.encoding.format | False    | None    | Format to use for batch files. |
| batch_config.encoding.compression | False    | None    | Compression format to use for batch files. |
| batch_config.storage | False    | None    | Defines the storage layer to use when writing batch files |
| batch_config.storage.root | False    | None    | Root path to use when writing batch files. |
| batch_config.storage.prefix | False    | None    | Prefix to use when writing batch files. |

A full list of supported settings and capabilities is available by running:
```bash
tap-zoomphone --about
```

### Configure using environment variables

This Singer tap will automatically import any environment variables within the working directory's
`.env` if the `--config=ENV` is provided, such that config values will be considered if a matching
environment variable is set either in the terminal context or in the `.env` file.

## Usage

You can easily run `tap-zoomphone` by itself or in a pipeline using [Meltano](https://meltano.com/).

### Executing the Tap Directly

```bash
tap-zoomphone --version
tap-zoomphone --help
tap-zoomphone --config CONFIG --discover > ./catalog.json
```

## Developer Resources

Follow these instructions to contribute to this project.

### Initialize your Development Environment

Prerequisites:

- Python 3.9+
- [uv](https://docs.astral.sh/uv/)

```bash
uv sync
```

### Create and Run Tests

Create tests within the `tests` subfolder and
  then run:

```bash
uv run pytest
```

You can also test the `tap-zoomphone` CLI interface directly using `uv run`:

```bash
uv run tap-zoomphone --help
```

### Testing with [Meltano](https://www.meltano.com)

_**Note:** This tap will work in any Singer environment and does not require Meltano.
Examples here are for convenience and to streamline end-to-end orchestration scenarios._

Next, install Meltano (if you haven't already) and any needed plugins:

```bash
# Install meltano
pipx install meltano
# Initialize meltano within this directory
cd tap-zoomphone
meltano install
```

Now you can test and orchestrate using Meltano:

```bash
# Test invocation:
meltano invoke tap-zoomphone --version

# OR run a test ELT pipeline:
meltano run tap-zoomphone target-jsonl
```

### SDK Dev Guide

See the [dev guide](https://sdk.meltano.com/en/latest/dev_guide.html) for more instructions on how to use the SDK to
develop your own taps and targets.

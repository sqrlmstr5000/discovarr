
## Install Python Dependencies
```
python -m venv ~/venv/discovarr
source ~/venv/discovarr/bin/activate
pip install -r server/src/requirements.txt
```

## Run Tests
```
cd server/src
source env.sh
pytest -s --log-cli-level=DEBUG tests/integration/test_trakt_provider.py

pytest -s --log-cli-level=DEBUG tests/integration/test_trakt_provider.py::TestTraktProviderLive::test_get_items_filtered_from_live_history
```
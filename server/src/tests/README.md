
## Set Environment Variables
```
export LOGLEVEL=DEBUG
export TRAKT_TEST_CLIENT_ID=1365e909d1a2591303d55b3e692c96ff807794dfe5f2354a6fb13fe10aa8d598
export TRAKT_TEST_CLIENT_SECRET=aec97de0a25e2ce3146c759d0f852d0877e90cba705d7ae858953f501e4614b7
export TRAKT_TEST_REDIRECT_URI="urn:ietf:wg:oauth:2.0:oob" 
export TRAKT_TEST_AUTH_JSON='{"access_token": "", "token_type": "bearer", "expires_in": 7776000, "refresh_token": "", "scope": "public", "created_at": 1749517164}'
```

## Run Tests
```
cd server/src
pytest -s --log-cli-level=DEBUG tests/integration/test_trakt_provider.py

pytest -s --log-cli-level=DEBUG tests/integration/test_trakt_provider.py::TestTraktProviderLive::test_get_items_filtered_from_live_history
```
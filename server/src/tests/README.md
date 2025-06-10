
## Set Environment Variables
```
export LOGLEVEL=DEBUG
export TRAKT_TEST_CLIENT_ID=1365e909d1a2591303d55b3e692c96ff807794dfe5f2354a6fb13fe10aa8d598
export TRAKT_TEST_CLIENT_SECRET=aec97de0a25e2ce3146c759d0f852d0877e90cba705d7ae858953f501e4614b7
export TRAKT_TEST_REDIRECT_URI="urn:ietf:wg:oauth:2.0:oob" 
export TRAKT_TEST_AUTH_JSON='{"access_token": "7c75729a3e60a5d00d3e28c71f7936f78d34422020e386169a68f2e64ed98d51", "token_type": "bearer", "expires_in": 7776000, "refresh_token": "313eafd182d5e34ebe647b0e3671639975f2104d0a88aaa51a779daae756669e", "scope": "public", "created_at": 1749517164}'
```

## Run Tests
```
cd server/src
pytest -s --log-cli-level=DEBUG tests/integration/test_trakt_provider.py
```
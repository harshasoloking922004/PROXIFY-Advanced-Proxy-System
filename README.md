# Advanced Proxy System

## Run
Install dependencies:
```powershell
python -m pip install -r requirements.txt
```

Start dashboard/server:
```powershell
python -m gui.server_dashboard
```
Click **Start Server**.

## TCP handshake test
```powershell
python client/test_connection.py
```

## Webpage fetch test
```powershell
python client/fetch_test.py
```
Or supply a URL:
```powershell
python client/fetch_test.py https://www.python.org
```

The fetch test downloads HTML through the local proxy server and saves it under `saved_pages/`.

## Implemented
- Dark dashboard UI
- TCP socket server
- Bounded worker thread pool
- Thread-safe session tracking and metrics
- HTTP/HTTPS HTML fetch with size and timeout limits
- Public-destination URL validation and redirect validation
- Test clients for TCP handshake and webpage fetching

## Security notes
The server binds to 127.0.0.1 by default. It only fetches HTTP/HTTPS on standard ports and blocks non-public IP destinations. Do not expose this development server to the public internet.

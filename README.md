# PROXIFY – Advanced Proxy Server and Client

### Multi-threaded Proxy System using Python, TCP Socket Programming and SQLite

![Python](https://img.shields.io/badge/Python-3.12-blue)
![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey)
![Database](https://img.shields.io/badge/Database-SQLite-green)
![Project](https://img.shields.io/badge/Project-Operating%20Systems-orange)

## 1. Project Overview

**PROXIFY** is an Advanced Multi-threaded Proxy Server and Client application developed as part of an Operating Systems project.

A proxy server acts as an intermediary between a client and an external web server. In this project, the client sends a webpage URL to the proxy server through TCP socket communication. The proxy server processes the request, fetches the webpage content, and sends the response back to the client.

The client then decodes the received content and automatically saves it as an HTML file with an appropriate filename.

The project also includes a graphical monitoring dashboard that displays server activity, request statistics, traffic information, and performance metrics.

## 2. Problem Statement

"Multi-threaded Proxy Server and Client: Develop a multi-threaded proxy server and client. The server accepts any URL from the client, fetches output, returns it to the client. The client should save output into HTML page with an appropriate name."

## 3. Project Objectives

- Develop a TCP-based proxy server and client.
- Implement concurrent request processing using multithreading.
- Fetch webpage content from HTTP and HTTPS URLs.
- Establish reliable communication between clients and the server.
- Automatically save retrieved webpage content as HTML files.
- Maintain request history using an SQLite database.
- Develop a graphical dashboard for monitoring proxy operations.

## 4. Key Features

### Multi-threaded Server
- Uses Python's `ThreadPoolExecutor`.
- Configured with a maximum of 20 worker threads.
- Processes multiple client requests concurrently.

### TCP Socket Communication
- Uses TCP sockets for client-server communication.
- Implements JSON-based request and response messages.
- Uses a 4-byte length prefix for message framing.

### Webpage Fetching
- Supports HTTP and HTTPS webpage requests.
- Retrieves HTML and XHTML content.
- Includes URL validation, timeouts, and error handling.

### Automatic HTML File Generation
- Receives webpage content from the proxy server.
- Decodes Base64-encoded response data.
- Generates filenames based on the requested URL.
- Saves the retrieved webpages in the `saved_pages` directory.

### SQLite Database
- Maintains persistent request history.
- Stores information used for historical monitoring and analytics.

### PROXIFY Monitoring Dashboard
- Displays total requests and successful requests.
- Shows success rate and latency information.
- Monitors incoming and outgoing traffic.
- Displays request distribution and recent activity.
- Provides historical analytics and CSV export functionality.

## 5. Technology Stack

| Technology | Purpose |
|---|---|
| Python 3.12 | Core programming language |
| Socket | TCP client-server communication |
| ThreadPoolExecutor | Concurrent request processing |
| JSON | Request and response serialization |
| Base64 | Response content encoding |
| SQLite | Request history storage |
| CustomTkinter | Graphical dashboard |
| Matplotlib | Charts and traffic visualization |
| Certifi | SSL certificate support |
| VS Code | Development environment |

## 6. System Architecture

The system consists of the following major components:

1. **Client Application:** Accepts webpage URLs, communicates with the proxy server, and saves received content as HTML files.
2. **TCP Communication Layer:** Establishes reliable communication between the client and server.
3. **Proxy Server:** Receives requests, validates URLs, and fetches webpage content.
4. **Thread Pool:** Handles multiple client requests concurrently.
5. **External Web Server:** Provides the requested webpage content.
6. **SQLite Database:** Maintains persistent request history.
7. **PROXIFY Dashboard:** Displays server activity and performance statistics.

### Request Processing Flow

```text
        CLIENT
           |
           | Enter Website URL
           |
           v
      TCP SOCKET
           |
           v
      PROXY SERVER
           |
           v
      URL VALIDATION
           |
           v
      THREAD POOL
           |
           v
   EXTERNAL WEB SERVER
           |
           | Fetch HTML Content
           |
           v
      PROXY SERVER
           |
           | JSON Response
           |
           v
         CLIENT
           |
           v
    HTML FILE GENERATION
           |
           v
      SAVED_PAGES/
```

## 7. Project Folder Structure

```text
PROXIFY-Advanced-Proxy-System/
│
├── client/
│   ├── __init__.py
│   ├── fetch_test.py
│   └── test_connection.py
│
├── server/
│   ├── __init__.py
│   └── proxy_server.py
│
├── gui/
│   ├── __init__.py
│   └── server_dashboard.py
│
├── database/
│   ├── __init__.py
│   └── request_store.py
│
├── saved_pages/
│
├── logs/
│
├── reports/
│
├── concurrent_test.py
├── test_30_urls.py
├── requirements.txt
├── README.md
└── .gitignore
```

*Note: Generated HTML files, local database files, logs, and virtual environment files are excluded from Git using `.gitignore`.*

## 8. Installation and Setup

### Prerequisites

- Windows 10 or Windows 11
- Python 3.12 or compatible Python version
- Visual Studio Code
- Git

### Step 1: Clone the Repository

Open the terminal and execute:

```bash
git clone https://github.com/harshasoloking922004/PROXIFY-Advanced-Proxy-System.git
```

### Step 2: Navigate to the Project Folder

```bash
cd PROXIFY-Advanced-Proxy-System
```

### Step 3: Create a Virtual Environment

```bash
python -m venv .venv
```

### Step 4: Activate the Virtual Environment

For Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

### Step 5: Install Dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## 9. How to Run the Project

### Step 1: Start the Dashboard

From the project root directory, execute:

```bash
python -m gui.server_dashboard
```

The PROXIFY graphical dashboard will open.

### Step 2: Start the Proxy Server

Click the **Start Server** button on the dashboard.

The server will start listening for incoming client connections.

### Step 3: Open a Second Terminal

Navigate to the project directory:

```bash
cd PROXIFY-Advanced-Proxy-System
```

Activate the virtual environment:

```powershell
.\.venv\Scripts\Activate.ps1
```

### Step 4: Send a Client Request

Execute:

```bash
python client/fetch_test.py https://example.com
```

The client sends the URL to the proxy server, receives the webpage content, and saves it as an HTML file.

### Step 5: View Saved Webpages

```powershell
explorer .\saved_pages
```

## 10. Testing

The project includes different testing procedures to verify its functionality.

### Single Client Testing

```bash
python client/fetch_test.py https://example.com
```

Additional test URLs:

```bash
python client/fetch_test.py https://www.python.org
python client/fetch_test.py https://www.wikipedia.org
python client/fetch_test.py https://www.mozilla.org
```

### Concurrent Client Testing

```bash
python concurrent_test.py
```

The concurrent test was successfully executed with five simultaneous clients.

**Observed Result:**

| Parameter | Result |
|---|---:|
| Total Clients | 5 |
| Successful Requests | 5 |
| Failed Requests | 0 |

### Multiple URL Testing

```bash
python test_30_urls.py
```

This script attempts webpage fetching using 30 different URLs and reports the individual results.

The success rate may vary depending on website availability, server restrictions, network connectivity, and supported response content.

## 11. Database Management

The project uses SQLite to maintain request history.

**Database Location:**

```text
database/proxy_history.db
```

The database supports:

- Persistent request history.
- Request-related information storage.
- Historical dashboard analytics.

SQLite does not require a separate database server.

## 12. Security and Implementation Limitations

The current implementation includes several safeguards:

- Validates destination URLs.
- Restricts fetching to public destination IP addresses.
- Allows standard HTTP and HTTPS ports (80 and 443).
- Revalidates redirected destinations.
- Uses a 12-second request timeout.
- Limits HTML response bodies to 5 MB.
- Accepts HTML/XHTML response content.

**Important:** This is an academic project implementation. It is not intended to be used as a production-grade public proxy service.

## 13. Future Enhancements

- Implement webpage caching.
- Add user authentication and authorization.
- Support additional response content types.
- Improve traffic analysis and reporting.
- Add configurable worker thread management.
- Introduce advanced security monitoring.
- Develop a browser-based dashboard.
- Deploy the system on a cloud platform.

## 14. Learning Outcomes

Through this project, we gained practical knowledge of:

- Operating Systems concepts.
- Process and thread management.
- Multithreading and concurrency.
- TCP socket programming.
- Client-server architecture.
- Synchronization and shared resources.
- Database integration.
- Graphical user interface development.
- Network request processing.

## 15. Project Team Members

| S.No | Name | Roll Number |
|---|---|---|
| 1 | B. Harsha | AP24110011355 |
| 2 | M. Siva | AP24110011328 |
| 3 | B. Jay Sai Raj | AP24110011425 |

## 16. Conclusion

PROXIFY demonstrates the implementation of a multi-threaded proxy server and client using Python and TCP socket programming.

The system retrieves supported webpage content through a proxy server, returns the response to the client, and automatically generates HTML files. Multithreading enables concurrent client request processing, while SQLite maintains request history.

The graphical PROXIFY dashboard provides a convenient way to monitor server activity, traffic information, and performance statistics.

This project provides practical experience in networking, concurrency, socket programming, database management, and important Operating Systems concepts.

---

## GitHub Repository

**Repository:** https://github.com/harshasoloking922004/PROXIFY-Advanced-Proxy-System

**Project Name:** PROXIFY – Advanced Proxy Server and Client

**Developed as an Operating Systems Academic Project.**

---

**Thank You!**

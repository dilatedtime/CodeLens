"""Sample Vulnerable Microservice for CodeLens Security & Code Quality Audit.

Contains intentional vulnerabilities across OWASP Top 10 categories:
- A03: Injection (SQL Injection, Command Injection)
- A08: Software and Data Integrity Failures (Insecure Deserialization via pickle)
- A07: Identification and Authentication Failures (Hardcoded Credentials)
- A01: Broken Access Control (Path Traversal)
- Common Python Pitfalls (Mutable default argument)
"""

import os
import pickle
import sqlite3
import subprocess

# 1. Hardcoded Secret Token (SEC001 / CWE-798)
API_SECRET_KEY = "dummy_insecure_auth_token_sample_key_998877"


# 2. Dangerous Mutable Default Argument (B006)
def register_user(username, roles=[]):
    """Registers a user with roles, but mutates shared default list."""
    roles.append("member")
    return {"user": username, "roles": roles}


# 3. SQL Injection via string formatting (B608 / CWE-89)
def query_user_by_name(cursor: sqlite3.Cursor, user_input: str):
    """Vulnerable to SQL Injection via direct f-string interpolation."""
    query = f"SELECT id, username, email FROM users WHERE username = '{user_input}'"
    cursor.execute(query)
    return cursor.fetchall()


# 4. Command Injection via shell=True (B602 / CWE-78)
def ping_host(host_ip: str):
    """Vulnerable to Command Injection when host_ip contains metacharacters (e.g. 127.0.0.1; whoami)."""
    cmd = f"ping -c 1 {host_ip}"
    return subprocess.check_output(cmd, shell=True)


# 5. Insecure Deserialization via pickle.loads (B301 / CWE-502)
def load_session(serialized_data: bytes):
    """Vulnerable to arbitrary remote code execution via malicious pickle payload."""
    return pickle.loads(serialized_data)


# 6. Path Traversal File Access (CWE-22)
def read_log_file(filename: str):
    """Vulnerable to directory traversal (e.g., ../../etc/passwd)."""
    log_dir = "/var/log/app"
    filepath = os.path.join(log_dir, filename)
    with open(filepath, "r") as f:
        return f.read()


# 7. Bare except clause masking interrupts (ERR001)
def safe_parse(value: str):
    try:
        return int(value)
    except:
        return 0

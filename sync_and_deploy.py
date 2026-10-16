import os
import shutil
import json
import ssl
import subprocess
import urllib.request
import urllib.parse
from pathlib import Path

# Paths
base_dir = Path(__file__).resolve().parent

# Run node build.js first to ensure bundle is fresh
print("Running node build.js...")
subprocess.run(["node", "build.js"], cwd=base_dir, check=True)

worker_file = base_dir / "dist" / "worker.js"
with open(worker_file, "r", encoding="utf-8") as f:
    worker_script = f.read()

print(f"✓ Loaded worker script from {worker_file} ({len(worker_script)} bytes)")

# Refresh Cloudflare OAuth token
wrangler_config = Path.home() / ".wrangler/config/default.toml"
cf_token = None
refresh_token = None

if wrangler_config.exists():
    with open(wrangler_config, "r", encoding="utf-8") as f:
        config_text = f.read()
        for line in config_text.splitlines():
            if line.strip().startswith("oauth_token"):
                cf_token = line.split("=")[1].strip().strip('"')
            if line.strip().startswith("refresh_token"):
                refresh_token = line.split("=")[1].strip().strip('"')

ctx = ssl._create_unverified_context()

# If refresh token exists, refresh it now
if refresh_token:
    try:
        print("Refreshing Cloudflare OAuth token...")
        refresh_req_data = urllib.parse.urlencode({
            "grant_type": "refresh_token",
            "client_id": "54d11594-84e4-413e-b418-e4d847e9d7e0",
            "refresh_token": refresh_token
        }).encode("utf-8")
        refresh_req = urllib.request.Request(
            "https://dash.cloudflare.com/oauth2/token",
            data=refresh_req_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        with urllib.request.urlopen(refresh_req, context=ctx) as resp:
            token_data = json.loads(resp.read().decode("utf-8"))
            if "access_token" in token_data:
                cf_token = token_data["access_token"]
                new_refresh = token_data.get("refresh_token", refresh_token)
                print("✓ Successfully refreshed Cloudflare OAuth access token!")
                
                # Update default.toml
                import re
                updated_toml = re.sub(r'oauth_token\s*=\s*"[^"]+"', f'oauth_token = "{cf_token}"', config_text)
                if new_refresh:
                    updated_toml = re.sub(r'refresh_token\s*=\s*"[^"]+"', f'refresh_token = "{new_refresh}"', updated_toml)
                with open(wrangler_config, "w", encoding="utf-8") as wf:
                    wf.write(updated_toml)
    except Exception as e:
        print(f"Notice: token refresh attempt: {e}")

account_id = "c1ed3a128361abb909218d88d7f72492"
script_name = "maplemanorsb"

metadata = {
    "main_module": "index.js",
    "compatibility_date": "2024-01-01"
}

boundary = "----FormBoundary1234567890"
body_parts = [
    f"--{boundary}".encode("utf-8"),
    b'Content-Disposition: form-data; name="metadata"',
    b"Content-Type: application/json",
    b"",
    json.dumps(metadata).encode("utf-8"),
    f"--{boundary}".encode("utf-8"),
    b'Content-Disposition: form-data; name="index.js"; filename="index.js"',
    b"Content-Type: application/javascript+module",
    b"",
    worker_script.encode("utf-8"),
    f"--{boundary}--".encode("utf-8")
]
body = b"\r\n".join(body_parts)

url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/workers/scripts/{script_name}"
req = urllib.request.Request(
    url,
    data=body,
    headers={
        "Authorization": f"Bearer {cf_token}",
        "Content-Type": f"multipart/form-data; boundary={boundary}"
    },
    method="PUT"
)

try:
    with urllib.request.urlopen(req, context=ctx) as response:
        res = json.loads(response.read().decode("utf-8"))
        print("CLOUDFLARE DEPLOY RESULT:", res.get("success"))
        if res.get("success"):
            print(f"✓ Successfully deployed Worker: {script_name}")
        else:
            print("Deploy errors:", res.get("errors"))
except Exception as e:
    print(f"Deploy Error: {e}")

# Enable workers.dev subdomain if needed
try:
    subdomain_url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/workers/scripts/{script_name}/subdomain"
    sub_data = json.dumps({"enabled": True}).encode("utf-8")
    sub_req = urllib.request.Request(
        subdomain_url,
        data=sub_data,
        headers={
            "Authorization": f"Bearer {cf_token}",
            "Content-Type": "application/json"
        },
        method="POST"
    )
    with urllib.request.urlopen(sub_req, context=ctx) as sub_resp:
        sub_res = json.loads(sub_resp.read().decode("utf-8"))
        print("WORKERS.DEV SUBDOMAIN ENABLED:", sub_res.get("success"))
except Exception as e:
    print(f"Subdomain notice: {e}")

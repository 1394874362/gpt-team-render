
# Proxy Configuration
PROXY_HOST = "170.130.97.208"
PROXY_PORT = "443"
PROXY_USER = "JgshZqSGcwhW" 
PROXY_PASS = "8avHcan293"
PROXY_URL = f"socks5://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}"

# Helper for requests
PROXIES = {
    "http": PROXY_URL,
    "https": PROXY_URL
}

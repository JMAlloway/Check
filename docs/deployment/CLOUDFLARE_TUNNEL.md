# Cloudflare Tunnel Setup for Remote Demo Access

This guide explains how to use Cloudflare Tunnel to access the Check Review Console demo remotely without exposing ports or configuring firewalls.

## Overview

Cloudflare Tunnel creates an encrypted outbound connection from your local machine to Cloudflare's network, allowing secure remote access without:
- Opening firewall ports
- Configuring port forwarding
- Managing SSL certificates
- Exposing your IP address

## Quick Start (Temporary URL)

For quick demos or testing, use a temporary tunnel that requires no Cloudflare account:

```bash
cd docker

# Start the application with quick tunnel
docker compose -f docker-compose.yml -f docker-compose.tunnel.yml --profile quick-tunnel up
```

Watch the logs for the cloudflared container - it will output a temporary URL like:
```
check_review_tunnel  | Your quick Tunnel has been created! Visit it at:
check_review_tunnel  | https://random-words-here.trycloudflare.com
```

Share this URL for remote demo access. The URL expires when you stop the container.

## Named Tunnel (Persistent URL)

For a persistent URL with your own domain, create a named tunnel.

### Prerequisites

1. A Cloudflare account (free tier works)
2. A domain added to Cloudflare (for custom hostname)
3. `cloudflared` CLI installed locally

### Step 1: Install cloudflared

```bash
# macOS
brew install cloudflared

# Linux (Debian/Ubuntu)
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb -o cloudflared.deb
sudo dpkg -i cloudflared.deb

# Linux (other)
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o cloudflared
chmod +x cloudflared
sudo mv cloudflared /usr/local/bin/
```

### Step 2: Authenticate with Cloudflare

```bash
cloudflared tunnel login
```

This opens a browser to authenticate and creates `~/.cloudflared/cert.pem`.

### Step 3: Create a Tunnel

```bash
cloudflared tunnel create check-demo
```

This outputs:
- A tunnel UUID
- Creates a credentials file at `~/.cloudflared/<UUID>.json`

### Step 4: Configure DNS

Route your domain to the tunnel:

```bash
cloudflared tunnel route dns check-demo demo.yourdomain.com
```

### Step 5: Get Tunnel Token

```bash
cloudflared tunnel token check-demo
```

Copy the token output.

### Step 6: Run with Docker Compose

**Option A: Using environment variable**

```bash
cd docker
export TUNNEL_TOKEN="<your-token-from-step-5>"
docker compose -f docker-compose.yml -f docker-compose.tunnel.yml --profile named-tunnel up
```

Or add to your `.env` file:
```
TUNNEL_TOKEN=<your-token-from-step-5>
```

**Option B: Using config file**

1. Copy the config template:
   ```bash
   cp cloudflared/config.yml.example cloudflared/config.yml
   ```

2. Edit `cloudflared/config.yml` with your tunnel UUID and hostname

3. Copy your credentials file:
   ```bash
   cp ~/.cloudflared/<UUID>.json docker/cloudflared/credentials.json
   ```

4. Run:
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.tunnel.yml --profile config-tunnel up
   ```

## Configuration Options

### Ingress Rules

The config file supports path-based routing to different services:

```yaml
ingress:
  # API requests go to backend
  - hostname: demo.yourdomain.com
    path: /api/*
    service: http://backend:8000

  # Everything else goes to frontend
  - hostname: demo.yourdomain.com
    service: http://frontend:3000

  # Required catch-all
  - service: http_status:404
```

### Multiple Hostnames

You can route multiple domains through one tunnel:

```yaml
ingress:
  - hostname: demo.yourdomain.com
    service: http://frontend:3000
  - hostname: api.yourdomain.com
    service: http://backend:8000
  - service: http_status:404
```

## Security Considerations

1. **Demo Mode**: Enable `DEMO_MODE=true` for demo data, but never use in production
2. **Credentials**: Never commit `credentials.json` or `TUNNEL_TOKEN` to version control
3. **Access Control**: Consider using Cloudflare Access to add authentication
4. **Monitoring**: Monitor tunnel connections in the Cloudflare Zero Trust dashboard

## Troubleshooting

### Tunnel not connecting

Check cloudflared logs:
```bash
docker compose logs cloudflared-quick  # or cloudflared / cloudflared-config
```

### 502 Bad Gateway

The upstream service (frontend/backend) may not be ready. Ensure services are healthy:
```bash
docker compose ps
```

### API requests failing

Ensure CORS is configured for your tunnel domain. Update `CORS_ORIGINS` in your `.env`:
```
CORS_ORIGINS='["https://demo.yourdomain.com"]'
```

### Quick tunnel URL not showing

The URL appears in container logs. View with:
```bash
docker compose logs -f cloudflared-quick
```

## Additional Resources

- [Cloudflare Tunnel Documentation](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/)
- [Cloudflare Access](https://developers.cloudflare.com/cloudflare-one/policies/access/) - Add authentication to your tunnel
- [Zero Trust Dashboard](https://one.dash.cloudflare.com/) - Manage tunnels and access policies

# Docker Deployment Guide for ActivityWatch Remote Server

This guide provides instructions for deploying ActivityWatch server in Docker containers for remote monitoring setups.

## Quick Start

### 1. Build the Docker Image

```bash
docker compose -f docker-compose.remote.yml build
```

### 2. Start the Server

```bash
docker compose -f docker-compose.remote.yml up -d
```

### 3. Verify the Server is Running

```bash
# Check logs
docker compose -f docker-compose.remote.yml logs -f aw-server-remote

# Test the API
curl http://localhost:5600/api/
```

### 4. Connect a Remote Client

On a different machine:

```bash
export AW_SERVER_HOST=your.server.com
export AW_SERVER_PORT=5600
export AW_SERVER_API_KEY=your_api_key
aw-client heartbeat bucket_name '{"data":"value"}'
```

## Configuration

### Environment Variables

Configure the server via environment variables:

```bash
# Host to listen on (default: 127.0.0.1)
AW_SERVER_HOST=0.0.0.0

# Port to listen on (default: 5600)
AW_SERVER_PORT=5600

# Log level (default: info)
AW_LOG_LEVEL=debug

# Optional: API key for authentication
AW_SERVER_API_KEY=your_secure_api_key
```

### Using .env File

Create a `.env` file in the same directory as `docker-compose.remote.yml`:

```bash
AW_SERVER_HOST=0.0.0.0
AW_SERVER_PORT=5600
AW_LOG_LEVEL=info
AW_SERVER_API_KEY=your_strong_api_key_here
```

Then start with:

```bash
docker compose -f docker-compose.remote.yml up -d
```

## Production Deployment

### 1. Use a Reverse Proxy (SSL/TLS)

**Important**: Never expose ActivityWatch directly to the internet without SSL/TLS.

Use Nginx with SSL termination:

```bash
# Configure nginx.conf.example with your domain
cp nginx.conf.example nginx.conf
# Edit nginx.conf and set server_name to your domain

# Generate SSL certificates (using Let's Encrypt)
docker run --rm -it -v $(pwd)/certs:/etc/letsencrypt \
  certbot/certbot certonly --standalone -d your.server.com

# Uncomment the aw-proxy service in docker-compose.remote.yml
# Then start both services
docker compose -f docker-compose.remote.yml up -d
```

### 2. Set a Strong API Key

```bash
# Generate a strong API key
openssl rand -base64 32

# Add to .env file
echo "AW_SERVER_API_KEY=$(openssl rand -base64 32)" >> .env
```

### 3. Configure Firewall

Only allow necessary ports:

```bash
# Allow SSH
sudo ufw allow 22/tcp

# Allow HTTPS
sudo ufw allow 443/tcp

# Allow HTTP (for Let's Encrypt renewal)
sudo ufw allow 80/tcp

# Deny ActivityWatch direct access
# (should only be accessible through reverse proxy)
```

### 4. Data Persistence

The Docker Compose setup includes a volume for data persistence:

```yaml
volumes:
  aw-data:
    driver: local
```

Data is stored at `/data` inside the container and persists across restarts.

### 5. Monitoring

Check logs:

```bash
docker compose -f docker-compose.remote.yml logs -f aw-server-remote
```

Health status:

```bash
docker compose -f docker-compose.remote.yml ps
```

## Multi-Machine Setup Example

### Server Machine

```bash
# On server.example.com
export AW_SERVER_HOST=0.0.0.0
export AW_SERVER_PORT=5600
export AW_SERVER_API_KEY=$(openssl rand -base64 32)
docker compose -f docker-compose.remote.yml up -d
```

### Client Machine 1

```bash
# On laptop.example.com
export AW_SERVER_HOST=server.example.com
export AW_SERVER_PORT=5600
export AW_SERVER_API_KEY=your_api_key
aw-client heartbeat laptop '{"app":"VS Code"}'
```

### Client Machine 2

```bash
# On desktop.example.com
export AW_SERVER_HOST=server.example.com
export AW_SERVER_PORT=5600
export AW_SERVER_API_KEY=your_api_key
aw-client heartbeat desktop '{"app":"Browser"}'
```

## Troubleshooting

### Server won't start

```bash
docker compose -f docker-compose.remote.yml logs aw-server-remote
```

Look for error messages and check:
- Port is not already in use
- Firewall allows the port
- Sufficient disk space for data

### Can't connect from remote client

```bash
# Check server is running
curl -v http://your.server.com:5600/api/

# Verify connectivity from client
curl -v http://your.server.com:5600/api/
ping your.server.com

# Check API key (if set)
curl -H "Authorization: Bearer $AW_SERVER_API_KEY" http://your.server.com:5600/api/
```

### SSL/TLS certificate issues

```bash
# Renew Let's Encrypt certificates
docker run --rm -it -v $(pwd)/certs:/etc/letsencrypt \
  certbot/certbot renew

# Restart the proxy
docker compose -f docker-compose.remote.yml restart aw-proxy
```

### Performance issues

1. Increase container resources in docker-compose.remote.yml
2. Check host system resources (CPU, memory, disk)
3. Reduce log level from `debug` to `info`

## Security Best Practices

✅ **DO:**
- Always use HTTPS/SSL in production
- Set a strong API key
- Use firewall to restrict access
- Keep containers updated
- Monitor logs for suspicious activity
- Use non-root user (already configured)
- Store .env file securely

❌ **DON'T:**
- Expose server directly without SSL
- Use weak API keys
- Leave firewall open to all traffic
- Run as root user
- Store API keys in version control
- Use self-signed certificates in production
- Log sensitive data

## Advanced: Custom Dockerfile

If you need to customize the image:

```dockerfile
FROM activitywatch:remote-latest

# Add your customizations here
RUN apt-get update && apt-get install -y custom-tool

ENTRYPOINT ["/app/entrypoint.sh"]
```

Build with:

```bash
docker build -f Dockerfile.custom -t activitywatch:custom .
```

## Environment Variable Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `AW_SERVER_HOST` | `127.0.0.1` | Host to listen on (use `0.0.0.0` for remote) |
| `AW_SERVER_PORT` | `5600` | Port to listen on |
| `AW_LOG_LEVEL` | `info` | Log level (debug, info, warn, error) |
| `AW_SERVER_API_KEY` | (empty) | Optional API key for authentication |
| `AW_DATA_DIR` | `/data` | Data storage directory |

## Resources

- [Docker Documentation](https://docs.docker.com/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [Nginx Documentation](https://nginx.org/en/docs/)
- [Let's Encrypt](https://letsencrypt.org/)
- [ActivityWatch Documentation](https://docs.activitywatch.net)
- [Remote Connections Guide](../docs/REMOTE_CONNECTIONS.md)

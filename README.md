# Talaria

A containerized URL shortening service built with Node.js, Redis, Docker, and Kubernetes that allows users to submit long URLs and receive shortened versions.

## Overview

This project demonstrates a complete cloud-native URL shortening service with:

- Containerized microservice architecture
- RESTful API for URL shortening
- Redis for fast in-memory storage
- Kubernetes deployment with scalability features
- Load testing capabilities

## Architecture

The system consists of two main components:

1. **URL Shortener Service**: Node.js application that handles URL shortening logic
2. **Redis**: In-memory database that stores the mapping between short and long URLs

## API Endpoints

| Endpoint      | Method | Description                  | Request Body                               | Response                                                             |
| ------------- | ------ | ---------------------------- | ------------------------------------------ | -------------------------------------------------------------------- |
| `/shorten`    | POST   | Create a shortened URL       | `{"url": "https://example.com/long/path"}` | `{"shortened_url": "http://host:port/abC123"}`                       |
| `/:shortCode` | GET    | Redirect to the original URL | -                                          | HTTP Redirect                                                        |
| `/health`     | GET    | Health check endpoint        | -                                          | `{"status": "healthy", "redis": "connected", "appVersion": "1.0.0"}` |

## Prerequisites

- Docker Desktop
- Minikube
- kubectl
- PowerShell (for Windows users)

## Setup and Deployment

### Building the Docker Image

```bash
# Navigate to the project directory
cd cloud_url_shortener

# Build the Docker image
./build-docker.ps1
```

The script builds a Docker image with the tag `urlshortener:latest`.

### Deploying to Kubernetes

```bash
# Start Minikube if not running
minikube start

# Load the Docker image into Minikube
minikube image load urlshortener:latest

# Deploy the application to Kubernetes
./setup.ps1
```

The setup script will:

1. Install MetalLB (load balancer)
2. Create Kubernetes resources (deployments, services, etc.)
3. Wait for all services to be ready

### Accessing the Service

```bash
# Create a tunnel to access the service
minikube service urlshortener
```

The service will be accessible at the URL provided by Minikube (typically something like `http://127.0.0.1:xxxxx`).

## Using the Service

### Shortening a URL

Send a POST request to the `/shorten` endpoint:

```json
{
  "url": "https://advay-sanketi-portfolio.vercel.app/"
}
```

The service will respond with:

```json
{
  "shortened_url": "http://host:port/AbCdEfGh"
}
```

### Accessing a Shortened URL

Simply navigate to the shortened URL in a browser, and you'll be redirected to the original URL.

## Scaling

The service is configured with a Horizontal Pod Autoscaler (HPA) to scale based on CPU usage:

```bash
# View the current state of the deployment
kubectl get all
```

The autoscaler maintains between 2-5 pods based on load, with a target CPU utilization of 70%.

## Monitoring

### Health Checks

```bash
# Access the health endpoint
curl http://host:port/health
```

Expected response:

```json
{
  "status": "healthy",
  "redis": "connected",
  "appVersion": "1.0.0",
  "timestamp": "2025-04-07T21:51:57.046Z"
}
```

### Logs

```bash
# View logs for the URL shortener pods
kubectl logs -f -l app=urlshortener
```

## Load Testing

The project includes a load testing script:

```bash
# Run the load test
cd url-shortener-load-test
./run-load-test.bat
```

The test will generate a report with metrics including:

- Average response time
- Total number of requests processed
- Performance graphs

## Cleanup

To remove all resources from your Kubernetes cluster:

```bash
./cleanup.ps1
```

This script will delete all Kubernetes resources created for this project.

## Performance Metrics

During load testing, the system achieved:

- Average response time: ~687ms
- Successfully processed over 6,800 requests
- Auto-scaled from 2 to 3 pods at peak load

## Technical Details

- **Node.js Version**: 20-alpine
- **Redis Version**: 7.4.2
- **Kubernetes Version**: 1.32.0
- **Docker Version**: 27.4.1

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contributors

- Advay Sanketi - [Portfolio](https://advay-sanketi-portfolio.vercel.app/)

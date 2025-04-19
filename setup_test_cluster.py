import os
import subprocess
import time
import yaml
import json
import random
import string

# Use the full paths to kubectl and kind in the Replit environment
KUBECTL = "/nix/store/05k95p72niq1gh39gv1g9n0ivsgl4hiy-kubectl-1.30.1/bin/kubectl"
KIND = "/nix/store/8if8dwbvyalf0cfk0vkaysvcmkva9syh-kind-0.23.0/bin/kind"

def run_command(command, show_output=True):
    """Run a shell command and print its output"""
    # Replace 'kubectl' and 'kind' with their full paths, but be careful with file paths
    if command.startswith("kind create cluster --config "):
        # Special handling for the kind create cluster command
        parts = command.split("--config ")
        command = f"{KIND} create cluster --config {parts[1]}"
    else:
        # Regular replacement for other commands
        command = command.replace("kubectl", KUBECTL).replace("kind", KIND)
    
    print(f"Running: {command}")
    process = subprocess.Popen(
        command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    stdout, stderr = process.communicate()
    
    if stdout and show_output:
        print(stdout.decode())
    if stderr and show_output:
        print(stderr.decode())
        
    return process.returncode, stdout.decode(), stderr.decode()

def create_kind_cluster():
    """Create a Kind Kubernetes cluster"""
    print("Creating Kind Kubernetes cluster...")
    
    # Create a Kind cluster configuration with port mappings
    cluster_config = """
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
name: root-cause-analysis
nodes:
- role: control-plane
  extraPortMappings:
  - containerPort: 30080
    hostPort: 8080
    protocol: TCP
  - containerPort: 30443
    hostPort: 8443
    protocol: TCP
"""
    
    # Write config to a temporary file
    with open("kind-config.yaml", "w") as f:
        f.write(cluster_config)
    
    # Create the cluster
    return_code, _, _ = run_command("kind create cluster --config kind-config.yaml")
    if return_code != 0:
        print("Failed to create Kind cluster")
        return False
    
    # Verify the cluster is created
    return_code, stdout, _ = run_command("kubectl cluster-info", show_output=False)
    if return_code != 0:
        print("Failed to connect to the created cluster")
        return False
    
    print("Kind cluster created successfully!")
    print(stdout)
    
    # Set up kubectl context
    run_command("kubectl config use-context kind-root-cause-analysis")
    
    return True

def deploy_test_microservices():
    """Deploy a set of test microservices to the cluster for root cause analysis"""
    print("Deploying test microservices...")
    
    # Create a test namespace
    run_command("kubectl create namespace test-microservices")
    
    # Create manifests directory if it doesn't exist
    if not os.path.exists("manifests"):
        os.makedirs("manifests")
    
    # Deploy Frontend Service
    frontend_deployment = """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: frontend
  namespace: test-microservices
spec:
  replicas: 2
  selector:
    matchLabels:
      app: frontend
  template:
    metadata:
      labels:
        app: frontend
    spec:
      containers:
      - name: frontend
        image: nginx:1.19
        ports:
        - containerPort: 80
        resources:
          requests:
            memory: "64Mi"
            cpu: "100m"
          limits:
            memory: "128Mi"
            cpu: "200m"
---
apiVersion: v1
kind: Service
metadata:
  name: frontend
  namespace: test-microservices
spec:
  selector:
    app: frontend
  ports:
  - port: 80
    targetPort: 80
    nodePort: 30080
  type: NodePort
"""
    
    with open("manifests/frontend.yaml", "w") as f:
        f.write(frontend_deployment)
    
    # Deploy Backend Service (with an intentional issue - high CPU usage)
    backend_deployment = """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: backend
  namespace: test-microservices
spec:
  replicas: 1
  selector:
    matchLabels:
      app: backend
  template:
    metadata:
      labels:
        app: backend
    spec:
      containers:
      - name: backend
        image: busybox:1.33.1
        command: ["/bin/sh", "-c"]
        args:
        - "while true; do echo Computing...; cat /dev/urandom | md5sum > /dev/null; done"
        resources:
          requests:
            memory: "64Mi"
            cpu: "100m"
          limits:
            memory: "128Mi"
            cpu: "200m"
---
apiVersion: v1
kind: Service
metadata:
  name: backend
  namespace: test-microservices
spec:
  selector:
    app: backend
  ports:
  - port: 8080
    targetPort: 8080
"""
    
    with open("manifests/backend.yaml", "w") as f:
        f.write(backend_deployment)
    
    # Deploy Database Service (with an intentional issue - frequent restarts)
    database_deployment = """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: database
  namespace: test-microservices
spec:
  replicas: 1
  selector:
    matchLabels:
      app: database
  template:
    metadata:
      labels:
        app: database
    spec:
      containers:
      - name: database
        image: busybox:1.33.1
        command: ["/bin/sh", "-c"]
        args:
        - "echo Starting database...; sleep 30; exit 1"
        resources:
          requests:
            memory: "64Mi"
            cpu: "50m"
          limits:
            memory: "128Mi"
            cpu: "100m"
---
apiVersion: v1
kind: Service
metadata:
  name: database
  namespace: test-microservices
spec:
  selector:
    app: database
  ports:
  - port: 5432
    targetPort: 5432
"""
    
    with open("manifests/database.yaml", "w") as f:
        f.write(database_deployment)
    
    # Deploy API Gateway Service (with an intentional issue - missing environment variable)
    api_gateway_deployment = """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-gateway
  namespace: test-microservices
spec:
  replicas: 1
  selector:
    matchLabels:
      app: api-gateway
  template:
    metadata:
      labels:
        app: api-gateway
    spec:
      containers:
      - name: api-gateway
        image: busybox:1.33.1
        command: ["/bin/sh", "-c"]
        args:
        - "echo API Gateway starting...; echo Required env: $REQUIRED_API_KEY; if [ -z \"$REQUIRED_API_KEY\" ]; then echo Missing required environment variable; exit 1; fi; sleep infinity"
        resources:
          requests:
            memory: "64Mi"
            cpu: "50m"
          limits:
            memory: "128Mi"
            cpu: "100m"
---
apiVersion: v1
kind: Service
metadata:
  name: api-gateway
  namespace: test-microservices
spec:
  selector:
    app: api-gateway
  ports:
  - port: 8000
    targetPort: 8000
"""
    
    with open("manifests/api-gateway.yaml", "w") as f:
        f.write(api_gateway_deployment)
    
    # Deploy Resource-heavy Service (with an intentional issue - high memory usage)
    resource_heavy_deployment = """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: resource-service
  namespace: test-microservices
spec:
  replicas: 1
  selector:
    matchLabels:
      app: resource-service
  template:
    metadata:
      labels:
        app: resource-service
    spec:
      containers:
      - name: resource-service
        image: busybox:1.33.1
        command: ["/bin/sh", "-c"]
        args:
        - "echo Starting resource-intensive service...; dd if=/dev/zero of=/tmp/memory-hogger bs=1M count=90; sleep infinity"
        resources:
          requests:
            memory: "64Mi"
            cpu: "50m"
          limits:
            memory: "128Mi"
            cpu: "100m"
---
apiVersion: v1
kind: Service
metadata:
  name: resource-service
  namespace: test-microservices
spec:
  selector:
    app: resource-service
  ports:
  - port: 8888
    targetPort: 8888
"""
    
    with open("manifests/resource-service.yaml", "w") as f:
        f.write(resource_heavy_deployment)
    
    # Create NetworkPolicy that incorrectly blocks traffic (intentional issue)
    network_policy = """
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: backend-network-policy
  namespace: test-microservices
spec:
  podSelector:
    matchLabels:
      app: backend
  policyTypes:
  - Ingress
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app: non-existent-service
"""
    
    with open("manifests/network-policy.yaml", "w") as f:
        f.write(network_policy)
    
    # Apply all manifests
    run_command("kubectl apply -f manifests/frontend.yaml")
    run_command("kubectl apply -f manifests/backend.yaml")
    run_command("kubectl apply -f manifests/database.yaml")
    run_command("kubectl apply -f manifests/api-gateway.yaml")
    run_command("kubectl apply -f manifests/resource-service.yaml")
    run_command("kubectl apply -f manifests/network-policy.yaml")
    
    print("Test microservices deployed successfully!")
    return True

def wait_for_services(namespace="test-microservices", timeout=60):
    """Wait for services to be available"""
    print(f"Waiting for services in namespace {namespace} to be available...")
    
    start_time = time.time()
    while time.time() - start_time < timeout:
        return_code, stdout, _ = run_command(f"kubectl get pods -n {namespace}", show_output=False)
        if return_code == 0 and "frontend" in stdout:
            break
        time.sleep(5)
    
    # Give some time for the pods to start (or fail, as some are designed to)
    time.sleep(30)
    
    # Show the current state
    run_command(f"kubectl get pods -n {namespace}")
    run_command(f"kubectl get services -n {namespace}")
    
    return True

def summarize_test_environment():
    """Print a summary of the test environment"""
    print("\n===== Test Environment Summary =====")
    print("A Kubernetes cluster has been set up with the following test microservices:")
    print("1. Frontend (nginx) - Functioning normally")
    print("2. Backend - High CPU usage issue")
    print("3. Database - Frequent restart issue")
    print("4. API Gateway - Missing environment variable issue")
    print("5. Resource Service - High memory usage issue")
    print("Additionally, a network policy is blocking traffic to the backend service.")
    print("\nYou can run the following command to see the status of the pods:")
    print("  kubectl get pods -n test-microservices")
    print("\nTo analyze the cluster with our tool, use the following settings:")
    print("  Context: kind-root-cause-analysis")
    print("  Namespace: test-microservices")
    print("  Analysis Type: comprehensive")
    print("\n====================================")

def main():
    """Main function to set up the test environment"""
    # Skip installation checks since we know they're installed
    print("Using Kind at:", KIND)
    print("Using kubectl at:", KUBECTL)
    
    # Create the Kind cluster
    if not create_kind_cluster():
        return
    
    # Deploy test microservices
    if not deploy_test_microservices():
        return
    
    # Wait for services to be available
    if not wait_for_services():
        return
    
    # Summarize the test environment
    summarize_test_environment()
    
    print("\nTest environment setup complete!")

if __name__ == "__main__":
    main()
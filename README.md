# K8s-RCA: Kubernetes Root Cause Analysis Tool

A sophisticated multi-agent Kubernetes root cause analysis system that leverages AI to provide comprehensive diagnostics and troubleshooting for cloud-native application infrastructures.

![K8s-RCA Screenshot](generated-icon.png)

## Features

- Python-based AI diagnostic engine
- Streamlit web interface
- Advanced distributed tracing algorithms
- Machine learning-powered root cause identification
- Interactive visualization of complex system metrics
- Evidence-based hypothesis generation and testing
- Multi-agent architecture analyzing different aspects of Kubernetes

## Prerequisites

Before starting, make sure you have the following installed on your system:

- **Python 3.10+** - Required to run the application
- **pip** - For Python package management
- **A Kubernetes cluster** - Either local (minikube, kind, k3s) or remote with access credentials
- **kubectl** - Properly configured to access your cluster
- **Git** - To clone the repository

Additionally, you will need:

- **An OpenAI API key** - For LLM-powered analysis
- **An Anthropic API key** - For alternative model use

## Installation

Follow these steps to set up the project on your local machine:

### 1. Clone the repository

```bash
git clone https://github.com/yourusername/k8s-rca.git
cd k8s-rca
```

### 2. Create and activate a virtual environment (recommended)

```bash
# For Linux/macOS
python -m venv venv
source venv/bin/activate

# For Windows
python -m venv venv
venv\Scripts\activate
```

### 3. Install dependencies

First, rename the dependencies.txt file to requirements.txt:

```bash
mv dependencies.txt requirements.txt
```

Then install the dependencies:

```bash
pip install -r requirements.txt
```

Alternatively, you can install the required packages manually:

```bash
pip install streamlit pandas kubernetes plotly networkx pyyaml openai anthropic python-dotenv requests httpx
```

## Configuration

### 1. Set up API Keys

Create a `.env` file in the project root directory:

```bash
touch .env
```

Add your API keys to the file:

```
OPENAI_API_KEY=your_openai_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
```

Alternatively, you can set environment variables directly:

```bash
# For Linux/macOS
export OPENAI_API_KEY=your_openai_api_key_here
export ANTHROPIC_API_KEY=your_anthropic_api_key_here

# For Windows
set OPENAI_API_KEY=your_openai_api_key_here
set ANTHROPIC_API_KEY=your_anthropic_api_key_here
```

### 2. Kubernetes Configuration

The application uses your existing kubectl configuration by default. Ensure your kubeconfig file is properly set up:

```bash
# Check if kubectl is working
kubectl get nodes
```

Alternatively, you can place a specific kubeconfig file in the `kube-config` directory:

```bash
mkdir -p kube-config
cp /path/to/your/kubeconfig kube-config/safe-kubeconfig.yaml
```

## Running the Application

### 1. Set up environment (only needed once)

#### For Linux/macOS
```bash
# Make sure you're in the project directory
# Activate the virtual environment if you created one
source venv/bin/activate

# Set the needed environment variables
export OPENAI_API_KEY=your_openai_api_key_here
export ANTHROPIC_API_KEY=your_anthropic_api_key_here
```

#### For Windows
```bash
# Make sure you're in the project directory
# Activate the virtual environment if you created one
venv\Scripts\activate

# Set the needed environment variables
set OPENAI_API_KEY=your_openai_api_key_here
set ANTHROPIC_API_KEY=your_anthropic_api_key_here
```

### 2. Start the Streamlit server

```bash
streamlit run app.py
```

This will launch the application on `http://localhost:5000`. The first time you run it, you may need to authenticate with your LLM API providers.

### 3. Access the application

Open your web browser and navigate to:
```
http://localhost:5000
```

You should see the K8s-RCA interface. Select a namespace from the sidebar to begin your analysis.

## Creating a Test Environment (Optional)

If you want to test the application with a predefined test environment, you can run:

```bash
python setup_test_cluster.py
```

This script creates a local Kind cluster with test microservices that have common Kubernetes issues for analysis. You need to have Docker and Kind installed for this to work.

## Usage Guide

### 1. Connect to Your Cluster

When you start the application, it will automatically attempt to connect to your Kubernetes cluster using your kubeconfig file.

### 2. Select a Namespace

From the sidebar, select the namespace you want to analyze.

### 3. Select a Component

Choose a component (Pod, Deployment, Service, etc.) that's experiencing issues.

### 4. Generate Hypotheses

The system will generate potential root causes for the observed issues.

### 5. Investigate Hypotheses

Select a hypothesis to investigate. The system will gather evidence and provide insights.

### 6. Review Evidence

Examine the collected evidence to understand the root cause of the issue.

### 7. Accept Conclusions

Once a hypothesis is confirmed, the system will provide recommendations for resolving the issue.

## Understanding the Multi-Agent System

The application uses a coordinated multi-agent system to analyze different aspects of your Kubernetes environment:

- **Metrics Agent** - Analyzes resource usage and performance metrics
- **Logs Agent** - Examines log data for error patterns and anomalies
- **Topology Agent** - Maps service dependencies and network flows
- **Events Agent** - Processes Kubernetes events and state changes
- **Traces Agent** - Analyzes distributed tracing data when available

## Troubleshooting

### API Key Issues

If you encounter errors related to API keys:

```
Error: Could not authenticate with OpenAI/Anthropic
```

Check that your API keys are correctly set in the `.env` file or as environment variables.

### Kubernetes Connection Issues

If you see errors connecting to the Kubernetes API:

```
Error: Could not connect to Kubernetes cluster
```

Verify that:
- kubectl is properly configured and working
- You have the necessary permissions in the cluster
- Your kubeconfig file is valid

### LLM API Key Issues

If you see errors related to missing API keys:

```
Error: Missing required API keys for LLM providers
```

Make sure you've set up the environment variables properly. You can check if they're set using:

```bash
# For Linux/macOS
echo $OPENAI_API_KEY
echo $ANTHROPIC_API_KEY

# For Windows
echo %OPENAI_API_KEY%
echo %ANTHROPIC_API_KEY%
```

If using a .env file, ensure Python's dotenv is correctly loading the file:

```python
# Check this is in your code
from dotenv import load_dotenv
load_dotenv()
```

### Missing Dependencies

If you see import errors:

```
ImportError: No module named 'streamlit'
```

Make sure all dependencies are installed:

```bash
pip install -r requirements.txt
```

### Permission Issues

If you see permission errors accessing Kubernetes resources:

```
Error: Forbidden - User does not have access to the resource
```

Check that your Kubernetes user has the necessary RBAC permissions to view pods, services, deployments, logs, and events.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Project Structure

The project is organized as follows:

```
.
├── agents/                    # Specialized agents for different analysis types
│   ├── base_agent.py          # Base agent class with common functionality
│   ├── coordinator.py         # Agent coordination logic
│   ├── events_agent.py        # Kubernetes events analysis
│   ├── logs_agent.py          # Log data analysis
│   ├── mcp_*.py               # Model Context Protocol agents
│   ├── metrics_agent.py       # Metrics data analysis
│   ├── resource_analyzer.py   # Resource usage analysis
│   ├── topology_agent.py      # Service dependency mapping
│   └── traces_agent.py        # Distributed tracing analysis
│
├── components/                # UI components
│   ├── interactive_session.py # Interactive analysis session UI
│   ├── report.py              # Analysis report generation
│   ├── sidebar.py             # Sidebar navigation UI
│   └── visualization.py       # Data visualization components
│
├── kube-config/               # Kubernetes configuration
│   └── safe-kubeconfig.yaml   # Kubeconfig file for cluster access
│
├── logs/                      # Analysis logs and evidence
│
├── utils/                     # Utility modules
│   ├── helper.py              # General helper functions
│   ├── k8s_client.py          # Kubernetes API client
│   ├── llm_client.py          # LLM API client
│   ├── llm_client_improved.py # Enhanced LLM client
│   └── logging_helper.py      # Logging utilities
│
├── .streamlit/               # Streamlit configuration
│   └── config.toml           # Streamlit server settings
│
├── app.py                    # Main application entry point
├── agent_coordinator.py      # Agent orchestration logic
├── dependencies.txt          # Python dependencies
├── setup_test_cluster.py     # Test cluster setup script
└── README.md                 # This README file
```

## Credits

This project was created to help Kubernetes administrators and developers quickly identify and resolve issues in their cloud-native environments.
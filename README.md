# Kubernetes Root Cause Analysis System

A sophisticated multi-agent Kubernetes root cause analysis system that provides intelligent, real-time diagnostics for cloud-native infrastructure monitoring.

## Features

- Python-based AI diagnostic engine
- Streamlit interactive web interface
- Advanced prompt logging and investigation tracking
- Machine learning root cause identification
- Live cluster connection monitoring
- Enhanced conversational UI with responsive design
- Multi-agent system for specialized analyses (metrics, logs, traces, topology, and events)
- Progressive context building with key findings extraction
- Interactive suggestion system

## Requirements

- Python 3.11+
- Kubernetes cluster access
- OpenAI or Anthropic API key

## Environment Setup

The system requires the following environment variables:
- `KUBECONFIG` - Path to your Kubernetes configuration file
- `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` - API keys for LLM access

## Running the Application

Start the application with:

```
streamlit run app.py --server.port 5000
```

## Project Structure

- `agents/` - Specialized diagnostic agents
- `components/` - Web UI components
- `logs/` - Investigation logs and archives
- `utils/` - Utility functions and services
- `kube-config/` - Kubernetes configuration
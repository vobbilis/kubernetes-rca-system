import json
import time
import random
import os
from datetime import datetime

class MockK8sClient:
    """
    Mock client for simulating interactions with Kubernetes.
    Provides synthetic data for testing the MCP agents.
    """
    
    def __init__(self, use_mock=True):
        """
        Initialize the mock Kubernetes client.
        
        Args:
            use_mock: If True, return mock data; if False, attempt to use real k8s
        """
        self.use_mock = use_mock
        self.connected = True
        self.current_context = "mock-context"
        self.available_contexts = ["mock-context"]
        
        # Load mock data once
        self._load_mock_data()
    
    def _load_mock_data(self):
        """Load mock data for testing."""
        # Define mock namespaces
        self.namespaces = ["default", "kube-system", "test-microservices"]
        
        # Define mock pods with various issues
        self.pods = {
            "test-microservices": [
                {
                    "metadata": {
                        "name": "frontend-7d8f675c7b-jk2x5",
                        "namespace": "test-microservices",
                        "labels": {"app": "frontend"}
                    },
                    "spec": {
                        "containers": [
                            {
                                "name": "frontend",
                                "image": "nginx:1.19",
                                "resources": {
                                    "requests": {"cpu": "100m", "memory": "64Mi"},
                                    "limits": {"cpu": "200m", "memory": "128Mi"}
                                }
                            }
                        ]
                    },
                    "status": {
                        "phase": "Running",
                        "conditions": [
                            {"type": "Ready", "status": "True"}
                        ],
                        "containerStatuses": [
                            {
                                "name": "frontend",
                                "ready": True,
                                "restartCount": 0,
                                "state": {"running": {"startedAt": "2023-04-18T10:00:00Z"}}
                            }
                        ]
                    }
                },
                {
                    "metadata": {
                        "name": "frontend-7d8f675c7b-p9x2q",
                        "namespace": "test-microservices",
                        "labels": {"app": "frontend"}
                    },
                    "spec": {
                        "containers": [
                            {
                                "name": "frontend",
                                "image": "nginx:1.19",
                                "resources": {
                                    "requests": {"cpu": "100m", "memory": "64Mi"},
                                    "limits": {"cpu": "200m", "memory": "128Mi"}
                                }
                            }
                        ]
                    },
                    "status": {
                        "phase": "Running",
                        "conditions": [
                            {"type": "Ready", "status": "True"}
                        ],
                        "containerStatuses": [
                            {
                                "name": "frontend",
                                "ready": True,
                                "restartCount": 0,
                                "state": {"running": {"startedAt": "2023-04-18T10:00:00Z"}}
                            }
                        ]
                    }
                },
                {
                    "metadata": {
                        "name": "backend-5b6d8f9c7d-2zf8g",
                        "namespace": "test-microservices",
                        "labels": {"app": "backend"}
                    },
                    "spec": {
                        "containers": [
                            {
                                "name": "backend",
                                "image": "busybox:1.33.1",
                                "resources": {
                                    "requests": {"cpu": "100m", "memory": "64Mi"},
                                    "limits": {"cpu": "200m", "memory": "128Mi"}
                                }
                            }
                        ]
                    },
                    "status": {
                        "phase": "Running",
                        "conditions": [
                            {"type": "Ready", "status": "True"}
                        ],
                        "containerStatuses": [
                            {
                                "name": "backend",
                                "ready": True,
                                "restartCount": 0,
                                "state": {"running": {"startedAt": "2023-04-18T10:00:00Z"}}
                            }
                        ]
                    }
                },
                {
                    "metadata": {
                        "name": "database-7c9f8b6d5e-3x5qp",
                        "namespace": "test-microservices",
                        "labels": {"app": "database"}
                    },
                    "spec": {
                        "containers": [
                            {
                                "name": "database",
                                "image": "busybox:1.33.1",
                                "resources": {
                                    "requests": {"cpu": "50m", "memory": "64Mi"},
                                    "limits": {"cpu": "100m", "memory": "128Mi"}
                                }
                            }
                        ]
                    },
                    "status": {
                        "phase": "CrashLoopBackOff",
                        "conditions": [
                            {"type": "Ready", "status": "False"}
                        ],
                        "containerStatuses": [
                            {
                                "name": "database",
                                "ready": False,
                                "restartCount": 5,
                                "state": {"waiting": {"reason": "CrashLoopBackOff", "message": "Back-off restarting failed container"}},
                                "lastState": {"terminated": {"exitCode": 1, "reason": "Error", "message": "Container exited with code 1"}}
                            }
                        ]
                    }
                },
                {
                    "metadata": {
                        "name": "api-gateway-6b7c8d9e5f-4q3zx",
                        "namespace": "test-microservices",
                        "labels": {"app": "api-gateway"}
                    },
                    "spec": {
                        "containers": [
                            {
                                "name": "api-gateway",
                                "image": "busybox:1.33.1",
                                "resources": {
                                    "requests": {"cpu": "50m", "memory": "64Mi"},
                                    "limits": {"cpu": "100m", "memory": "128Mi"}
                                }
                            }
                        ]
                    },
                    "status": {
                        "phase": "Failed",
                        "conditions": [
                            {"type": "Ready", "status": "False"}
                        ],
                        "containerStatuses": [
                            {
                                "name": "api-gateway",
                                "ready": False,
                                "restartCount": 3,
                                "state": {"terminated": {"exitCode": 1, "reason": "Error", "message": "Missing required environment variable"}},
                                "lastState": {"terminated": {"exitCode": 1, "reason": "Error", "message": "Missing required environment variable"}}
                            }
                        ]
                    }
                },
                {
                    "metadata": {
                        "name": "resource-service-9d8e7f6c5b-1r5wq",
                        "namespace": "test-microservices",
                        "labels": {"app": "resource-service"}
                    },
                    "spec": {
                        "containers": [
                            {
                                "name": "resource-service",
                                "image": "busybox:1.33.1",
                                "resources": {
                                    "requests": {"cpu": "50m", "memory": "64Mi"},
                                    "limits": {"cpu": "100m", "memory": "128Mi"}
                                }
                            }
                        ]
                    },
                    "status": {
                        "phase": "Running",
                        "conditions": [
                            {"type": "Ready", "status": "True"}
                        ],
                        "containerStatuses": [
                            {
                                "name": "resource-service",
                                "ready": True,
                                "restartCount": 0,
                                "state": {"running": {"startedAt": "2023-04-18T10:00:00Z"}}
                            }
                        ]
                    }
                }
            ],
            "default": [],
            "kube-system": []
        }
        
        # Define mock services
        self.services = {
            "test-microservices": [
                {
                    "metadata": {
                        "name": "frontend",
                        "namespace": "test-microservices"
                    },
                    "spec": {
                        "selector": {"app": "frontend"},
                        "ports": [{"port": 80, "targetPort": 80, "nodePort": 30080}],
                        "type": "NodePort"
                    }
                },
                {
                    "metadata": {
                        "name": "backend",
                        "namespace": "test-microservices"
                    },
                    "spec": {
                        "selector": {"app": "backend"},
                        "ports": [{"port": 8080, "targetPort": 8080}],
                        "type": "ClusterIP"
                    }
                },
                {
                    "metadata": {
                        "name": "database",
                        "namespace": "test-microservices"
                    },
                    "spec": {
                        "selector": {"app": "database"},
                        "ports": [{"port": 5432, "targetPort": 5432}],
                        "type": "ClusterIP"
                    }
                },
                {
                    "metadata": {
                        "name": "api-gateway",
                        "namespace": "test-microservices"
                    },
                    "spec": {
                        "selector": {"app": "api-gateway"},
                        "ports": [{"port": 8000, "targetPort": 8000}],
                        "type": "ClusterIP"
                    }
                },
                {
                    "metadata": {
                        "name": "resource-service",
                        "namespace": "test-microservices"
                    },
                    "spec": {
                        "selector": {"app": "resource-service"},
                        "ports": [{"port": 8888, "targetPort": 8888}],
                        "type": "ClusterIP"
                    }
                }
            ],
            "default": [],
            "kube-system": []
        }
        
        # Define mock deployments
        self.deployments = {
            "test-microservices": [
                {
                    "metadata": {
                        "name": "frontend",
                        "namespace": "test-microservices"
                    },
                    "spec": {
                        "replicas": 2,
                        "selector": {"matchLabels": {"app": "frontend"}},
                        "template": {
                            "metadata": {"labels": {"app": "frontend"}},
                            "spec": {
                                "containers": [
                                    {
                                        "name": "frontend",
                                        "image": "nginx:1.19",
                                        "resources": {
                                            "requests": {"cpu": "100m", "memory": "64Mi"},
                                            "limits": {"cpu": "200m", "memory": "128Mi"}
                                        }
                                    }
                                ]
                            }
                        }
                    },
                    "status": {
                        "availableReplicas": 2,
                        "readyReplicas": 2,
                        "replicas": 2,
                        "updatedReplicas": 2
                    }
                },
                {
                    "metadata": {
                        "name": "backend",
                        "namespace": "test-microservices"
                    },
                    "spec": {
                        "replicas": 1,
                        "selector": {"matchLabels": {"app": "backend"}},
                        "template": {
                            "metadata": {"labels": {"app": "backend"}},
                            "spec": {
                                "containers": [
                                    {
                                        "name": "backend",
                                        "image": "busybox:1.33.1",
                                        "resources": {
                                            "requests": {"cpu": "100m", "memory": "64Mi"},
                                            "limits": {"cpu": "200m", "memory": "128Mi"}
                                        }
                                    }
                                ]
                            }
                        }
                    },
                    "status": {
                        "availableReplicas": 1,
                        "readyReplicas": 1,
                        "replicas": 1,
                        "updatedReplicas": 1
                    }
                },
                {
                    "metadata": {
                        "name": "database",
                        "namespace": "test-microservices"
                    },
                    "spec": {
                        "replicas": 1,
                        "selector": {"matchLabels": {"app": "database"}},
                        "template": {
                            "metadata": {"labels": {"app": "database"}},
                            "spec": {
                                "containers": [
                                    {
                                        "name": "database",
                                        "image": "busybox:1.33.1",
                                        "resources": {
                                            "requests": {"cpu": "50m", "memory": "64Mi"},
                                            "limits": {"cpu": "100m", "memory": "128Mi"}
                                        }
                                    }
                                ]
                            }
                        }
                    },
                    "status": {
                        "availableReplicas": 0,
                        "readyReplicas": 0,
                        "replicas": 1,
                        "updatedReplicas": 1
                    }
                },
                {
                    "metadata": {
                        "name": "api-gateway",
                        "namespace": "test-microservices"
                    },
                    "spec": {
                        "replicas": 1,
                        "selector": {"matchLabels": {"app": "api-gateway"}},
                        "template": {
                            "metadata": {"labels": {"app": "api-gateway"}},
                            "spec": {
                                "containers": [
                                    {
                                        "name": "api-gateway",
                                        "image": "busybox:1.33.1",
                                        "resources": {
                                            "requests": {"cpu": "50m", "memory": "64Mi"},
                                            "limits": {"cpu": "100m", "memory": "128Mi"}
                                        }
                                    }
                                ]
                            }
                        }
                    },
                    "status": {
                        "availableReplicas": 0,
                        "readyReplicas": 0,
                        "replicas": 1,
                        "updatedReplicas": 1
                    }
                },
                {
                    "metadata": {
                        "name": "resource-service",
                        "namespace": "test-microservices"
                    },
                    "spec": {
                        "replicas": 1,
                        "selector": {"matchLabels": {"app": "resource-service"}},
                        "template": {
                            "metadata": {"labels": {"app": "resource-service"}},
                            "spec": {
                                "containers": [
                                    {
                                        "name": "resource-service",
                                        "image": "busybox:1.33.1",
                                        "resources": {
                                            "requests": {"cpu": "50m", "memory": "64Mi"},
                                            "limits": {"cpu": "100m", "memory": "128Mi"}
                                        }
                                    }
                                ]
                            }
                        }
                    },
                    "status": {
                        "availableReplicas": 1,
                        "readyReplicas": 1,
                        "replicas": 1,
                        "updatedReplicas": 1
                    }
                }
            ],
            "default": [],
            "kube-system": []
        }
        
        # Define mock metrics
        self.pod_metrics = {
            "test-microservices": {
                "frontend-7d8f675c7b-jk2x5": {
                    "cpu": {"usage": 50, "usage_percentage": 25},
                    "memory": {"usage": 32 * 1024 * 1024, "usage_percentage": 25}
                },
                "frontend-7d8f675c7b-p9x2q": {
                    "cpu": {"usage": 60, "usage_percentage": 30},
                    "memory": {"usage": 40 * 1024 * 1024, "usage_percentage": 31.25}
                },
                "backend-5b6d8f9c7d-2zf8g": {
                    "cpu": {"usage": 180, "usage_percentage": 90},
                    "memory": {"usage": 60 * 1024 * 1024, "usage_percentage": 46.88}
                },
                "database-7c9f8b6d5e-3x5qp": {
                    "cpu": {"usage": 40, "usage_percentage": 40},
                    "memory": {"usage": 70 * 1024 * 1024, "usage_percentage": 54.69}
                },
                "api-gateway-6b7c8d9e5f-4q3zx": {
                    "cpu": {"usage": 30, "usage_percentage": 30},
                    "memory": {"usage": 40 * 1024 * 1024, "usage_percentage": 31.25}
                },
                "resource-service-9d8e7f6c5b-1r5wq": {
                    "cpu": {"usage": 50, "usage_percentage": 50},
                    "memory": {"usage": 115 * 1024 * 1024, "usage_percentage": 89.84}
                }
            }
        }
        
        self.node_metrics = {
            "mock-worker-1": {
                "cpu": {"usage_percentage": 65},
                "memory": {"usage_percentage": 72}
            },
            "mock-worker-2": {
                "cpu": {"usage_percentage": 45},
                "memory": {"usage_percentage": 60}
            },
            "mock-control-plane": {
                "cpu": {"usage_percentage": 40},
                "memory": {"usage_percentage": 55}
            }
        }
        
        # Define mock events
        self.events = {
            "test-microservices": [
                {
                    "metadata": {
                        "name": "database-7c9f8b6d5e-3x5qp.16b78f5c9d8e7f",
                        "namespace": "test-microservices"
                    },
                    "involvedObject": {
                        "kind": "Pod",
                        "name": "database-7c9f8b6d5e-3x5qp",
                        "namespace": "test-microservices"
                    },
                    "type": "Warning",
                    "reason": "BackOff",
                    "message": "Back-off restarting failed container database in pod database-7c9f8b6d5e-3x5qp",
                    "count": 5,
                    "firstTimestamp": "2023-04-18T10:00:00Z",
                    "lastTimestamp": "2023-04-18T10:05:00Z"
                },
                {
                    "metadata": {
                        "name": "api-gateway-6b7c8d9e5f-4q3zx.27e8f9d7c6b5a",
                        "namespace": "test-microservices"
                    },
                    "involvedObject": {
                        "kind": "Pod",
                        "name": "api-gateway-6b7c8d9e5f-4q3zx",
                        "namespace": "test-microservices"
                    },
                    "type": "Warning",
                    "reason": "Failed",
                    "message": "Error: Missing required environment variable",
                    "count": 3,
                    "firstTimestamp": "2023-04-18T10:00:00Z",
                    "lastTimestamp": "2023-04-18T10:02:00Z"
                },
                {
                    "metadata": {
                        "name": "backend-5b6d8f9c7d-2zf8g.38f9e7d6c5b4a",
                        "namespace": "test-microservices"
                    },
                    "involvedObject": {
                        "kind": "Pod",
                        "name": "backend-5b6d8f9c7d-2zf8g",
                        "namespace": "test-microservices"
                    },
                    "type": "Warning",
                    "reason": "CPUThrottling",
                    "message": "Container backend CPU throttled",
                    "count": 10,
                    "firstTimestamp": "2023-04-18T10:10:00Z",
                    "lastTimestamp": "2023-04-18T10:30:00Z"
                },
                {
                    "metadata": {
                        "name": "resource-service-9d8e7f6c5b-1r5wq.49g0h1i2j3k4",
                        "namespace": "test-microservices"
                    },
                    "involvedObject": {
                        "kind": "Pod",
                        "name": "resource-service-9d8e7f6c5b-1r5wq",
                        "namespace": "test-microservices"
                    },
                    "type": "Warning",
                    "reason": "MemoryHigh",
                    "message": "Container resource-service memory usage high (89.84%)",
                    "count": 2,
                    "firstTimestamp": "2023-04-18T10:20:00Z",
                    "lastTimestamp": "2023-04-18T10:25:00Z"
                }
            ],
            "default": [],
            "kube-system": []
        }
        
        # Define mock logs
        self.logs = {
            "test-microservices": {
                "frontend-7d8f675c7b-jk2x5": {
                    "frontend": "2023-04-18T10:00:00.000Z INFO: Starting nginx server\n2023-04-18T10:00:01.000Z INFO: nginx running\n2023-04-18T10:01:00.000Z INFO: Received request for /\n2023-04-18T10:02:00.000Z INFO: Received request for /api/data"
                },
                "frontend-7d8f675c7b-p9x2q": {
                    "frontend": "2023-04-18T10:00:00.000Z INFO: Starting nginx server\n2023-04-18T10:00:01.000Z INFO: nginx running\n2023-04-18T10:01:30.000Z INFO: Received request for /\n2023-04-18T10:02:30.000Z INFO: Received request for /api/data"
                },
                "backend-5b6d8f9c7d-2zf8g": {
                    "backend": "2023-04-18T10:00:00.000Z INFO: Starting backend service\n2023-04-18T10:00:01.000Z INFO: Computing...\n2023-04-18T10:00:02.000Z INFO: Computing...\n2023-04-18T10:00:03.000Z INFO: Computing...\n2023-04-18T10:00:04.000Z INFO: Computing...\n2023-04-18T10:00:05.000Z INFO: Computing..."
                },
                "database-7c9f8b6d5e-3x5qp": {
                    "database": "2023-04-18T10:00:00.000Z INFO: Starting database...\n2023-04-18T10:00:30.000Z ERROR: Database initialization failed\n2023-04-18T10:01:00.000Z INFO: Starting database...\n2023-04-18T10:01:30.000Z ERROR: Database initialization failed\n2023-04-18T10:02:00.000Z INFO: Starting database...\n2023-04-18T10:02:30.000Z ERROR: Database initialization failed"
                },
                "api-gateway-6b7c8d9e5f-4q3zx": {
                    "api-gateway": "2023-04-18T10:00:00.000Z INFO: API Gateway starting...\n2023-04-18T10:00:00.100Z INFO: Required env: \n2023-04-18T10:00:00.200Z ERROR: Missing required environment variable\n"
                },
                "resource-service-9d8e7f6c5b-1r5wq": {
                    "resource-service": "2023-04-18T10:00:00.000Z INFO: Starting resource-intensive service...\n2023-04-18T10:00:10.000Z INFO: Allocating memory resources\n2023-04-18T10:00:20.000Z WARN: Memory usage high\n2023-04-18T10:00:30.000Z WARN: Memory usage approaching limit"
                }
            }
        }
        
        # Define mock network policies
        self.network_policies = {
            "test-microservices": [
                {
                    "metadata": {
                        "name": "backend-network-policy",
                        "namespace": "test-microservices"
                    },
                    "spec": {
                        "podSelector": {
                            "matchLabels": {"app": "backend"}
                        },
                        "policyTypes": ["Ingress"],
                        "ingress": [
                            {
                                "from": [
                                    {
                                        "podSelector": {
                                            "matchLabels": {"app": "non-existent-service"}
                                        }
                                    }
                                ]
                            }
                        ]
                    }
                }
            ],
            "default": [],
            "kube-system": []
        }
        
        # Define mock endpoints
        self.endpoints = {
            "test-microservices": {
                "frontend": {
                    "metadata": {
                        "name": "frontend",
                        "namespace": "test-microservices"
                    },
                    "subsets": [
                        {
                            "addresses": [
                                {"ip": "10.244.0.5", "targetRef": {"kind": "Pod", "name": "frontend-7d8f675c7b-jk2x5"}},
                                {"ip": "10.244.0.6", "targetRef": {"kind": "Pod", "name": "frontend-7d8f675c7b-p9x2q"}}
                            ],
                            "ports": [{"port": 80, "protocol": "TCP"}]
                        }
                    ]
                },
                "backend": {
                    "metadata": {
                        "name": "backend",
                        "namespace": "test-microservices"
                    },
                    "subsets": [
                        {
                            "addresses": [
                                {"ip": "10.244.0.7", "targetRef": {"kind": "Pod", "name": "backend-5b6d8f9c7d-2zf8g"}}
                            ],
                            "ports": [{"port": 8080, "protocol": "TCP"}]
                        }
                    ]
                },
                "database": {
                    "metadata": {
                        "name": "database",
                        "namespace": "test-microservices"
                    },
                    "subsets": []  # No endpoints because the pod is in CrashLoopBackOff
                },
                "api-gateway": {
                    "metadata": {
                        "name": "api-gateway",
                        "namespace": "test-microservices"
                    },
                    "subsets": []  # No endpoints because the pod is in Failed state
                },
                "resource-service": {
                    "metadata": {
                        "name": "resource-service",
                        "namespace": "test-microservices"
                    },
                    "subsets": [
                        {
                            "addresses": [
                                {"ip": "10.244.0.10", "targetRef": {"kind": "Pod", "name": "resource-service-9d8e7f6c5b-1r5wq"}}
                            ],
                            "ports": [{"port": 8888, "protocol": "TCP"}]
                        }
                    ]
                }
            }
        }
        
        # Define mock HPA data
        self.hpas = {
            "test-microservices": [
                {
                    "metadata": {
                        "name": "frontend-hpa",
                        "namespace": "test-microservices"
                    },
                    "spec": {
                        "minReplicas": 2,
                        "maxReplicas": 5,
                        "scaleTargetRef": {
                            "apiVersion": "apps/v1",
                            "kind": "Deployment",
                            "name": "frontend"
                        },
                        "metrics": [
                            {
                                "type": "Resource",
                                "resource": {
                                    "name": "cpu",
                                    "target": {
                                        "type": "Utilization",
                                        "averageUtilization": 50
                                    }
                                }
                            }
                        ]
                    },
                    "status": {
                        "currentReplicas": 2,
                        "desiredReplicas": 2,
                        "currentMetrics": [
                            {
                                "type": "Resource",
                                "resource": {
                                    "name": "cpu",
                                    "current": {
                                        "averageUtilization": 27,
                                        "averageValue": "54m"
                                    }
                                }
                            }
                        ]
                    }
                },
                {
                    "metadata": {
                        "name": "backend-hpa",
                        "namespace": "test-microservices"
                    },
                    "spec": {
                        "minReplicas": 1,
                        "maxReplicas": 3,
                        "scaleTargetRef": {
                            "apiVersion": "apps/v1",
                            "kind": "Deployment",
                            "name": "backend"
                        },
                        "metrics": [
                            {
                                "type": "Resource",
                                "resource": {
                                    "name": "cpu",
                                    "target": {
                                        "type": "Utilization",
                                        "averageUtilization": 80
                                    }
                                }
                            }
                        ]
                    },
                    "status": {
                        "currentReplicas": 1,
                        "desiredReplicas": 3,  # Desired is more than current - indicating scaling is needed
                        "currentMetrics": [
                            {
                                "type": "Resource",
                                "resource": {
                                    "name": "cpu",
                                    "current": {
                                        "averageUtilization": 90,
                                        "averageValue": "180m"
                                    }
                                }
                            }
                        ]
                    }
                }
            ],
            "default": [],
            "kube-system": []
        }
    
    def is_connected(self):
        """
        Check if the client is connected to a Kubernetes cluster.
        
        Returns:
            bool: True if connected, False otherwise
        """
        return self.connected
    
    def get_available_contexts(self):
        """
        Get a list of available Kubernetes contexts.
        
        Returns:
            list: Available Kubernetes contexts
        """
        return self.available_contexts
    
    def get_current_context(self):
        """
        Get the current Kubernetes context.
        
        Returns:
            str: Current context name
        """
        return self.current_context
    
    def set_context(self, context_name):
        """
        Set the Kubernetes context.
        
        Args:
            context_name: Name of the context to set
            
        Returns:
            bool: True if context was set successfully, False otherwise
        """
        if context_name not in self.available_contexts:
            return False
        
        self.current_context = context_name
        return True
    
    def get_namespaces(self):
        """
        Get a list of all namespaces in the cluster.
        
        Returns:
            list: Namespace names
        """
        return self.namespaces
    
    def get_pods(self, namespace):
        """
        Get all pods in a namespace.
        
        Args:
            namespace: Namespace to query
            
        Returns:
            list: Pod data
        """
        return self.pods.get(namespace, [])
    
    def get_services(self, namespace):
        """
        Get all services in a namespace.
        
        Args:
            namespace: Namespace to query
            
        Returns:
            list: Service data
        """
        return self.services.get(namespace, [])
    
    def get_deployments(self, namespace):
        """
        Get all deployments in a namespace.
        
        Args:
            namespace: Namespace to query
            
        Returns:
            list: Deployment data
        """
        return self.deployments.get(namespace, [])
    
    def get_node_metrics(self):
        """
        Get metrics for all nodes in the cluster.
        
        Returns:
            dict: Node metrics data
        """
        return self.node_metrics
    
    def get_pod_metrics(self, namespace):
        """
        Get metrics for all pods in a namespace.
        
        Args:
            namespace: Namespace to query
            
        Returns:
            dict: Pod metrics data
        """
        return self.pod_metrics.get(namespace, {})
    
    def get_pod_logs(self, namespace, pod_name, container_name=None, tail_lines=100, previous=False):
        """
        Get logs for a pod.
        
        Args:
            namespace: Namespace of the pod
            pod_name: Name of the pod
            container_name: Name of the container (optional)
            tail_lines: Number of lines to return from the end of the logs
            previous: Whether to get logs from the previous instance of the container
            
        Returns:
            str: Pod logs
        """
        if namespace not in self.logs or pod_name not in self.logs[namespace]:
            return "No logs available for this pod"
        
        pod_logs = self.logs[namespace][pod_name]
        
        if container_name and container_name in pod_logs:
            return pod_logs[container_name]
        elif container_name:
            return f"Container {container_name} not found in pod {pod_name}"
        else:
            # If no container name specified, return logs for the first container
            return next(iter(pod_logs.values()), "No logs available for this pod")
    
    def get_events(self, namespace, field_selector=None, limit=None):
        """
        Get events for a namespace.
        
        Args:
            namespace: Namespace to query
            field_selector: Field selector to filter events
            limit: Maximum number of events to return
            
        Returns:
            list: Event data
        """
        events = self.events.get(namespace, [])
        
        if field_selector:
            # Simple field selector implementation for mock data
            filtered_events = []
            for event in events:
                if "involvedObject.kind" in field_selector and "involvedObject.name" in field_selector:
                    kind_value = field_selector.split("involvedObject.kind=")[1].split(",")[0]
                    name_value = field_selector.split("involvedObject.name=")[1]
                    
                    if (event["involvedObject"]["kind"] == kind_value and 
                        event["involvedObject"]["name"] == name_value):
                        filtered_events.append(event)
                elif "involvedObject.kind" in field_selector:
                    kind_value = field_selector.split("involvedObject.kind=")[1]
                    
                    if event["involvedObject"]["kind"] == kind_value:
                        filtered_events.append(event)
                elif "involvedObject.name" in field_selector:
                    name_value = field_selector.split("involvedObject.name=")[1]
                    
                    if event["involvedObject"]["name"] == name_value:
                        filtered_events.append(event)
                else:
                    filtered_events.append(event)
            
            events = filtered_events
        
        if limit and limit < len(events):
            events = events[:limit]
        
        return events
    
    def get_ingresses(self, namespace):
        """
        Get all ingresses in a namespace.
        
        Args:
            namespace: Namespace to query
            
        Returns:
            list: Ingress data
        """
        # Mock implementation - no ingresses for simplicity
        return []
    
    def get_network_policies(self, namespace):
        """
        Get all network policies in a namespace.
        
        Args:
            namespace: Namespace to query
            
        Returns:
            list: NetworkPolicy data
        """
        return self.network_policies.get(namespace, [])
    
    def get_configmaps(self, namespace):
        """
        Get all ConfigMaps in a namespace.
        
        Args:
            namespace: Namespace to query
            
        Returns:
            list: ConfigMap data
        """
        # Mock implementation - no configmaps for simplicity
        return []
    
    def get_secrets(self, namespace):
        """
        Get all Secrets in a namespace.
        
        Args:
            namespace: Namespace to query
            
        Returns:
            list: Secret data (without the actual secret values)
        """
        # Mock implementation - no secrets for simplicity
        return []
    
    def get_hpas(self, namespace):
        """
        Get all Horizontal Pod Autoscalers in a namespace.
        
        Args:
            namespace: Namespace to query
            
        Returns:
            list: HPA data
        """
        return self.hpas.get(namespace, [])
    
    def get_endpoints(self, namespace, name):
        """
        Get endpoints for a service.
        
        Args:
            namespace: Namespace of the service
            name: Name of the service
            
        Returns:
            dict: Endpoints data
        """
        if namespace in self.endpoints and name in self.endpoints[namespace]:
            return self.endpoints[namespace][name]
        return None
    
    def get_pod_status(self, namespace, pod_name):
        """
        Get detailed status for a specific pod.
        
        Args:
            namespace: Namespace of the pod
            pod_name: Name of the pod
            
        Returns:
            dict: Pod status data
        """
        pods = self.pods.get(namespace, [])
        for pod in pods:
            if pod["metadata"]["name"] == pod_name:
                return pod
        return None
    
    def get_service(self, namespace, service_name):
        """
        Get a specific service.
        
        Args:
            namespace: Namespace of the service
            service_name: Name of the service
            
        Returns:
            dict: Service data
        """
        services = self.services.get(namespace, [])
        for service in services:
            if service["metadata"]["name"] == service_name:
                return service
        return None
    
    def get_deployment(self, namespace, deployment_name):
        """
        Get a specific deployment.
        
        Args:
            namespace: Namespace of the deployment
            deployment_name: Name of the deployment
            
        Returns:
            dict: Deployment data
        """
        deployments = self.deployments.get(namespace, [])
        for deployment in deployments:
            if deployment["metadata"]["name"] == deployment_name:
                return deployment
        return None
    
    def get_statefulsets(self, namespace):
        """
        Get all StatefulSets in a namespace.
        
        Args:
            namespace: Namespace to query
            
        Returns:
            list: StatefulSet data
        """
        # Mock implementation - no statefulsets for simplicity
        return []
    
    def get_resource_quotas(self, namespace):
        """
        Get resource quotas for a namespace.
        
        Args:
            namespace: Namespace to query
            
        Returns:
            list: ResourceQuota data
        """
        # Mock implementation - no resource quotas for simplicity
        return []
    
    def get_current_time(self):
        """
        Get the current time in ISO 8601 format.
        
        Returns:
            str: Current time in ISO 8601 format
        """
        return datetime.now().isoformat()

    # Dummy methods for distributed tracing
    def get_trace_ids(self, service_name=None, error_only=False, limit=10):
        """
        Get a list of recent trace IDs.
        
        Args:
            service_name: Filter by service name (optional)
            error_only: Only return traces with errors
            limit: Maximum number of trace IDs to return
            
        Returns:
            list: Trace IDs
        """
        # Mock implementation - return some dummy trace IDs
        trace_ids = [
            "abc123def456ghi789",
            "def456ghi789jkl012",
            "ghi789jkl012mno345"
        ]
        return trace_ids[:limit]

    def get_trace_details(self, trace_id):
        """
        Get details for a specific trace.
        
        Args:
            trace_id: The trace ID to retrieve
            
        Returns:
            dict: Trace details
        """
        # Mock implementation - return some dummy trace details
        return {
            "traceId": trace_id,
            "duration": 1500,
            "services": [
                {"name": "frontend", "duration": 200},
                {"name": "backend", "duration": 1000, "error": False},
                {"name": "database", "duration": 300}
            ],
            "spans": [
                {"id": "span1", "name": "GET /api/data", "service": "frontend", "duration": 200, "error": False},
                {"id": "span2", "name": "Process request", "service": "backend", "duration": 1000, "error": False},
                {"id": "span3", "name": "Query database", "service": "database", "duration": 300, "error": False}
            ]
        }

    def get_service_latency_stats(self, service_name=None, time_range_minutes=30):
        """
        Get latency statistics for services.
        
        Args:
            service_name: Filter by service name (optional)
            time_range_minutes: Time range in minutes to analyze
            
        Returns:
            dict: Latency statistics
        """
        # Mock implementation - return some dummy latency stats
        stats = {
            "frontend": {
                "p50": 100,
                "p90": 200,
                "p95": 300,
                "p99": 500,
                "count": 1000
            },
            "backend": {
                "p50": 500,
                "p90": 900,
                "p95": 1200,
                "p99": 2000,
                "count": 800
            },
            "database": {
                "p50": 200,
                "p90": 300,
                "p95": 400,
                "p99": 600,
                "count": 600
            }
        }
        
        if service_name and service_name in stats:
            return {service_name: stats[service_name]}
        return stats

    def get_error_rate_by_service(self, time_range_minutes=30):
        """
        Get error rates for services.
        
        Args:
            time_range_minutes: Time range in minutes to analyze
            
        Returns:
            dict: Dictionary mapping service names to error rates
        """
        # Mock implementation - return some dummy error rates
        return {
            "frontend": 0.01,  # 1% error rate
            "backend": 0.05,   # 5% error rate
            "database": 0.15,  # 15% error rate
            "api-gateway": 0.25,  # 25% error rate
            "resource-service": 0.02  # 2% error rate
        }

    def get_service_dependencies(self, service_name=None):
        """
        Get service dependency map based on traces.
        
        Args:
            service_name: Central service to map dependencies for (optional)
            
        Returns:
            dict: Dictionary mapping services to their dependencies
        """
        # Mock implementation - return some dummy dependencies
        dependencies = {
            "frontend": ["backend", "api-gateway"],
            "backend": ["database", "resource-service"],
            "api-gateway": ["backend"],
            "resource-service": ["database"],
            "database": []
        }
        
        if service_name and service_name in dependencies:
            return {service_name: dependencies[service_name]}
        return dependencies

    def find_slow_operations(self, threshold_ms=1000, time_range_minutes=30):
        """
        Find unusually slow operations across services.
        
        Args:
            threshold_ms: Threshold in milliseconds to consider an operation slow
            time_range_minutes: Time range in minutes to analyze
            
        Returns:
            list: List of slow operations with their details
        """
        # Mock implementation - return some dummy slow operations
        return [
            {
                "service": "backend",
                "operation": "Process request",
                "average_duration_ms": 1200,
                "p95_duration_ms": 2000,
                "count": 100
            },
            {
                "service": "database",
                "operation": "Query user data",
                "average_duration_ms": 1500,
                "p95_duration_ms": 3000,
                "count": 50
            }
        ]

    def are_traces_available(self):
        """
        Check if distributed tracing is available.
        
        Returns:
            bool: True if tracing is available, False otherwise
        """
        # Mock implementation - return True for testing
        return True
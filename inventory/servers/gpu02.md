---
id: gpu-server-02
name: GPU Server 02
aliases:
  - gpu02
  - 4090 서버
type: gpu_server

network:
  hostname: gpu02.internal
  ip: 192.168.10.22
  subnet: 192.168.10.0/24

ssh:
  enabled: true
  port: 22023
  user: researcher

gpu:
  - model: NVIDIA RTX 4090
    count: 2

services:
  - name: vllm
    port: 8000

location: GPU Lab
status: active
---

# GPU Server 02

학습 및 배치 inference 용 GPU 서버.

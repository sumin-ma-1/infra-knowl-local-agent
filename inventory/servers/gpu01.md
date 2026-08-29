---
id: gpu-server-01
name: GPU Server 01
aliases:
  - gpu01
  - 5090 서버
type: gpu_server

network:
  hostname: gpu01.internal
  ip: 192.168.10.21
  subnet: 192.168.10.0/24

ssh:
  enabled: true
  port: 22022
  user: researcher

gpu:
  - model: NVIDIA RTX 5090
    count: 2

services:
  - name: ollama
    port: 11434
  - name: jupyter
    port: 8888

location: GPU Lab
status: active
---

# GPU Server 01

GUI Agent 및 VLM inference 용 GPU 서버.

## Notes

외부에서는 VPN 연결 후 SSH 접근 가능.

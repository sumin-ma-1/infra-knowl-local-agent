---
id: workstation-ai
name: AI Workstation
aliases:
  - workstation01
  - workstation-ai
type: workstation

network:
  hostname: ws-ai.internal
  ip: 192.168.20.41
  subnet: 192.168.20.0/24

ssh:
  enabled: true
  port: 22
  user: researcher

gpu:
  - model: NVIDIA RTX 3090
    count: 1

services:
  - name: jupyter
    port: 8888

location: Research Desk
status: active
---

# AI Workstation

연구용 데스크톱 워크스테이션.

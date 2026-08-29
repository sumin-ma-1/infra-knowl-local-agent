---
id: nas01
name: NAS 01
aliases:
  - nas
  - 스토리지
type: nas

network:
  hostname: nas01.internal
  ip: 192.168.20.10
  subnet: 192.168.20.0/24

ssh:
  enabled: true
  port: 22
  user: admin

services:
  - name: nextcloud
    port: 443
  - name: smb
    port: 445

location: Server Room
status: active
---

# NAS 01

연구 자료 및 Nextcloud 데이터 저장소.

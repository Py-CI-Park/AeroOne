"""Leantime 동거(co-deploy) 연결 모듈.

Leantime 은 AeroOne 에 흡수하지 않고 별도 스택(PHP·MariaDB·IIS)으로 나란히 운영한다.
이 모듈은 그 스택이 실제로 기동됐는지 TCP 로 가볍게 감지(health)해, 대시보드가 '설치·구동됨'
과 '미설치/미구동'을 실시간으로 구분해 보여줄 수 있게 한다. Leantime 데이터/DB 에는 접근하지
않는다(경계는 docs/runbook/leantime-codeploy.md).
"""

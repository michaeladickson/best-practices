@echo off
rem Task Scheduler entry point for the independent heartbeat check (CC-Heartbeats).
rem Runs on Windows python directly — no WSL needed (gh + python are native here).
cd /d C:\Users\micha\best-practices
python -X utf8 scripts\check_heartbeats.py >> logs\heartbeats.log 2>&1

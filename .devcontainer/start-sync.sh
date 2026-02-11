#!/bin/bash
sleep 5
cd /workspaces/vibefoundry-sandbox/app_folder
nohup python sync_server.py > /tmp/sync_server.log 2>&1 &

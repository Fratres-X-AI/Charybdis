#!/usr/bin/env bash
ssh -p 40077 -i ~/.ssh/id_ed25519 root@213.192.2.94 'grep "eval pass" /tmp/pod_max_gpu.log; grep "new_best" /tmp/pod_max_gpu.log; grep "PASS " /tmp/pod_max_gpu.log | tail -n 3; grep "FINAL" /tmp/pod_max_gpu.log; grep "4090 max ladder complete" /tmp/pod_max_gpu.log'

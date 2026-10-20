#!/bin/bash
# Tune macOS host TCP stack for high-bitrate HTTP Range media streaming (Sol / jellyfin-metal)
/usr/sbin/sysctl -w net.inet.tcp.sendspace=524288
/usr/sbin/sysctl -w net.inet.tcp.recvspace=524288
/usr/sbin/sysctl -w net.inet.tcp.autosndbufmax=8388608
/usr/sbin/sysctl -w net.inet.tcp.autorcvbufmax=8388608
/usr/sbin/sysctl -w net.inet.tcp.delayed_ack=2

#!/bin/bash
set -e

echo "[firewall] Applying firewall rules..."

# Flush all chains
iptables -F INPUT
iptables -F OUTPUT
iptables -F FORWARD

# ── INBOUND RULES ──────────────────────────
# Allow loopback
iptables -A INPUT -i lo -j ACCEPT

# Allow established/related (responses to our outbound)
iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT

# Block everything else inbound
iptables -A INPUT -j DROP

# ── OUTBOUND RULES ─────────────────────────
# Allow loopback
iptables -A OUTPUT -o lo -j ACCEPT

# Allow established/related
iptables -A OUTPUT -m state --state ESTABLISHED,RELATED -j ACCEPT

# Allow HTTP and HTTPS only
iptables -A OUTPUT -p tcp --dport 80  -j ACCEPT
iptables -A OUTPUT -p tcp --dport 443 -j ACCEPT

# Block everything else outbound
iptables -A OUTPUT -j DROP

echo "[firewall] Done. All inbound blocked. Only ports 80 and 443 allowed outbound."

exec "$@"

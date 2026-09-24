# Security Policy

## Supported versions

| Version | Supported |
|---|---|
| 1.0.x | ✅ |

## Reporting a vulnerability

Please **do not** open a public issue for a security problem.

Use GitHub's private reporting instead:
**Security → Report a vulnerability** on this repository.

Include what you can:

- what the problem is, and what an attacker could do with it
- the steps to reproduce it
- the version, your OS, and how you installed it

You will get a first reply within a few days.

## Scope

Nmap Studio builds and runs `nmap` command lines and parses what comes back.
Things worth reporting:

- a crafted scan result (XML, NSE output, hostname, service banner) that leads
  to code execution, file access, or anything beyond text on screen
- any path where user input reaches a shell — the app spawns `nmap` directly
  with an argument vector, never through a shell, so a break in that is a bug
- the elevation path (`pkexec` / `sudo`) being used to run something other than
  the nmap command shown in the Command bar

Out of scope: what nmap itself does once you run it, and Npcap, which is not
part of this project.

## A note on use

This is a front-end for a scanner. Scan only machines you own or have written
permission to test.

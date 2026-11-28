# Git Installation Guide (Windows)

This guide covers the Git installation step needed for the SOPRAS reviewer quick start. For Python, see [INSTALL_PYTHON.md](INSTALL_PYTHON.md). For MySQL, see [INSTALL_MYSQL.md](INSTALL_MYSQL.md).

## Download

Download Git for Windows from:

```text
https://git-scm.com/download/win
```

## Install

Run the installer and keep the default options. In particular, use:

- Git from the command line and also from third-party software.
- The bundled OpenSSH client.
- The OpenSSL library for HTTPS connections.
- The default Windows service and credential-manager options.

## Verify Git

Open a new PowerShell window and run:

```powershell
git --version
```

A version string such as `git version 2.x` confirms that Git is installed.

## Continue

After Git is installed, install Python as described in [INSTALL_PYTHON.md](INSTALL_PYTHON.md), then install MySQL as described in [INSTALL_MYSQL.md](INSTALL_MYSQL.md). Finally, continue with the reviewer quick start in the main [README](../README.md#quick-start-mysql).

## Screenshot Plan

Screenshots will be stored under `docs/images/install/`.

| File | Content |
|---|---|
| `git-01-download.png` | Git for Windows download page |
| `git-02-install-options.png` | Git installation options |
| `git-03-verify.png` | `git --version` verification |

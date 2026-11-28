# Installation Guide (Windows)

This guide covers the Git and MySQL installation steps needed for the SOPRAS reviewer quick start. Python can be downloaded from the mirror link in the main README.

## 1. Install Git

### Download

Download Git for Windows from:

```text
https://git-scm.com/download/win
```

### Install

Run the installer and keep the default options. In particular, use:

- Git from the command line and also from third-party software.
- The bundled OpenSSH client.
- The OpenSSL library for HTTPS connections.
- The default Windows service and credential-manager options.

### Verify Git

Open a new PowerShell window and run:

```powershell
git --version
```

A version string such as `git version 2.x` confirms that Git is installed.

## 2. Install MySQL

### Download MySQL Installer

Download the full offline MySQL Installer from the official MySQL downloads page.

The MySQL Installer program itself may be listed as 32-bit. This is expected: the installer can install a 64-bit MySQL Server.

### Select MySQL Server

Choose:

```text
MySQL Server 8.0 - x64
```

Do not select only the command-line client or the sample database.

### Configure the Server

Use the default port:

```text
3306
```

Start MySQL as a Windows service and allow it to start automatically.

### Set the Root Password

Set a password for the local `root` account and keep it in a safe place. Use the same password in `.env.reviewer`:

```text
DB_PASSWORD=your-mysql-password
```

Do not put the password in `DB_NAME` and do not commit `.env.reviewer` to Git.

### Complete the Configuration

Click `Execute` and wait until all configuration steps show `Complete`.

### Verify MySQL

Open a new PowerShell window and run:

```powershell
mysql --version
```

If MySQL is installed but the command is not found, add the MySQL `bin` directory to `PATH` or reopen PowerShell.

## 3. Return to the Main README

After Git and MySQL are installed, continue with the reviewer quick start in the main README.

## Screenshot Plan

Screenshots will be stored under `docs/images/install/`.

| File | Content |
|---|---|
| `git-01-download.png` | Git for Windows download page |
| `git-02-install-options.png` | Git installation options |
| `git-03-verify.png` | `git --version` verification |
| `mysql-01-installer-download.png` | MySQL Installer download |
| `mysql-02-select-server.png` | Select MySQL Server 8.0 - x64 |
| `mysql-03-port.png` | Port 3306 |
| `mysql-04-root-password.png` | Root password configuration |
| `mysql-05-service.png` | Windows service configuration |
| `mysql-06-complete.png` | Configuration completed |

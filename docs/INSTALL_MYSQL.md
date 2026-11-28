# MySQL Installation Guide (Windows)

This guide covers the MySQL installation step needed for the SOPRAS reviewer quick start. For Git, see [INSTALL_GIT.md](INSTALL_GIT.md).

## Download MySQL Installer

Download the full offline MySQL Installer from the official MySQL downloads page:

```text
https://dev.mysql.com/downloads/installer/
```

If the official CDN is slow, a domestic mirror is available. The mirror currently carries version 8.0.29:

```text
Directory:       https://mirrors.huaweicloud.com/mysql/Downloads/MySQLInstaller/
Offline package: https://mirrors.huaweicloud.com/mysql/Downloads/MySQLInstaller/mysql-installer-community-8.0.29.0.msi
Online package:  https://mirrors.huaweicloud.com/mysql/Downloads/MySQLInstaller/mysql-installer-web-community-8.0.29.0.msi
```

Prefer the full offline package (about 461 MB); the online package still downloads the server components from the official CDN. Any MySQL 8.0.x release is supported, so the patch version may differ from the one shown in the screenshots below.

The MySQL Installer program itself may be listed as 32-bit. This is expected: the installer can install a 64-bit MySQL Server.

## Select MySQL Server

Choose:

```text
MySQL Server 8.0 - x64
```

Do not select only the command-line client or the sample database.

## Configure the Server

Use the default port:

```text
3306
```

Start MySQL as a Windows service and allow it to start automatically.

## Set the Root Password

Set a password for the local `root` account and keep it in a safe place. Use the same password in `.env.reviewer`:

```text
DB_PASSWORD=your-mysql-password
```

Do not put the password in `DB_NAME` and do not commit `.env.reviewer` to Git.

## Complete the Configuration

Click `Execute` and wait until all configuration steps show `Complete`.

## Verify MySQL

Open a new PowerShell window and run:

```powershell
mysql --version
```

If MySQL is installed but the command is not found, add the MySQL `bin` directory to `PATH` or reopen PowerShell.

## Continue

After MySQL is installed, continue with the reviewer quick start in the main [README](../README.md#quick-start-mysql).

## Screenshot Plan

Screenshots will be stored under `docs/images/install/`.

| File | Content |
|---|---|
| `mysql-01-installer-download.png` | MySQL Installer download |
| `mysql-02-select-server.png` | Select MySQL Server 8.0 - x64 |
| `mysql-03-port.png` | Port 3306 |
| `mysql-04-root-password.png` | Root password configuration |
| `mysql-05-service.png` | Windows service configuration |
| `mysql-06-complete.png` | Configuration completed |

# MySQL Installation Guide (Windows)

This guide prepares a local MySQL 8.0 server for the SOPRAS reviewer quick start. The reviewer setup in the main README only needs MySQL, Python, and Git.

## 1. Download MySQL Installer

Download the full offline MySQL Installer from the official MySQL downloads page.

The MySQL Installer program itself may be listed as 32-bit. This is expected: the installer can install a 64-bit MySQL Server.

## 2. Select MySQL Server

Choose:

```text
MySQL Server 8.0 - x64
```

Do not select only the command-line client or the sample database.

## 3. Configure the Server

Use the default port:

```text
3306
```

Start MySQL as a Windows service and allow it to start automatically.

## 4. Set the Root Password

Set a password for the local `root` account and keep it in a safe place. Use the same password in `.env.reviewer`:

```text
DB_PASSWORD=your-mysql-password
```

Do not put the password in `DB_NAME` and do not commit `.env.reviewer` to Git.

## 5. Complete the Configuration

Click `Execute` and wait until all configuration steps show `Complete`.

## 6. Verify the Installation

Open a new PowerShell window and run:

```powershell
mysql --version
```

If MySQL is installed but the command is not found, add the MySQL `bin` directory to `PATH` or reopen PowerShell.

Then return to the main README and continue with the reviewer quick start.

## Screenshot Plan

The following screenshots should be added under `docs/images/mysql/`:

| File | Content |
|---|---|
| `01-installer-download.png` | MySQL Installer download |
| `02-select-server.png` | Select MySQL Server 8.0 - x64 |
| `03-port.png` | Port 3306 |
| `04-root-password.png` | Root password configuration |
| `05-service.png` | Windows service configuration |
| `06-complete.png` | Configuration completed |

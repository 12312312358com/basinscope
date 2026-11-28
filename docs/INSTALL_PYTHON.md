# Python Installation Guide (Windows)

This guide covers the Python installation step needed for the SOPRAS reviewer quick start. For Git, see [INSTALL_GIT.md](INSTALL_GIT.md). For MySQL, see [INSTALL_MYSQL.md](INSTALL_MYSQL.md).

Python 3.10 or later is required. The reviewer workflow below uses Python 3.12.10 for Windows x64.

## Download

Download the Python 3.12.10 Windows x64 installer from the Aliyun mirror:

```text
https://mirrors.aliyun.com/python-release/windows/python-3.12.10-amd64.exe
```

If you already have Python 3.10 or later, you may skip the installation and continue with the verification step.

## Install

Run the installer and:

1. Select **Add python.exe to PATH**.
2. Select **Install Now**.
3. Wait until the installation reports **Setup was successful**.
4. Close the installer.

Do not install the reviewer dependencies globally. The quick start creates a local virtual environment named `.venv-review`.

## Verify Python

Open a new PowerShell window and run:

```powershell
python --version
```

A result such as `Python 3.12.10` confirms that Python is available. Then check pip:

```powershell
python -m pip --version
```

If Windows opens the Microsoft Store when you run `python`, close it and rerun the Python installer. Select **Modify**, enable the PATH option, complete the installation, and open a new PowerShell window.

## Continue

After Python is installed, install MySQL as described in [INSTALL_MYSQL.md](INSTALL_MYSQL.md), then continue with the reviewer quick start in the main [README](../README.md#quick-start-mysql).

## Screenshot Plan

Screenshots will be stored under `docs/images/install/`.

| File | Content |
|---|---|
| `python-01-download.png` | Python 3.12.10 x64 installer download |
| `python-02-add-to-path.png` | Add Python to PATH |
| `python-03-verify.png` | `python --version` verification |
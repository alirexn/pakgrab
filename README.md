# 🪟 OpenWrt Package Downloader (Windows)

A smart tool powered by python for downloading OpenWrt packages with all their dependencies for offline use

This project provides a **Windows executable (.exe)** for easy usage, and the **original Python source code** is also included

The script works similarly to how opkg in OpenWrt downloads packages.

## ✨ Features

- Download any OpenWrt package
- Automatically resolve and download all dependencies
- Works like the real OpenWrt package manager
- Designed for offline package preparation
- Simple and easy to use
- Windows ready (.exe included)


> ⚠️ **Windows Notice**
>
> The project includes a ready-to-use **.exe version for Windows**, and also provides the original **Python source code**.  
> If Python or required dependencies are not installed on the system, the tool will automatically download and install them before running.


## ⚙️ How It Works

The script uses your firmware's `distfeeds.conf` file to access the correct OpenWrt repositories.

1. Place your `distfeeds.conf` file in the same folder as the script
2. Create a file named `packages.txt`
3. Add the packages you want to download (one package per line)
4. Run the program

The tool will :
- Read repository sources from `distfeeds.conf`
- Resolve dependencies
- Download all required packages automatically

Just like the OPKG in OpenWRT! 🥳

## 📦 Package Groups (Folder Organization)

You can also create groups to organize downloaded packages into separate folders.

This is useful if you want each package and its dependencies to be stored in a dedicated folder.

To do this, add a folder name starting with `/` in the `packages.txt` file.

Example :
```
/dnsmasq-full and depends
dnsmasq-full
```
The script will :

- Create a folder named **dnsmasq-full and depends**
- Download the package below it
- Download all required dependencies
- Save everything inside that folder

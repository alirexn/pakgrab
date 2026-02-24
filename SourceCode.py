import os
import sys
import subprocess
import re
from collections import defaultdict

# Color support with safe fallback
colorama_available = False
Fore = Style = None

try:
    from colorama import init, Fore, Style
    init(autoreset=True)
    colorama_available = True
except ImportError:
    print("colorama not found. Attempting to install automatically...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "colorama"])
        print("colorama installed successfully.")
        from colorama import init, Fore, Style
        init(autoreset=True)
        colorama_available = True
    except Exception:
        print("Failed to install colorama. Continuing without colors...")
        colorama_available = False

# Automatically install 'requests' if missing
try:
    import requests
except ImportError:
    print("Module 'requests' not found. Installing it now...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
        print("requests installed successfully.")
        import requests
    except Exception as e:
        print(f"Failed to install requests automatically: {e}")
        print("Please install manually: python -m pip install requests")
        sys.exit(1)

# ────────────────────────────────────────────────
REPO_FILE = "distfeeds.conf"
DOWNLOAD_DIR = "downloads"
PACKAGES_FILE = "packages.txt"

os.makedirs(DOWNLOAD_DIR, exist_ok=True)

downloaded = set()

SKIP_PACKAGES = {
    "libc", "libgcc", "libgcc1", "libpthread", "librt", "libm", "libdl",
    "libutil", "libresolv", "ld-linux", "ld.so", "libcrypt", "libnsl",
    "musl", "uClibc",
    "kernel", "kernel (=6.6.119~6a9e125268c43e0bae8cecb014c8ab03-r1)"
}

def load_repos_from_distfeeds():
    if not os.path.exists(REPO_FILE):
        if colorama_available:
            print(Fore.RED + f"File {REPO_FILE} not found!" + Style.RESET_ALL)
        else:
            print(f"File {REPO_FILE} not found!")
        if colorama_available:
            print(Fore.YELLOW + "Please create distfeeds.conf and add your src/gz lines." + Style.RESET_ALL)
        else:
            print("Please create distfeeds.conf and add your src/gz lines.")
        sys.exit(1)
    
    repos = []
    with open(REPO_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            match = re.match(r'^(src(?:/gz)?)\s+(\S+)\s+(https?://\S+)', line)
            if match:
                repo_name = match.group(2)
                repo_url  = match.group(3)
                repos.append({"name": repo_name, "url": repo_url})
            else:
                if re.search(r'https?://', line):
                    repos.append({"name": "unknown_repo", "url": line.strip()})
    
    if not repos:
        if colorama_available:
            print(Fore.RED + f"No valid repositories found in {REPO_FILE}!" + Style.RESET_ALL)
        else:
            print(f"No valid repositories found in {REPO_FILE}!")
        sys.exit(1)
    
    if colorama_available:
        print(Fore.GREEN + f"{len(repos)} repositories loaded from {REPO_FILE}:" + Style.RESET_ALL)
    else:
        print(f"{len(repos)} repositories loaded from {REPO_FILE}:")
    
    for r in repos:
        print(f"  - {r['name']}: {r['url']}")
    
    return repos

def download_file(url, dest):
    """
    Download file and replace old version if filename is different (newer version).
    """
    file_name = os.path.basename(dest)
    dir_path = os.path.dirname(dest)

    # Find any existing file with the same package name but possibly different version
    old_file = None
    for existing in os.listdir(dir_path):
        if existing.startswith(file_name.split('_')[0] + '_') and existing.endswith('.ipk'):
            old_file = os.path.join(dir_path, existing)
            break

    # If an older version exists, remove it
    if old_file and old_file != dest:
        print(f"Newer version detected. Removing old file: {os.path.basename(old_file)}")
        try:
            os.remove(old_file)
        except Exception as e:
            print(f"Warning: Could not remove old file {old_file}: {e}")

    # Now download if not already present (or after removal)
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        print(f"Already exists (current version): {file_name}")
        return True

    print(f"Downloading new version: {file_name}")
    try:
        r = requests.get(url, stream=True, timeout=30)
        r.raise_for_status()
        os.makedirs(dir_path, exist_ok=True)
        with open(dest, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        return True
    except Exception as e:
        print(f"Failed to download {url}: {e}")
        return False

def build_package_index(repo_urls):
    package_index = {}
    provides_index = defaultdict(list)
    
    total_text = ""
    for repo in repo_urls:
        print(f"Fetching index from repo: {repo['name']}")
        content = get_packages_content(repo['url'])
        if content:
            total_text += content + "\n\n"
    
    if not total_text:
        print("Failed to retrieve any Packages data.")
        sys.exit(1)
    
    current_package = None
    for line in total_text.splitlines():
        line = line.strip()
        if not line: continue
            
        if line.startswith("Package:"):
            current_package = line.split(":", 1)[1].strip()
            package_index[current_package] = {"depends": [], "filename": "", "provides": []}
        elif current_package:
            if line.startswith("Depends:"):
                deps = [d.strip() for d in re.split(r',\s*|\s*\|\s*', line.split(":", 1)[1].strip()) if d.strip()]
                package_index[current_package]["depends"] = deps
            elif line.startswith("Filename:"):
                package_index[current_package]["filename"] = line.split(":", 1)[1].strip()
            elif line.startswith("Provides:"):
                provs = [p.strip() for p in line.split(":", 1)[1].strip().split(",") if p.strip()]
                package_index[current_package]["provides"] = provs
                for p in provs:
                    provides_index[p].append(current_package)
    
    return package_index, provides_index

def resolve_and_download(pkg_name, pkg_index, prov_index, to_download_set, current_subdir=None):
    if pkg_name in SKIP_PACKAGES or pkg_name.startswith("kernel (="):
        return True

    if pkg_name in to_download_set or pkg_name in downloaded:
        return True
    
    if pkg_name not in pkg_index:
        if pkg_name in prov_index and prov_index[pkg_name]:
            real_pkg = prov_index[pkg_name][0]
            print(f"  {pkg_name} provided by → {real_pkg}")
            pkg_name = real_pkg
        else:
            print(f"  Skipping unresolved dependency: {pkg_name}")
            return True
    
    to_download_set.add(pkg_name)
    
    filename = pkg_index[pkg_name].get("filename", "")
    if not filename:
        print(f"  No Filename entry for: {pkg_name}")
        return False
    
    found = False
    repo_url = None
    for repo in REPO_URLS:
        test_url = f"{repo['url']}/{filename}"
        try:
            r = requests.head(test_url, timeout=2)
            if r.status_code == 200:
                url = test_url
                repo_url = repo['url']
                found = True
                break
        except:
            pass
    
    if not found:
        print(f"  Could not locate download URL for: {filename}")
        return False
    
    # Extract relative repository path after 'releases/24.10.5/'
    if "releases/24.10.5/" in repo_url:
        relative_path = repo_url.split("releases/24.10.5/")[-1]
    else:
        relative_path = "unknown_repo"
    
    # Build save path: group (if any) + relative repo path
    if current_subdir:
        base_save = os.path.join(DOWNLOAD_DIR, current_subdir, relative_path)
    else:
        base_save = os.path.join(DOWNLOAD_DIR, relative_path)
    
    dest = os.path.join(base_save, os.path.basename(filename))
    
    if download_file(url, dest):
        downloaded.add(pkg_name)
    
    for dep in pkg_index[pkg_name]["depends"]:
        resolve_and_download(dep, pkg_index, prov_index, to_download_set, current_subdir)
    
    return True

# ────────────────────────────────────────────────
if __name__ == "__main__":
    REPO_URLS = load_repos_from_distfeeds()
    
    if not os.path.exists(PACKAGES_FILE):
        print(f"Missing file: {PACKAGES_FILE}")
        print("Create packages.txt with package names (one per line).")
        sys.exit(1)
    
    print("\nLoading package indexes from distfeeds.conf repositories...\n")
    pkg_index, prov_index = build_package_index(REPO_URLS)
    
    print("\nResolving and downloading with full repository structure inside groups:\n")
    to_download = set()
    
    current_subdir = None
    with open(PACKAGES_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            
            if line.startswith("/"):
                current_subdir = line[1:].strip()
                print(f"\nStarting group: {current_subdir}")
                continue
            
            pkg = line
            print(f"• {pkg} (in {current_subdir if current_subdir else 'main'})")
            resolve_and_download(pkg, pkg_index, prov_index, to_download, current_subdir)
    
    if colorama_available:
        print(Fore.GREEN + f"\nFinished. Downloaded {len(downloaded)} packages." + Style.RESET_ALL)
        print(Fore.CYAN + f"Files → {os.path.abspath(DOWNLOAD_DIR)}" + Style.RESET_ALL)
        input(Fore.YELLOW + "\nPress Enter to Exit..." + Style.RESET_ALL)
    else:
        print(f"\nFinished. Downloaded {len(downloaded)} packages.")
        print(f"Files → {os.path.abspath(DOWNLOAD_DIR)}")
        input("\nPress Enter to Exit...")

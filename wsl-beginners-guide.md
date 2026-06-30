# WSL Beginner's Guide — Level Up Course

> **What you'll walk away with:** The ability to install WSL, navigate Linux from your Windows machine, move files between both systems, and run real Linux commands daily — without fear.

---

## Before You Start

**What is WSL?**
WSL (Windows Subsystem for Linux) lets you run a real Linux terminal directly inside Windows — no virtual machine, no dual boot. You get Linux tools, Linux file paths, and Linux commands living side-by-side with your normal Windows apps.

**What you need:**
- Windows 10 version 2004+ or Windows 11
- A few minutes and an internet connection

---

## Level 1 — Install WSL and Get Online

**Goal:** Have a working Linux terminal open on your Windows machine.

### Step 1: Open PowerShell as Administrator

Press `Win` → type `PowerShell` → right-click → **Run as administrator**.

### Step 2: Run the install command

```powershell
wsl --install
```

This one command does everything:
- Enables the WSL feature in Windows
- Downloads and installs the Linux kernel
- Installs Ubuntu as your default Linux distribution
- Sets WSL 2 as the default version

Restart your computer when prompted.

### Step 3: First launch

After restart, Ubuntu opens automatically and asks you to create a username and password. This is your Linux account — it does **not** have to match your Windows username.

> **Why does the password not show as I type?** Linux hides passwords while you type for security. It's working — just type and press Enter.

### Step 4: Verify it worked

Open PowerShell (no need for admin this time) and run:

```powershell
wsl --status
```

You should see `Default Version: 2`. That means you're on WSL 2 — the fast, modern version.

**Level 1 Complete.** You have Linux running on Windows.

---

## Level 2 — Understand the Terminal

**Goal:** Stop being scared of the terminal. Understand what you're looking at.

### The prompt explained

When your terminal opens, you see something like:

```
yourname@DESKTOP-ABC123:~$
```

| Part | What it means |
|---|---|
| `yourname` | Your Linux username |
| `DESKTOP-ABC123` | Your computer's name |
| `~` | Your current location (home directory) |
| `$` | You're a regular user (not admin) |

### The most important concept: where am I?

Linux organizes everything as a tree of folders starting from `/` (called "root"). Your home folder lives at `/home/yourname`, but Linux shortens it to `~` for convenience.

### Step 1: Print your current location

```bash
pwd
```

Output: `/home/yourname` — you're in your home directory.

### Step 2: List what's here

```bash
ls
```

Nothing yet — your home folder is empty on a fresh install. Try:

```bash
ls -la
```

| Flag | What it adds |
|---|---|
| `-l` | Long format — shows permissions, size, date |
| `-a` | All files — shows hidden files (ones starting with `.`) |

### Step 3: Move around

```bash
cd /          # Go to the root of the entire filesystem
ls            # See what's there
cd ~          # Jump back home instantly
```

> **Tip:** `cd` with no arguments always takes you home. When lost, just type `cd`.

### Step 4: Look at a manual

Every command has a built-in manual:

```bash
man ls
```

Press arrow keys to scroll, press `q` to quit. This works for almost every command.

**Level 2 Complete.** You can navigate the terminal without panic.

---

## Level 3 — Essential Linux Commands

**Goal:** Learn the daily-driver commands you'll use every single time you open a terminal.

### Working with directories

```bash
mkdir projects              # Create a folder called "projects"
mkdir -p projects/web/css   # Create nested folders all at once (-p = parents)
cd projects                 # Enter the folder
cd ..                       # Go up one level
cd ../..                    # Go up two levels
rmdir projects              # Delete an EMPTY folder
```

### Working with files

```bash
# Create and view files
echo "Hello, Linux!" > hello.txt    # Write text into a new file
cat hello.txt                        # Print file contents to terminal
less hello.txt                       # View large files (q to quit)

# Copy, move, delete
cp hello.txt hello-backup.txt        # Copy a file
mv hello.txt renamed.txt             # Rename (move) a file
mv renamed.txt projects/             # Move file into a folder
rm hello-backup.txt                  # Delete a file

# Delete a folder and everything inside it
rm -r projects/
```

> **Warning:** Linux has no Recycle Bin. `rm` deletes permanently. Be careful with `rm -r`.

### Searching and counting

```bash
wc hello.txt           # Count lines, words, and characters in a file
wc -l hello.txt        # Count lines only

sort names.txt         # Sort file lines alphabetically
uniq names.txt         # Remove duplicate lines (must be sorted first)
sort names.txt | uniq  # Sort then remove duplicates — pipe two commands together
```

### The pipe `|` — your superpower

The pipe sends the output of one command into the next:

```bash
ls -la | less          # View a long file listing one page at a time
echo "world" | wc -c  # Count the characters in "world"
```

### Redirection — saving output to a file

```bash
ls > filelist.txt       # Save ls output to a file (overwrites)
ls >> filelist.txt      # Append ls output to an existing file
```

### Getting help fast

```bash
man cp          # Full manual for cp
cp --help       # Quick flag reference (works for most commands)
```

**Level 3 Complete.** You can create, read, move, and delete files from the command line.

---

## Level 4 — WSL Commands from PowerShell

**Goal:** Control WSL itself — manage distributions, check versions, shut things down.

These commands run in **PowerShell or Command Prompt** (not inside Linux). Think of them as the "remote control" for your Linux environment.

### See what you have installed

```powershell
wsl --list --verbose
# Short form:
wsl -l -v
```

Output looks like:

```
  NAME      STATE           VERSION
* Ubuntu    Running         2
```

The `*` marks your default distribution.

### Check and set WSL version

```powershell
# See the WSL version being used
wsl --status

# Upgrade a specific distro to WSL 2
wsl --set-version Ubuntu 2

# Make WSL 2 the default for all future installs
wsl --set-default-version 2
```

### Install more Linux distributions

```powershell
# See everything available
wsl --list --online

# Install a specific one
wsl --install -d Debian
wsl --install -d kali-linux
```

### Switch your default distribution

```powershell
wsl --set-default Ubuntu
```

### Shut down WSL

```powershell
# Stop a specific distro
wsl --terminate Ubuntu

# Stop ALL running WSL instances
wsl --shutdown
```

> **When to use `--shutdown`:** If WSL feels sluggish or something is stuck, a shutdown clears everything and gives you a fresh start.

### Update the Linux kernel

```powershell
wsl --update
```

### Export and import (backup your whole Linux setup)

```powershell
# Save your entire Ubuntu install to a file
wsl --export Ubuntu C:\Backups\ubuntu-backup.tar

# Restore it on this or another machine
wsl --import Ubuntu C:\WSL\Ubuntu C:\Backups\ubuntu-backup.tar

# Start fresh — unregister and delete a distro
wsl --unregister Ubuntu
```

### Run a single Linux command from PowerShell without entering Linux

```powershell
wsl ls -la
wsl pwd
wsl echo "Hello from Linux"
```

**Level 4 Complete.** You can manage WSL from PowerShell like a pro.

---

## Level 5 — Files: Understanding Two Worlds

**Goal:** Understand how Windows and Linux file systems connect, and know where to put your files.

### The two file systems

You have two separate file systems running at once:

| System | Root path in Linux | Example |
|---|---|---|
| Linux filesystem | `/` | `/home/yourname/projects` |
| Windows C: drive | `/mnt/c/` | `/mnt/c/Users/YourName/Desktop` |

### Accessing Windows files from Linux

Your Windows drives are automatically mounted under `/mnt/`:

```bash
ls /mnt/c/                              # Browse your C: drive
ls /mnt/c/Users/YourName/Documents/    # Your Windows Documents folder
cd /mnt/c/Users/YourName/Desktop       # Go to your Windows Desktop
cp myfile.txt /mnt/c/Users/YourName/Desktop/  # Copy a file to Windows Desktop
```

### Accessing Linux files from Windows

Inside Windows Explorer, type this in the address bar:

```
\\wsl$\Ubuntu\home\yourname
```

Or open any WSL terminal and run:

```bash
explorer.exe .
```

This opens the current Linux folder in Windows Explorer. You can drag, drop, and edit files normally.

### The golden rule: where to store your files

| Task | Store files HERE | Why |
|---|---|---|
| Linux development (coding, git, npm) | Linux filesystem (`~/projects`) | Much faster I/O |
| Windows apps (Word, Photoshop, etc.) | Windows filesystem (`/mnt/c/...`) | Apps expect Windows paths |
| Shared access needed | Linux filesystem, open via `\\wsl$\...` | Best of both worlds |

> **Performance warning:** Running Linux tools (like `npm install`, `git clone`, `make`) on files stored in `/mnt/c/` is significantly slower than working in the Linux filesystem. Keep project files in `~/` for speed.

### Practical example: start a project the right way

```bash
# In your Linux terminal:
mkdir ~/projects
cd ~/projects
mkdir my-website
cd my-website

# Open this folder in VS Code from Linux
code .
```

VS Code will open the Linux folder natively via the Remote - WSL extension.

### Linux file permissions (quick reference)

```bash
ls -la
```

Output example:
```
-rw-r--r-- 1 yourname yourname  42 Jun 30 10:00 hello.txt
drwxr-xr-x 2 yourname yourname 4096 Jun 30 10:00 projects/
```

| Character | Meaning |
|---|---|
| `d` | Directory |
| `-` | Regular file |
| `r` | Read permission |
| `w` | Write permission |
| `x` | Execute permission |
| First 3 chars after type | Owner's permissions |
| Next 3 | Group's permissions |
| Last 3 | Everyone else's permissions |

Change permissions:

```bash
chmod +x script.sh    # Make a file executable
chmod 644 file.txt    # Owner: read+write, everyone else: read-only
```

**Level 5 Complete.** You know where files live and how to move between both worlds.

---

## Level 6 — Everyday Power Skills

**Goal:** The commands and habits that make you actually productive in WSL daily.

### sudo — temporary admin powers

Some commands need administrator (root) access. Prefix them with `sudo`:

```bash
sudo apt update           # Update the list of available packages
sudo apt upgrade          # Install all available updates
sudo apt install git      # Install git
sudo apt install python3  # Install Python 3
```

> **Rule:** Never blindly copy-paste a `sudo` command from the internet. Read it first and understand what it does.

### Update your Linux packages regularly

Make this a habit when you first open WSL:

```bash
sudo apt update && sudo apt upgrade -y
```

`&&` runs the second command only if the first succeeded. `-y` automatically says "yes" to all prompts.

### Find things

```bash
# Find a file by name
find ~ -name "hello.txt"

# Find all .md files in current folder
find . -name "*.md"

# Search inside files for a word
grep "error" logfile.txt          # Find lines containing "error"
grep -r "TODO" ~/projects/        # Search recursively through all files
grep -i "error" logfile.txt       # Case-insensitive search
```

### View running processes

```bash
ps aux           # List all running processes
top              # Live view of CPU/memory usage (press q to quit)
```

### Useful shortcuts

| Shortcut | What it does |
|---|---|
| `Ctrl + C` | Kill the running command |
| `Ctrl + L` | Clear the terminal screen |
| `Tab` | Autocomplete filenames and commands |
| `Tab Tab` | Show all possible completions |
| Up arrow | Cycle through previous commands |
| `Ctrl + R` | Search command history |
| `!!` | Repeat the last command |
| `sudo !!` | Re-run the last command with sudo |

### Environment variables

```bash
echo $HOME      # Your home directory path
echo $PATH      # Where Linux looks for commands
echo $USER      # Your username

# Set a temporary variable (gone when terminal closes)
export MY_VAR="hello"
echo $MY_VAR
```

### Interoperability — run Windows apps from Linux

```bash
# Open current folder in Windows Explorer
explorer.exe .

# Open a file with the default Windows app
cmd.exe /c start myfile.pdf

# Open VS Code in current Linux directory
code .

# Run a Windows executable from Linux
/mnt/c/Windows/System32/notepad.exe
```

**Level 6 Complete.** You're no longer just surviving in the terminal — you're productive.

---

## Quick Reference Card

### Navigation
```bash
pwd           # Where am I?
ls -la        # What's here (including hidden files)?
cd ~/projects # Go to projects folder in home
cd ..         # Go up one level
cd -          # Go back to previous directory
```

### Files
```bash
cp a.txt b.txt          # Copy
mv a.txt b.txt          # Rename/move
rm a.txt                # Delete file
rm -r folder/           # Delete folder
mkdir -p a/b/c          # Create nested folders
cat file.txt            # Print file
less file.txt           # View file (q to quit)
echo "text" > file.txt  # Write to file
echo "text" >> file.txt # Append to file
```

### WSL Control (run in PowerShell)
```bash
wsl -l -v                      # List distros and versions
wsl --shutdown                 # Stop all WSL instances
wsl --update                   # Update WSL kernel
wsl --install -d <distro>      # Install a distro
wsl --export Ubuntu backup.tar # Backup Ubuntu
```

### Windows ↔ Linux Files
```bash
/mnt/c/Users/Name/   # Your Windows C: drive from Linux
explorer.exe .       # Open current Linux folder in Windows Explorer
\\wsl$\Ubuntu\home\  # Access Linux files from Windows Explorer
```

### Packages
```bash
sudo apt update           # Refresh package list
sudo apt upgrade -y       # Install all updates
sudo apt install <name>   # Install a package
sudo apt remove <name>    # Remove a package
apt search <keyword>      # Search for packages
```

---

## Common Questions (FAQ)

**Can WSL access the internet?**
Yes — WSL shares your Windows network connection automatically.

**Can I run graphical Linux apps?**
Yes, on Windows 11 (and updated Windows 10). WSL 2 includes WSLg which supports GUI Linux apps out of the box.

**Will WSL slow down my computer?**
WSL 2 only uses resources when you're actively running it. When not in use it consumes minimal resources.

**What's the difference between WSL 1 and WSL 2?**
WSL 2 uses a real Linux kernel in a lightweight VM. It's faster for most Linux tasks, supports Docker, and has better compatibility. WSL 1 had better Windows file system performance (for files on `/mnt/c/`), but WSL 2 is the recommended default for almost everyone.

**Can I install packages I'm used to from Linux?**
Yes — Ubuntu in WSL uses `apt`, the same package manager as desktop Ubuntu. Any package available for Ubuntu works here.

**Do I need to leave WSL running all the time?**
No. WSL starts when you open a terminal and you can stop it with `wsl --shutdown`. Your files and settings are preserved.

**My Linux terminal is stuck — what do I do?**
In PowerShell run `wsl --shutdown`, then reopen your Linux terminal. That restarts everything cleanly.

---

## What's Next

You've covered the essentials. Here's where to go from here:

| Skill | What to learn |
|---|---|
| Coding | Install `git`, `python3`, `node`, `gcc` with `apt` |
| Shell scripting | Write `.sh` scripts to automate repetitive tasks |
| Text editing | Learn `nano` (beginner-friendly) or `vim` (powerful) |
| Networking | Learn `curl`, `wget`, `ssh` for web and server tasks |
| Docker | WSL 2 runs Docker Desktop natively — great for web dev |

Good luck — you've got this.

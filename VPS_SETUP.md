# VPS Setup Instructions for b3sitechecker

This guide will help you set up and run `b3sitechecker.py` on a VPS (Virtual Private Server).

## Prerequisites

- Ubuntu/Debian-based VPS (recommended)
- Python 3.8 or higher
- Root or sudo access

## Step 1: Update System Packages

```bash
sudo apt update
sudo apt upgrade -y
```

## Step 2: Install Python and pip

```bash
sudo apt install python3 python3-pip -y
```

Verify installation:
```bash
python3 --version
pip3 --version
```

## Step 3: Install System Dependencies for Playwright

Playwright requires additional system libraries:

```bash
sudo apt install -y \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libcairo2 \
    libatspi2.0-0 \
    libxshmfence1
```

## Step 4: Upload Files to VPS

Upload the following files to your VPS:
- `b3sitechecker.py`
- `requirements.txt`
- `config.py` (if you have one)

You can use `scp` or `rsync`:

```bash
scp b3sitechecker.py requirements.txt user@your-vps-ip:/path/to/destination/
```

## Step 5: Install Python Dependencies

SSH into your VPS and navigate to the directory where you uploaded the files:

```bash
cd /path/to/your/files
pip3 install -r requirements.txt
```

## Step 6: Install Playwright Browsers

Playwright needs to download browser binaries:

```bash
playwright install chromium
```

Or install all browsers:
```bash
playwright install
```

## Step 7: (Optional) Set Up Virtual Environment

It's recommended to use a virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

To activate the virtual environment later:
```bash
source venv/bin/activate
```

## Step 8: Run the Script

```bash
python3 b3sitechecker.py
```

Or if using virtual environment:
```bash
source venv/bin/activate
python3 b3sitechecker.py
```

## Running in Background (Optional)

To run the script in the background and keep it running after disconnecting:

### Using nohup:
```bash
nohup python3 b3sitechecker.py > output.log 2>&1 &
```

### Using screen:
```bash
# Install screen
sudo apt install screen -y

# Start a new screen session
screen -S b3checker

# Run your script
python3 b3sitechecker.py

# Detach: Press Ctrl+A then D
# Reattach: screen -r b3checker
```

### Using tmux:
```bash
# Install tmux
sudo apt install tmux -y

# Start a new tmux session
tmux new -s b3checker

# Run your script
python3 b3sitechecker.py

# Detach: Press Ctrl+B then D
# Reattach: tmux attach -t b3checker
```

## Troubleshooting

### Playwright Issues
If you encounter issues with Playwright, try:
```bash
playwright install --force chromium
```

### Permission Issues
If you get permission errors, you might need to run with sudo or fix permissions:
```bash
sudo chmod +x b3sitechecker.py
```

### Display Issues (for headless mode)
If running in headless mode, ensure you have the necessary display libraries. The script should work in headless mode by default, but if you need to run with a display:

```bash
# Install Xvfb for virtual display
sudo apt install xvfb -y

# Run with virtual display
xvfb-run -a python3 b3sitechecker.py
```

## Important: Headless Mode for VPS

The script currently runs with `headless=False` (visible browser). For VPS without a display, you have two options:

### Option 1: Use Xvfb (Virtual Display)
```bash
sudo apt install xvfb -y
xvfb-run -a python3 b3sitechecker.py
```

### Option 2: Enable Headless Mode (Recommended for VPS)
Edit `b3sitechecker.py` and change line ~1283:
```python
# Change from:
headless=False,  # Visible browser

# To:
headless=True,  # Headless browser for VPS
```

## Notes

- The script uses Playwright which requires browser binaries (~200MB download)
- For headless operation on VPS, set `headless=True` in the browser launch options (line ~1283)
- Monitor disk space as logs and screenshots may accumulate
- Consider setting up log rotation for long-running processes
- If you need to see what's happening, use Xvfb or enable VNC/X11 forwarding


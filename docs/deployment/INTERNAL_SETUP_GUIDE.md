# Internal Setup Guide: Bank Pilot Deployment

> **Who is this for?** Internal team members setting up pilot deployments
> **Skill level assumed:** Basic command line familiarity, no development experience required
> **Time to complete:** 2-4 hours depending on scenario

This guide walks you through every possible setup scenario step-by-step. Follow the path that matches your situation.

---

## Table of Contents

1. [Before You Start](#before-you-start)
2. [Scenario A: Demo Mode (Quickest)](#scenario-a-demo-mode)
3. [Scenario B: Pilot with Real Domain](#scenario-b-pilot-with-real-domain)
4. [Scenario C: Full Bank Integration](#scenario-c-full-bank-integration)
5. [Add-On: SSO Authentication](#add-on-sso-authentication)
6. [Add-On: Account Context Feed](#add-on-account-context-feed)
7. [Troubleshooting](#troubleshooting)
8. [Glossary](#glossary)

---

## Before You Start

### What You Need on Your Computer

| Tool | What it is | How to check if you have it |
|------|------------|----------------------------|
| Docker Desktop | Runs our application in containers | Type `docker --version` in terminal |
| Git | Downloads our code | Type `git --version` in terminal |
| A text editor | To edit configuration files | VS Code, Notepad++, or even Notepad |
| Terminal/Command Prompt | To type commands | Already on your computer |

### How to Open a Terminal

**On Mac:**
1. Press `Cmd + Space`
2. Type "Terminal"
3. Press Enter

**On Windows:**
1. Press `Windows key`
2. Type "PowerShell" or "Command Prompt"
3. Press Enter

### Understanding the Folder Structure

After you download our code, you'll see this structure:

```
Check/
├── backend/           ← The server (you won't touch this)
├── frontend/          ← The website (you won't touch this)
├── connector/         ← Bank image connector (for advanced setups)
├── docker/            ← WHERE YOU'LL WORK MOST
│   ├── docker-compose.pilot.yml    ← Main configuration
│   ├── .env.pilot.example          ← Template for secrets
│   ├── nginx.conf                  ← Web server config
│   └── certs/                      ← TLS certificates go here
└── docs/              ← Documentation (you're reading one now)
```

---

## Scenario A: Demo Mode

**Use this when:** You want to show the system to someone quickly, or train users before connecting to real bank data.

**What you get:** A fully working system with fake check images and sample data.

**Time required:** About 30 minutes

### Step A1: Download the Code

Open your terminal and type these commands one at a time:

```bash
# Go to where you want to put the project
cd ~/Desktop

# Download the code
git clone https://github.com/YourOrg/Check.git

# Go into the project folder
cd Check
```

**What this does:** Downloads all the application files to your Desktop in a folder called "Check".

### Step A2: Go to the Docker Folder

```bash
cd docker
```

**What this does:** Moves you into the folder where all the configuration files are.

### Step A3: Create Your Configuration File

```bash
# Copy the example file
cp .env.pilot.example .env.pilot
```

**What this does:** Creates your personal configuration file from the template.

### Step A4: Generate Secret Keys

You need 4 secret keys. Run this command 4 times, saving each result:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

Each time you run it, you'll get something like:
```
Ks8j2nF_xQ7mP3rT9vB5wY1zA4cE6hG8
```

**Save these somewhere temporarily** - you'll need them in the next step.

### Step A5: Edit Your Configuration File

Open the file `docker/.env.pilot` in a text editor.

Find these lines and replace the placeholder text with your generated keys:

```bash
# Database (make up a password - just letters and numbers, no spaces)
POSTGRES_USER=check_review_user
POSTGRES_PASSWORD=MySecurePassword123

# Paste your 4 generated keys here (one per line)
SECRET_KEY=paste-your-first-key-here
CSRF_SECRET_KEY=paste-your-second-key-here
NETWORK_PEPPER=paste-your-third-key-here
IMAGE_SIGNING_KEY=paste-your-fourth-key-here

# For demo mode
DEMO_MODE=true
```

**Save the file.**

### Step A6: Create Test Certificates

For demo mode, we'll create temporary certificates:

```bash
# Create the certificates folder
mkdir -p certs

# Generate a test certificate (just press Enter for all questions)
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout certs/server.key \
  -out certs/server.crt \
  -subj "/CN=localhost"
```

**What this does:** Creates temporary security certificates that let your browser connect securely. These are fine for testing but shouldn't be used for real deployments.

### Step A7: Start the Application

```bash
# Build and start everything
docker compose -f docker-compose.pilot.yml --env-file .env.pilot up -d
```

**What this does:**
- Downloads all necessary components
- Builds the application
- Starts everything running in the background

This takes 5-10 minutes the first time. You'll see lots of text scrolling by - that's normal.

### Step A8: Check That Everything Started

Wait 2 minutes, then run:

```bash
docker compose -f docker-compose.pilot.yml ps
```

You should see something like:
```
NAME                    STATUS
check_review_db         running (healthy)
check_review_redis      running (healthy)
check_review_backend    running (healthy)
check_review_frontend   running (healthy)
check_review_nginx      running (healthy)
```

**If any show "unhealthy" or "restarting"**, see [Troubleshooting](#troubleshooting).

### Step A9: Access the Application

1. Open your web browser
2. Go to: `https://localhost`
3. You'll see a security warning (because we used test certificates) - click "Advanced" then "Proceed" or "Accept the Risk"
4. You should see the login page

### Step A10: Log In with Demo Accounts

Use any of these test accounts:

| Username | Password | What they can do |
|----------|----------|------------------|
| `reviewer` | `reviewer123` | View and decide on checks |
| `supervisor` | `supervisor123` | All above + reassign work |
| `administrator` | `admin123` | All above + manage users |

**Congratulations!** You have a working demo. Skip to [Common Tasks](#common-tasks) for next steps.

---

## Scenario B: Pilot with Real Domain

**Use this when:** A bank will access the system over the internet at a real web address like `https://pilot.yourcompany.com`.

**What you need:**
- A domain name (like `pilot.yourcompany.com`)
- A server with a public IP address
- Real TLS certificates

**Time required:** About 2 hours

### Step B1: Complete Scenario A First

Do all steps in Scenario A to make sure the basic setup works.

### Step B2: Stop the Demo

```bash
docker compose -f docker-compose.pilot.yml down
```

### Step B3: Get Your Domain Ready

You need:
1. **A domain name** pointing to your server's IP address
2. **TLS certificates** for that domain

**If you don't have certificates yet**, you can get free ones from Let's Encrypt:

```bash
# Install certbot (on Ubuntu/Debian)
sudo apt-get update
sudo apt-get install certbot

# Get certificates (replace with your actual domain)
sudo certbot certonly --standalone -d pilot.yourcompany.com
```

The certificates will be saved to `/etc/letsencrypt/live/pilot.yourcompany.com/`

### Step B4: Copy Certificates to the Project

```bash
# Copy the certificate files (replace domain with yours)
sudo cp /etc/letsencrypt/live/pilot.yourcompany.com/fullchain.pem docker/certs/server.crt
sudo cp /etc/letsencrypt/live/pilot.yourcompany.com/privkey.pem docker/certs/server.key

# Make sure they're readable
sudo chmod 644 docker/certs/server.crt
sudo chmod 600 docker/certs/server.key
```

### Step B5: Update Your Configuration

Edit `docker/.env.pilot` and update the CORS setting:

```bash
# Change this line to your actual domain
CORS_ORIGINS=["https://pilot.yourcompany.com"]
```

**Important:** The domain must match exactly, including `https://`.

### Step B6: Disable Demo Mode (Optional)

If you want real data instead of fake data:

```bash
# In .env.pilot, change:
DEMO_MODE=false
```

**Note:** With `DEMO_MODE=false`, there won't be any check data until you connect a bank's image system (Scenario C).

### Step B7: Start the Application

```bash
docker compose -f docker-compose.pilot.yml --env-file .env.pilot up -d
```

### Step B8: Test Your Domain

1. Open a browser
2. Go to `https://pilot.yourcompany.com`
3. You should see the login page without any certificate warnings

**If you see certificate warnings**, your certificates aren't set up correctly. See [Troubleshooting](#troubleshooting).

---

## Scenario C: Full Bank Integration

**Use this when:** You're connecting a real bank with real check images.

**What you need:**
- Completed Scenario B (real domain, real certificates)
- Bank IT contact who can deploy the connector
- Bank's image storage information

**Time required:** 1-2 weeks (mostly waiting for bank IT)

### Understanding the Integration

```
┌─────────────────────────────────────────────────────────┐
│                    BANK NETWORK                          │
│                                                         │
│   ┌──────────────┐         ┌──────────────┐            │
│   │ Check Images │ ───────▶│  Connector   │            │
│   │ (File Share) │         │  (You help   │            │
│   └──────────────┘         │   install)   │            │
│                            └──────┬───────┘            │
└───────────────────────────────────┼─────────────────────┘
                                    │ HTTPS (encrypted)
                                    ▼
┌───────────────────────────────────────────────────────────┐
│                   YOUR SERVER                              │
│                                                           │
│   ┌─────────┐    ┌──────────┐    ┌──────────┐            │
│   │  Nginx  │───▶│ Backend  │───▶│ Database │            │
│   │  (TLS)  │    │          │    │          │            │
│   └─────────┘    └──────────┘    └──────────┘            │
│                                                           │
└───────────────────────────────────────────────────────────┘
```

**How it works:**
1. Check images stay on the bank's servers
2. The connector (installed at the bank) fetches images when requested
3. Images are shown to reviewers but never permanently stored on our servers

### Step C1: Gather Bank Information

You need this information from the bank:

| Information | Example | Who provides it |
|-------------|---------|-----------------|
| Image storage path | `\\fileserver\Checks\Transit\` | Bank IT |
| Image format | TIFF | Bank IT |
| Service account name | `svc_checkreview` | Bank IT |
| Network requirements | "Need firewall rule for outbound 443" | Bank IT |

### Step C2: Generate Connector Keys

The connector needs a cryptographic key pair for secure communication.

On your server, run:

```bash
cd ~/Check/connector

# Generate the key pair
python scripts/mint_token.py --generate-keys
```

This creates two files:
- `connector_private.pem` - **Give to bank IT** (they keep this secret)
- `connector_public.pem` - **You keep this** (register in admin panel)

### Step C3: Send Connector Package to Bank

Create a package for the bank IT team:

```bash
# Create a folder with everything they need
mkdir bank_connector_package
cp -r connector/* bank_connector_package/
cp docs/connectors/CONNECTOR_SETUP.md bank_connector_package/SETUP_INSTRUCTIONS.md
```

Send them:
1. The `bank_connector_package` folder
2. Your server's public key (`saas_public.pem`)
3. Your server's URL (e.g., `https://pilot.yourcompany.com`)

### Step C4: Wait for Bank to Install Connector

The bank IT team will:
1. Set up a server inside their network
2. Install Docker on that server
3. Configure the connector with their image paths
4. Start the connector
5. Tell you when it's ready

**This typically takes 3-7 business days** depending on their change management process.

### Step C5: Register the Connector in Admin Panel

Once the bank confirms their connector is running:

1. Log into your system as administrator
2. Go to **Admin → Image Connectors → Add New**
3. Enter:
   - **Connector ID:** `bank-001-prod` (or whatever you agreed on)
   - **Base URL:** The connector's URL (bank provides this)
   - **Public Key:** Paste contents of `connector_public.pem`
4. Click **Test Connection**
5. If successful, click **Save**

### Step C6: Verify Images Load

1. Log in as a reviewer
2. Navigate to the check queue
3. Click on a check item
4. Verify the check image displays

**If images don't load**, see [Troubleshooting](#troubleshooting).

### Step C7: Set Up Decision Output

The bank needs to receive decision files (approve/return decisions).

**Option 1: SFTP (Most Common)**

Get from bank:
- SFTP host: `sftp.bank.com`
- SFTP port: `22`
- Username: `checkreview`
- Password or SSH key

Add to `docker/.env.pilot`:
```bash
# Decision output via SFTP
DECISION_OUTPUT_TYPE=sftp
DECISION_SFTP_HOST=sftp.bank.com
DECISION_SFTP_PORT=22
DECISION_SFTP_USER=checkreview
DECISION_SFTP_PASSWORD=their-password
DECISION_SFTP_PATH=/incoming/decisions/
```

**Option 2: Shared Folder**

If the bank prefers a network share:

```bash
# Decision output via shared folder
DECISION_OUTPUT_TYPE=folder
DECISION_FOLDER_PATH=/mnt/bank-share/decisions/
```

You'll need to mount the bank's share on your server (requires network connectivity to bank).

Restart after configuration:
```bash
docker compose -f docker-compose.pilot.yml --env-file .env.pilot down
docker compose -f docker-compose.pilot.yml --env-file .env.pilot up -d
```

---

## Add-On: SSO Authentication

**Use this when:** The bank wants their employees to log in with their existing company credentials (like Okta, Azure AD, etc.)

### Understanding SSO

Without SSO:
- Users have a separate username/password for Check Review
- You manage all user accounts

With SSO:
- Users log in with their bank credentials
- The bank controls who has access
- No separate passwords to manage

### Step SSO1: Get Bank's SSO Information

Ask the bank's IT team for:

| Information | What it looks like | Notes |
|-------------|-------------------|-------|
| SSO Provider | Okta, Azure AD, Ping, etc. | |
| Protocol | SAML 2.0 or OIDC | We support both |
| Metadata URL or file | `https://bank.okta.com/app/.../metadata` | For SAML |
| Client ID | `0oa1234567890abcdef` | For OIDC |
| Client Secret | `abc123...` | For OIDC |

### Step SSO2: Configure SSO

**For SAML:**

Add to `docker/.env.pilot`:
```bash
# SSO Configuration (SAML)
SSO_ENABLED=true
SSO_PROVIDER=saml
SAML_METADATA_URL=https://bank.okta.com/app/xxxxx/sso/saml/metadata
SAML_ENTITY_ID=check-review-console
```

**For OIDC:**

Add to `docker/.env.pilot`:
```bash
# SSO Configuration (OIDC)
SSO_ENABLED=true
SSO_PROVIDER=oidc
OIDC_CLIENT_ID=0oa1234567890abcdef
OIDC_CLIENT_SECRET=your-client-secret-here
OIDC_ISSUER_URL=https://bank.okta.com
```

### Step SSO3: Restart the Application

```bash
docker compose -f docker-compose.pilot.yml --env-file .env.pilot down
docker compose -f docker-compose.pilot.yml --env-file .env.pilot up -d
```

### Step SSO4: Test SSO Login

1. Go to your login page
2. You should see a "Login with SSO" button
3. Clicking it should redirect to the bank's login page
4. After logging in there, you should return to Check Review

### Step SSO5: Map Roles (Important!)

You need to tell the system which bank users get which roles.

In the admin panel:
1. Go to **Admin → SSO Settings**
2. Configure role mappings:
   - Bank AD Group `Check_Reviewers` → Role `reviewer`
   - Bank AD Group `Check_Supervisors` → Role `supervisor`
   - Bank AD Group `Check_Admins` → Role `administrator`

---

## Add-On: Account Context Feed

**Use this when:** The bank wants reviewers to see account information (balance, history) alongside check images.

### Understanding Context Feeds

Without context:
- Reviewers see the check image and amount only

With context:
- Reviewers see: current balance, account age, recent activity, risk indicators
- Helps make better decisions

### Step CTX1: Define What Data the Bank Will Provide

Common fields:

| Field | Required? | Example |
|-------|-----------|---------|
| Account Number | Yes | `1234567890` |
| Current Balance | Yes | `5432.10` |
| Average Balance (30 day) | Recommended | `4200.00` |
| Account Open Date | Recommended | `2019-03-15` |
| Account Type | Optional | `Checking` |
| Recent Check Count | Optional | `12` |

### Step CTX2: Create a File Specification

The bank needs to know exactly what format to send. Share this template:

```
ACCOUNT_CONTEXT_YYYYMMDD.csv

Format: CSV with header row
Encoding: UTF-8
Delimiter: Comma

Columns:
1. account_number (required) - Account identifier
2. current_balance (required) - Current balance as decimal
3. average_balance_30d (optional) - 30-day average
4. account_open_date (optional) - YYYY-MM-DD format
5. account_type (optional) - Text description
6. check_count_30d (optional) - Integer count

Example:
account_number,current_balance,average_balance_30d,account_open_date,account_type,check_count_30d
1234567890,5432.10,4200.00,2019-03-15,Checking,12
0987654321,1250.75,1100.00,2021-08-22,Savings,3
```

### Step CTX3: Set Up File Transfer

**Option A: Bank Pushes to Your SFTP**

You provide:
- SFTP host: your server
- Username/password or SSH key

Add to `docker/.env.pilot`:
```bash
CONTEXT_FEED_ENABLED=true
CONTEXT_FEED_TYPE=sftp_receive
CONTEXT_FEED_PATH=/data/context_feeds/
```

**Option B: You Pull from Bank's SFTP**

Bank provides:
- SFTP host: their server
- Credentials

Add to `docker/.env.pilot`:
```bash
CONTEXT_FEED_ENABLED=true
CONTEXT_FEED_TYPE=sftp_pull
CONTEXT_SFTP_HOST=sftp.bank.com
CONTEXT_SFTP_USER=checkreview
CONTEXT_SFTP_PASSWORD=their-password
CONTEXT_SFTP_PATH=/outgoing/context/
CONTEXT_PULL_SCHEDULE=0 5 * * *  # 5am daily
```

### Step CTX4: Restart and Verify

```bash
docker compose -f docker-compose.pilot.yml --env-file .env.pilot down
docker compose -f docker-compose.pilot.yml --env-file .env.pilot up -d
```

Once a context file is loaded, you'll see account details on check review screens.

---

## Common Tasks

### Starting the System

```bash
cd ~/Check/docker
docker compose -f docker-compose.pilot.yml --env-file .env.pilot up -d
```

### Stopping the System

```bash
cd ~/Check/docker
docker compose -f docker-compose.pilot.yml down
```

### Viewing Logs

To see what's happening:

```bash
# All logs
docker compose -f docker-compose.pilot.yml logs

# Just backend logs
docker compose -f docker-compose.pilot.yml logs backend

# Follow logs in real-time (Ctrl+C to stop)
docker compose -f docker-compose.pilot.yml logs -f backend
```

### Checking System Health

```bash
# Quick status check
docker compose -f docker-compose.pilot.yml ps

# Detailed health check
curl -k https://localhost/health
```

### Restarting After Configuration Changes

```bash
docker compose -f docker-compose.pilot.yml down
docker compose -f docker-compose.pilot.yml --env-file .env.pilot up -d
```

### Creating a Backup

```bash
# Backup the database
docker exec check_review_db pg_dump -U check_review_user -d check_review > backup_$(date +%Y%m%d).sql

# Backup your configuration
cp docker/.env.pilot backups/.env.pilot.$(date +%Y%m%d)
```

### Restoring from Backup

```bash
# Stop the application
docker compose -f docker-compose.pilot.yml down

# Restore the database
cat backup_20260115.sql | docker exec -i check_review_db psql -U check_review_user -d check_review

# Start again
docker compose -f docker-compose.pilot.yml --env-file .env.pilot up -d
```

---

## Troubleshooting

### Problem: "Container is unhealthy"

**Symptoms:** `docker compose ps` shows a container as "unhealthy" or "restarting"

**Solution:**
1. Check the logs:
   ```bash
   docker compose -f docker-compose.pilot.yml logs backend
   ```
2. Look for error messages in red or with "ERROR"
3. Common causes:
   - Missing environment variable → Check `.env.pilot` has all required values
   - Database not ready → Wait 30 seconds and try again
   - Port already in use → Stop other applications using ports 80/443

### Problem: "Certificate errors in browser"

**Symptoms:** Browser shows "Your connection is not private" or similar

**Solutions:**
- **For localhost/demo:** Click "Advanced" → "Proceed anyway"
- **For real domains:** Your certificates aren't correct
  1. Verify certificate files exist: `ls -la docker/certs/`
  2. Verify they match your domain: `openssl x509 -in docker/certs/server.crt -text | grep CN`
  3. Regenerate if needed (see Step B3-B4)

### Problem: "Cannot connect to server"

**Symptoms:** Browser shows "This site can't be reached"

**Solutions:**
1. Check containers are running: `docker compose ps`
2. Check ports are open: `curl -k https://localhost/health`
3. Check firewall allows 80/443
4. Check domain DNS points to correct IP

### Problem: "Login fails"

**Symptoms:** Correct password shows "Invalid credentials"

**Solutions:**
1. Demo accounts only work if `DEMO_MODE=true`
2. Check the backend logs: `docker compose logs backend | grep -i auth`
3. Try resetting demo data:
   ```bash
   docker compose exec backend python -m scripts.seed_db --reset
   ```

### Problem: "Images don't load"

**Symptoms:** Check detail page shows broken image icon

**Solutions:**
1. Connector not registered → Check Admin → Image Connectors
2. Connector offline → Ask bank IT to check connector status
3. Network issue → Test connectivity between your server and bank connector

### Problem: "Decisions aren't being sent"

**Symptoms:** Bank says they're not receiving decision files

**Solutions:**
1. Check SFTP credentials are correct
2. Check the folder path exists on bank's SFTP
3. Check backend logs for SFTP errors:
   ```bash
   docker compose logs backend | grep -i sftp
   ```

---

## Glossary

| Term | Plain English Meaning |
|------|----------------------|
| **Container** | A packaged application that runs in isolation |
| **Docker** | Software that runs containers |
| **Docker Compose** | Tool to run multiple containers together |
| **TLS/SSL** | Encryption that makes HTTPS secure |
| **Certificate** | A file that proves your server's identity |
| **CORS** | Security setting that controls which websites can talk to your API |
| **SFTP** | Secure file transfer (like FTP but encrypted) |
| **SSO** | Single Sign-On - log in once, access multiple systems |
| **SAML/OIDC** | Protocols (languages) for SSO |
| **Environment Variable** | A setting you configure outside the code |
| **Connector** | Software installed at the bank that fetches images |

---

## Quick Reference Card

### Key Folders
```
~/Check/docker/           ← Configuration files
~/Check/docker/certs/     ← TLS certificates
~/Check/docker/.env.pilot ← Your settings (secrets!)
```

### Key Commands
```bash
# Start
docker compose -f docker-compose.pilot.yml --env-file .env.pilot up -d

# Stop
docker compose -f docker-compose.pilot.yml down

# Status
docker compose -f docker-compose.pilot.yml ps

# Logs
docker compose -f docker-compose.pilot.yml logs -f backend
```

### Key URLs
```
https://localhost/           ← Application (demo)
https://your-domain.com/     ← Application (production)
https://localhost/health     ← Health check
https://localhost/api/v1/docs ← API documentation (if enabled)
```

### Demo Accounts
```
reviewer / reviewer123       ← Basic reviewer
supervisor / supervisor123   ← Supervisor
administrator / admin123     ← Full admin
```

---

## Getting Help

| Issue | Contact |
|-------|---------|
| This guide is unclear | Document feedback → documentation@yourcompany.com |
| Technical problem | Internal Slack → #check-review-support |
| Bank-side issue | Escalate to bank's IT contact |

---

*Document Version: 1.0 | Last Updated: January 2026*

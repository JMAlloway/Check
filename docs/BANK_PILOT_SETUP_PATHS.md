# Bank Pilot Setup Paths

> **Who is this for?** Bank project managers, IT coordinators, and operations leads who need to understand what's involved in setting up the Check Review Console.
>
> **How to use this guide:** Answer the questions in each section. Your answers will tell you which setup path to follow.

---

## Quick Overview

The Check Review Console connects to your bank in up to three ways:

| Connection | What it does | Required? |
|------------|--------------|-----------|
| **Images** | Shows check images to reviewers | Yes |
| **Decisions** | Sends reviewer decisions back to your core system | Yes |
| **Account Info** | Shows account details alongside checks (balance, history) | Optional but recommended |

Your answers to a few key questions determine how complex your setup will be.

---

## Question 1: How will you provide check images?

This is the most important decision. Pick the option that best describes your situation:

### Option A: "We want to try it first with fake data"
**→ Demo Mode (Easiest)**

✅ Best for:
- Initial evaluation
- Training staff before go-live
- Proof of concept

📋 What's involved:
- Nothing from your IT team
- We provide sample check images
- Can be running in 1 day

⏭️ **[Go to: Demo Mode Setup](#path-1-demo-mode)**

---

### Option B: "Our check images are on a Windows file server"
**→ On-Premise Connector**

✅ Best for:
- Most community banks
- Banks using Director Pro, ITI, or similar
- Images stored on internal network shares

📋 What's involved:
- Small software installation on one Windows or Linux server
- Read-only access to your image folders
- Firewall rule to allow outbound HTTPS
- Typical timeline: 1-2 weeks

⏭️ **[Go to: Connector Setup](#path-2-on-premise-connector)**

---

### Option C: "Our images are in the cloud (AWS, Azure, etc.)"
**→ Cloud Integration**

✅ Best for:
- Banks using cloud-based image archival
- Modernized infrastructure

📋 What's involved:
- API credentials for your cloud storage
- IAM role or service principal configuration
- Typical timeline: 1-2 weeks

⏭️ **[Go to: Cloud Integration](#path-3-cloud-integration)**

---

## Question 2: How should decisions get back to your system?

After a reviewer approves or returns a check, that decision needs to reach your core banking system. Pick one:

### Option A: "Drop a file on our SFTP server"
**→ SFTP File Drop (Most Common)**

✅ Best for:
- Banks with existing automated file processing
- Core systems that import decision files

📋 What you provide:
- SFTP server address and credentials
- Desired file format (CSV, fixed-width, etc.)
- File naming convention

---

### Option B: "Put the file on a shared folder"
**→ Shared Folder Drop**

✅ Best for:
- Smaller banks with manual processes
- Simpler IT environments

📋 What you provide:
- Network path to the shared folder
- Service account with write access

---

### Option C: "Call our API when a decision is made"
**→ Real-Time API (Advanced)**

✅ Best for:
- Banks wanting immediate decision posting
- Modern core banking integrations

📋 What you provide:
- API endpoint URL
- Authentication method
- Expected request/response format

---

## Question 3: Do you want account information shown alongside checks?

This is optional but helps reviewers make better decisions.

### Option A: "Yes, show us account balances and history"
**→ Account Context Feed**

📋 What you provide:
- Daily export file with account data (we'll specify the format)
- SFTP location to drop the file, OR
- API endpoint we can call

Benefits:
- Reviewers see current balance
- Account age and check history visible
- Better fraud detection

---

### Option B: "No, just show us the checks"
**→ Basic Mode**

📋 What's involved:
- Nothing additional needed
- Reviewers see check images and amounts only

---

## Question 4: How will your staff log in?

### Option A: "Just give them usernames and passwords"
**→ Built-in Authentication (Default)**

📋 What's involved:
- We create accounts for your users
- Users set their own passwords on first login
- Password requirements: 12+ characters, complexity enforced

---

### Option B: "We want to use our company login (SSO)"
**→ Single Sign-On**

📋 What you provide:
- SSO provider (Okta, Azure AD, Ping, etc.)
- SAML metadata file or OIDC configuration
- Attribute mapping for roles

Timeline: Adds 3-5 days for SSO configuration

---

# Setup Paths

Based on your answers above, follow the appropriate path below.

---

## Path 1: Demo Mode

**You chose:** Fake data for evaluation/training

### What We Do
1. Provide you access to a demo environment
2. Pre-load sample check images and scenarios
3. Create test user accounts

### What You Do
1. Provide names and emails for demo users
2. Schedule a 30-minute orientation call
3. Try the system with your team

### Timeline
- Day 1: Access granted
- Day 1-5: Team evaluation
- Day 5: Decision call (proceed to production or not)

### Next Steps
When ready for real data, return to this guide and choose a different image option.

**[→ Skip to: User Setup](#user-setup)**

---

## Path 2: On-Premise Connector

**You chose:** Check images on Windows file server

### What We Provide
- Connector software (small application, ~50MB)
- Installation guide with screenshots
- Public key for secure communication

### What You Provide

| Item | Who Provides | Notes |
|------|--------------|-------|
| Windows or Linux server | Your IT | Minimum: 2 CPU, 4GB RAM, 10GB disk |
| Read-only access to image shares | Your IT | Service account that can read check images |
| Firewall rule | Your IT | Allow outbound HTTPS (port 443) to our service |
| Image path format | Your operations | Example: `\\server\Checks\Transit\{date}\{trace}.tif` |

### Step-by-Step

#### Step 1: Prepare the Server (Your IT Team)
- [ ] Provision a Windows Server 2019+ or Linux server
- [ ] Install Docker (we provide instructions)
- [ ] Create a service account (e.g., `svc_checkreview`)
- [ ] Grant read-only access to check image folders

#### Step 2: Network Configuration (Your IT Team)
- [ ] Allow outbound HTTPS (443) to `*.checkreview.com`
- [ ] If using a proxy, note the proxy address

#### Step 3: Install Connector (Joint Effort)
- [ ] Download connector package from secure link we provide
- [ ] Run installation script
- [ ] Enter configuration (image paths, service account)
- [ ] Test connection to our service

#### Step 4: Verify Images (Joint Effort)
- [ ] We send test requests for sample images
- [ ] Confirm images display correctly in console
- [ ] Sign off on image integration

### Timeline
| Task | Duration | Who |
|------|----------|-----|
| Server provisioning | 1-3 days | Your IT |
| Network/firewall changes | 1-5 days | Your IT |
| Connector installation | 2-4 hours | Joint |
| Testing and verification | 1-2 days | Joint |
| **Total** | **1-2 weeks** | |

### Troubleshooting

**"The connector can't reach the internet"**
→ Check firewall rules, verify proxy settings if applicable

**"Images aren't loading"**
→ Verify service account has read access to the image paths

**"Connection test fails"**
→ Verify DNS resolution, check that port 443 outbound is open

**[→ Continue to: Decision Output Setup](#decision-output-setup)**

---

## Path 3: Cloud Integration

**You chose:** Check images in cloud storage (S3, Azure Blob, etc.)

### What You Provide

| Item | Notes |
|------|-------|
| Cloud provider | AWS S3, Azure Blob Storage, or Google Cloud Storage |
| Bucket/container name | Where images are stored |
| Access credentials | IAM role ARN, service principal, or access keys |
| Path pattern | How images are organized (e.g., `checks/{date}/{trace}.tiff`) |

### Step-by-Step

#### For AWS S3:
1. Create an IAM role with read-only S3 access to the image bucket
2. Provide us the role ARN
3. We configure cross-account access

#### For Azure Blob:
1. Create a service principal with Blob Reader role
2. Provide us the tenant ID, client ID, and client secret
3. We configure the integration

### Timeline
| Task | Duration | Who |
|------|----------|-----|
| Credential provisioning | 1-2 days | Your IT |
| Configuration | 1 day | Us |
| Testing | 1-2 days | Joint |
| **Total** | **3-5 days** | |

**[→ Continue to: Decision Output Setup](#decision-output-setup)**

---

## Decision Output Setup

**How reviewer decisions get back to your system**

### If You Chose: SFTP File Drop

#### What You Provide
| Item | Example |
|------|---------|
| SFTP host | `sftp.yourbank.com` |
| Port | `22` (default) or custom |
| Username | `checkreview_svc` |
| Authentication | SSH key (we provide our public key) or password |
| Upload directory | `/incoming/check_decisions/` |
| File format | CSV or fixed-width |

#### File Contents
We'll send a file with these fields (customizable):
- Transaction ID
- Decision (APPROVE / RETURN / HOLD)
- Reviewer username
- Decision timestamp
- Return reason code (if applicable)
- Supervisor approval (if required)

#### Timing
- Files sent: Every 15 minutes (configurable)
- Or: On-demand when batch is complete

### If You Chose: Shared Folder

#### What You Provide
| Item | Example |
|------|---------|
| Network path | `\\fileserver\Incoming\CheckDecisions\` |
| Service account | `DOMAIN\svc_checkreview` (with write access) |

#### Our Connector Will:
- Write decision files to this folder
- Use a naming convention you specify
- Optionally create a "processed" acknowledgment file

### If You Chose: Real-Time API

#### What You Provide
| Item | Example |
|------|---------|
| Endpoint URL | `https://api.yourbank.com/decisions` |
| Authentication | API key, OAuth, or certificate |
| Expected format | JSON or XML |

#### We Will:
- Call your API immediately when a decision is made
- Retry on failure (configurable)
- Log all attempts for audit

**[→ Continue to: Account Context (Optional)](#account-context-setup-optional)**

---

## Account Context Setup (Optional)

**Showing account information alongside checks**

If you chose to include account context:

### What You Provide Daily
A file containing:
| Field | Required? | Notes |
|-------|-----------|-------|
| Account number | Yes | Primary matching key |
| Current balance | Yes | As of export time |
| 30-day average balance | Recommended | Helps spot anomalies |
| Account open date | Recommended | Flags new accounts |
| Account type | Optional | Checking, savings, etc. |
| Check count (30 days) | Optional | Activity level |
| Returned items (12 months) | Optional | Risk indicator |

### How to Send
**Option A: SFTP Upload**
- Drop file to SFTP location we specify
- Naming: `ACCOUNT_CONTEXT_YYYYMMDD.csv`
- Timing: Before your first check batch of the day

**Option B: We Pull from Your SFTP**
- You provide SFTP credentials
- We pull the file each morning

### File Format
We support:
- CSV (recommended, easiest)
- Fixed-width (if required by your core system)
- JSON (for modern integrations)

**[→ Continue to: User Setup](#user-setup)**

---

## User Setup

### User Roles Explained

| Role | What They Can Do | Typical Staff |
|------|------------------|---------------|
| **Reviewer** | View checks, make decisions | Tellers, operations staff |
| **Senior Reviewer** | All above + approve high-value items | Senior operations staff |
| **Supervisor** | All above + reassign work, manage queues | Team leads |
| **Administrator** | All above + create users, set policies | Operations manager |
| **Auditor** | View-only access to all history | Compliance team |

### What We Need From You

| Information | Example |
|-------------|---------|
| User list | Name, email, role for each person |
| Dual control threshold | Dollar amount requiring supervisor approval (e.g., $5,000) |
| Working hours | When reviewers will be active (for SLA tracking) |

### Account Creation Process

1. You provide user list (spreadsheet is fine)
2. We create accounts and send welcome emails
3. Users click link to set password
4. Users log in and complete brief orientation

---

## Go-Live Checklist

Before your pilot goes live, verify:

### Technical
- [ ] Check images loading correctly
- [ ] Test decisions reaching your system
- [ ] Account context displaying (if applicable)
- [ ] All users can log in

### Operational
- [ ] Users completed training
- [ ] Escalation contacts identified
- [ ] Support process documented
- [ ] Backup reviewer coverage planned

### Sign-Off
- [ ] IT lead approval
- [ ] Operations lead approval
- [ ] Compliance acknowledgment (if required)

---

## Common Questions

### "How long does this take?"
| Setup Type | Typical Timeline |
|------------|------------------|
| Demo mode | 1 day |
| Connector + basic | 1-2 weeks |
| Connector + context feed | 2-3 weeks |
| Full integration with SSO | 3-4 weeks |

### "What if we get stuck?"
- Email support with your bank name and issue
- Response within 2 business hours
- We can schedule screen-share troubleshooting

### "Can we change options later?"
Yes. You can:
- Start with demo → add real images later
- Start without account context → add it later
- Start with passwords → add SSO later

### "What does the connector have access to?"
- **Read-only** access to check images only
- Cannot modify, delete, or access other files
- All access is logged and auditable

### "Where is our data stored?"
- US-based data centers
- Encrypted at rest and in transit
- See our SOC 2 report for details

---

## Your Next Steps

1. **Complete the [Technical Intake Questionnaire](./BANK_INTAKE_QUESTIONNAIRE.md)** if you haven't already
2. **Identify your contact** for each area:
   - IT/Server admin
   - Network/Firewall admin
   - Core banking system
   - Operations lead
3. **Schedule kickoff call** with our team
4. **Share this document** with your team so everyone understands the process

---

## Contact

| Question Type | Contact |
|---------------|---------|
| General/Sales | sales@checkreview.com |
| Technical Setup | onboarding@checkreview.com |
| Urgent Issues | support@checkreview.com |

---

*Document Version: 1.0 | Last Updated: January 2026*

#!/bin/bash
# Setup script for Summer 2027 Internship Tracker
# Run this ONCE to configure email and schedule daily runs

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLIST_NAME="com.lokesh.interntracker"
PLIST_PATH="$HOME/Library/LaunchAgents/$PLIST_NAME.plist"

echo ""
echo "╔═══════════════════════════════════════════════════╗"
echo "║     Summer 2027 Internship Tracker — Setup        ║"
echo "╚═══════════════════════════════════════════════════╝"
echo ""

# ── Step 1: Gmail App Password ────────────────────────────────────────────────
echo "STEP 1: Gmail App Password"
echo "──────────────────────────"
echo "You need a Gmail App Password (NOT your regular password)."
echo "Get one at: https://myaccount.google.com/apppasswords"
echo "  1. Sign in to Google Account"
echo "  2. Security → 2-Step Verification (must be ON)"
echo "  3. App passwords → Create → Name: 'Intern Tracker'"
echo "  4. Copy the 16-character password shown"
echo ""
read -rsp "Paste your Gmail App Password (input hidden): " APP_PASS
echo ""

if [[ -z "$APP_PASS" ]]; then
    echo "❌ No password entered. Aborting."
    exit 1
fi

# Save to a local .env file (not committed to git)
cat > "$SCRIPT_DIR/.env" <<EOF
GMAIL_USER=3lokesharora@gmail.com
GMAIL_APP_PASSWORD=jkxf mgcp lebv whmr
RECIPIENT_EMAIL=3lokesharora@gmail.com
EOF
chmod 600 "$SCRIPT_DIR/.env"
echo "✅ Saved credentials to $SCRIPT_DIR/.env (chmod 600)"

# ── Step 2: Test email ────────────────────────────────────────────────────────
echo ""
echo "STEP 2: Sending test email..."
cd "$SCRIPT_DIR"
set -a; source .env; set +a
python3 -c "
import smtplib, os
from email.mime.text import MIMEText
user = os.environ['GMAIL_USER']
pwd  = os.environ['GMAIL_APP_PASSWORD']
to   = os.environ['RECIPIENT_EMAIL']
msg = MIMEText('<h3>Intern Tracker is configured!</h3><p>Daily updates will arrive each morning at 8 AM.</p>', 'html')
msg['Subject'] = '[Intern Tracker] Setup successful!'
msg['From'] = user
msg['To'] = to
with smtplib.SMTP_SSL('smtp.gmail.com', 465) as s:
    s.login(user, pwd)
    s.sendmail(user, to, msg.as_string())
print('✅ Test email sent to', to)
"

# ── Step 3: Install launchd plist (runs daily at 8 AM) ───────────────────────
echo ""
echo "STEP 3: Scheduling daily run at 8:00 AM..."

mkdir -p "$HOME/Library/LaunchAgents"

cat > "$PLIST_PATH" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$PLIST_NAME</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>$SCRIPT_DIR/tracker.py</string>
    </array>
    <key>EnvironmentVariables</key>
    <dict>
        <key>GMAIL_USER</key>
        <string>3lokesharora@gmail.com</string>
        <key>GMAIL_APP_PASSWORD</key>
        <string>$APP_PASS</string>
        <key>RECIPIENT_EMAIL</key>
        <string>3lokesharora@gmail.com</string>
    </dict>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>8</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>$SCRIPT_DIR/tracker.log</string>
    <key>StandardErrorPath</key>
    <string>$SCRIPT_DIR/tracker.log</string>
    <key>RunAtLoad</key>
    <false/>
</dict>
</plist>
EOF

# Load the launchd job
launchctl unload "$PLIST_PATH" 2>/dev/null || true
launchctl load "$PLIST_PATH"
echo "✅ Scheduled: runs daily at 8:00 AM"

# ── Step 4: Run now ───────────────────────────────────────────────────────────
echo ""
read -rp "Run tracker NOW to get today's results? [Y/n]: " RUN_NOW
RUN_NOW="${RUN_NOW:-Y}"
if [[ "$RUN_NOW" =~ ^[Yy] ]]; then
    echo ""
    echo "Running tracker (this may take 2-5 minutes)..."
    set -a; source "$SCRIPT_DIR/.env"; set +a
    python3 "$SCRIPT_DIR/tracker.py"
fi

echo ""
echo "╔═══════════════════════════════════════════════════╗"
echo "║  ✅ All done! Tracker is active.                  ║"
echo "║  📧 Daily email at 8 AM → 3lokesharora@gmail.com ║"
echo "║  📄 Logs: $SCRIPT_DIR/tracker.log    ║"
echo "║  🏢 Companies: companies.json                     ║"
echo "╚═══════════════════════════════════════════════════╝"
echo ""
echo "Useful commands:"
echo "  Run manually:      cd $SCRIPT_DIR && python3 tracker.py"
echo "  Stop scheduler:    launchctl unload $PLIST_PATH"
echo "  Restart scheduler: launchctl load $PLIST_PATH"
echo "  View logs:         tail -f $SCRIPT_DIR/tracker.log"
echo "  Add a company:     edit companies.json"

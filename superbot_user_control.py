import os
import subprocess
import signal
import json
import time
import logging
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters

BOT_TOKEN = 'YOUR_TELEGRAM_BOT_TOKEN'
ADMIN_USER_ID = 7316824198
LOG_FILE = 'bot_activity.log'
STATE_FILE = 'running_bots.json'
USERS_FILE = 'allowed_users.json'

current_dir = os.path.expanduser("~")
running_processes = {}
allowed_users = set()

logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format='%(asctime)s - %(message)s')

def log_action(msg):
    print(msg)
    logging.info(msg)

def save_state():
    with open(STATE_FILE, 'w') as f:
        json.dump(running_processes, f)

def load_state():
    global running_processes
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            try:
                running_processes = json.load(f)
            except:
                running_processes = {}

def save_users():
    with open(USERS_FILE, 'w') as f:
        json.dump(list(allowed_users), f)

def load_users():
    global allowed_users
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r') as f:
            try:
                allowed_users = set(json.load(f))
            except:
                allowed_users = set()

def is_process_alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except:
        return False

async def restart_bot(script):
    if script in running_processes:
        try:
            os.kill(running_processes[script], signal.SIGKILL)
        except:
            pass
        del running_processes[script]

    full_path = os.path.join(current_dir, script)
    if os.path.isfile(full_path):
        proc = subprocess.Popen(["python3", full_path], cwd=current_dir)
        running_processes[script] = proc.pid
        log_action(f"[AUTO-RESTART] Restarted {script} (PID: {proc.pid})")
        save_state()
        return proc.pid
    return None

async def heartbeat():
    while True:
        await asyncio.sleep(60)
        to_restart = []
        for script, pid in list(running_processes.items()):
            if not is_process_alive(pid):
                to_restart.append(script)
        for script in to_restart:
            await restart_bot(script)

async def handle_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_dir
    user_id = update.effective_user.id

    command = update.message.text.strip()
    log_action(f"[COMMAND] {user_id} > {command}")

    if user_id != ADMIN_USER_ID and user_id not in allowed_users:
        await update.message.reply_text("Access denied.")
        return

    # Admin-only commands
    if user_id == ADMIN_USER_ID:
        if command.startswith("adduser "):
            new_id = command[8:].strip()
            if new_id.isdigit():
                allowed_users.add(int(new_id))
                save_users()
                await update.message.reply_text(f"User {new_id} added.")
            else:
                await update.message.reply_text("Invalid user ID.")
            return

        if command.startswith("deluser "):
            rem_id = command[8:].strip()
            if rem_id.isdigit() and int(rem_id) in allowed_users:
                allowed_users.remove(int(rem_id))
                save_users()
                await update.message.reply_text(f"User {rem_id} removed.")
            else:
                await update.message.reply_text("User not found.")
            return

    # Special command: ./depstx ip port duration thread
    if command.startswith("./depstx"):
        if user_id in allowed_users:
            try:
                result = subprocess.run(command, shell=True, capture_output=True, text=True, cwd=current_dir, timeout=600)
                output = result.stdout.strip() + "
" + result.stderr.strip()
            except Exception as e:
                output = f"Error: {str(e)}"
            output = output.strip() or "Command executed."
            for i in range(0, len(output), 4000):
                await update.message.reply_text(output[i:i+4000])
        else:
            await update.message.reply_text("You are not allowed to use this command.")
        return

    # Default to original command logic
    await update.message.reply_text("Unknown command or not allowed here.")

app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_command))

if __name__ == '__main__':
    log_action("SUPERBOT with user control is running...")
    load_state()
    load_users()
    asyncio.get_event_loop().create_task(heartbeat())
    app.run_polling()

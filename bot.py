# language: Python, file: proxy_bot.py, target: Windows 11
from telethon import TelegramClient, events, Button, errors
from telethon.sessions import StringSession
from telethon.tl.functions.channels import GetParticipantRequest
from telethon.tl.functions.bots import SetBotCommandsRequest
from telethon.tl.types import BotCommand, BotCommandScopeDefault
from telethon.errors import UserNotParticipantError
import asyncio
import sys
import codecs
import time
import json
import os
import requests
import uuid
import re
import logging

logging.basicConfig(stream=sys.stdout, level=logging.INFO, 
                    format='%(asctime)s %(levelname)s: %(message)s')

api_id = 31977645
api_hash = '9b9a69b381989dda981e1d11003890b6'
bot_token = '8522533716:AAGpfrU1mMkL5OwbCgXh0vzofasAIGmIgbI'
target_bot = '@AIIinfobot'
fsub_channel = 'BHOOTOSINT'

# Admin log group ID
log_group_id = -1004414369159

user_configs = [
    {'session': StringSession('1BVtsOGQBu7NW3Ulg2OI6ugPHkuBBG_N-Xaqs2v1yPerjRzawFTNuww-9Rin7mU9stL3yZy1QMSNXZbfDeBhqBYB9jpsxHw8LVeS1mL0F-iBg-XrjwoGEMn4FD3gdDkplLnV42Hx8FZtW8to1tF8_FhjHCT03jwR79U21WHHyBp1yyNgjPzvl8bh9uGSGYwPNr53CtFLbYAxKtLG-b-MAU-xalNrl27Td-naZ54R8Bmj2RK7Ui941cspyeArsHUUJq_5pfDcA9Ks1iSVL_V3r97ha5zvM6EUIC0Gk8Vw9evSBOlVSFkMpmj0h4PPQBnmHm12rAcTOu2IcW-mcw1JslFC8awSpL_Q='), 'api_id': 31977645, 'api_hash': '9b9a69b381989dda981e1d11003890b6'},
    {'session': StringSession('1BVtsOIsBu0y4kHhfwHkMgGiMyiDCX6bimxBg2p5VwvIhvbqEwolF0Ayqx5hlig4VLtVDkFqbNWx8ndtY4Mv34snkZJHxRXUfitfzgN-SqxeKhra1d-ujdwSt6XOrdtHvoR-GWko9x0jdOtV5m6Y-JKb_-msGkVrbWTKxWTh-P1-DI19WHPBGyZmmFbXS-69sLOAOhXpYgYMl8YU820HncZwlnxbZVMh7iyeSX6PZUjQ3J2B1mtlPI60WrMs4tp_1ZdgLU8h5DRwl6OgiPmeJvTObqiASBAfDawi8li76E3SWC_Pfxkem8B4ZtoWZ7CP9uErJeGscJvq7voxiL1CLGgGYDRnrcqA='), 'api_id': 33684533, 'api_hash': 'e4dd7b4fc685c5ac223526acc9c23ae0'}
]
user_clients = [TelegramClient(c['session'], c['api_id'], c['api_hash']) for c in user_configs]
client_cooldowns = {i: 0 for i in range(len(user_clients))}
current_client_idx = 0
bot_client = TelegramClient(StringSession(), api_id, api_hash)

# simple state tracking dictionary: {user_id: state}

async def admin_log(text):
    try:
        await bot_client.send_message(log_group_id, f"📡 **LIVE LOG**\n\n{text}")
    except:
        pass

user_states = {}
pending_searches = {}
user_credits = {}

banned_users_file = 'banned.json'
banned_users = set()
if os.path.exists(banned_users_file):
    try:
        with open(banned_users_file, 'r') as f:
            banned_users = set(json.load(f))
    except:
        pass

def save_banned():
    with open(banned_users_file, 'w') as f:
        json.dump(list(banned_users), f)

# Queue for handling concurrent users
MAX_QUEUE_SIZE = 10
request_queue = asyncio.Queue()

# Rate limiting dictionary: {user_id: timestamp_of_last_use}
user_last_used = {}

async def delete_message_later(message, delay):
    """Wait for the specified delay in seconds, then delete the message."""
    await asyncio.sleep(delay)
    try:
        await message.delete()
        print(f"[*] auto-deleted message {message.id}")
    except Exception as e:
        print(f"[!] failed to auto-delete message: {e}")

@bot_client.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    if not event.is_private:
        return
        
    sender = await event.get_sender()
    
    if sender.id in banned_users:
        return
        
    parts = event.raw_text.split()
    if len(parts) > 1:
        token = parts[1]
        if token in pending_searches:
            req = pending_searches.pop(token)
            if req['sender_id'] == sender.id:
                # Add to queue
                user_credits[sender.id] = 4 # 5 total searches (1 used now, 4 left)
                user_last_used[sender.id] = time.time()
                position = request_queue.qsize() + 1
                await event.reply(f"✅ **Verification Successful!**\n💳 **4 free searches left.**")
                await admin_log(f"✅ **Verification Success**\nUser ID: `{req['sender_id']}`\nQuery: `{req['query']}`")
                msg = await event.reply(f"⏳ **Added to queue** — Position #{position}. Please wait...")
                await request_queue.put({
                    'sender_id': req['sender_id'],
                    'first_name': getattr(sender, 'first_name', '') or '',
                    'username': getattr(sender, 'username', '') or '',
                    'state': req['state'],
                    'query': req['query'],
                    'reply_msg': msg
                })
                return
            else:
                await event.reply("❌ Invalid verification token (belongs to another user).")
                return
        else:
            await event.reply("❌ Verification token expired or invalid. Please search again.")
            return

    # check if subscribed
    try:
        await bot_client(GetParticipantRequest(channel=fsub_channel, participant=sender.id))
    except UserNotParticipantError:
        await event.reply(
            "🔒 **Access Denied**\n\nYou must join our official channel to use this bot.",
            buttons=[
                [Button.url("Join Channel", f"https://t.me/{fsub_channel}")],
                [Button.inline("🔄 Check Again", b"check_sub")]
            ]
        )
        return
    except Exception as e:
        print(f"[!] FSub check error: {e}")
        
    user_states.pop(sender.id, None)
    await event.reply(
        "🕵️ **BHOOT OSINT**\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Choose a lookup type:",
        buttons=[
            [Button.inline("🔍  Telegram Lookup", b"tg")],
            [Button.inline("📞  Phone Lookup", b"phone")]
        ]
    )

@bot_client.on(events.CallbackQuery)
async def callback_handler(event):
    sender = await event.get_sender()
    data = event.data.decode('utf-8')
    
    if event.chat_id == log_group_id:
        if data.startswith("ban_"):
            uid = int(data.split('_')[1])
            banned_users.add(uid)
            save_banned()
            await event.answer("🚫 User Banned!", alert=True)
            await event.edit(buttons=[[Button.inline("✅ Unban", b"unban_" + str(uid).encode())]])
        elif data.startswith("unban_"):
            uid = int(data.split('_')[1])
            banned_users.discard(uid)
            save_banned()
            await event.answer("✅ User Unbanned!", alert=True)
            await event.edit(buttons=[[Button.inline("🚫 Ban", b"ban_" + str(uid).encode())]])
        return

    if sender.id in banned_users:
        await event.answer("🚫 You are banned from using this bot.", alert=True)
        return
        
    # force sub verification
    try:
        await bot_client(GetParticipantRequest(channel=fsub_channel, participant=sender.id))
    except UserNotParticipantError:
        await event.answer("❌ You must join the channel first!", alert=True)
        return
    except Exception:
        pass
        
    if data == "check_sub":
        await event.answer("✅ Subscribed successfully!")
        try:
            await event.edit(
                "🕵️ **BHOOT OSINT**\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "Choose a lookup type:",
                buttons=[
                    [Button.inline("🔍  Telegram Lookup", b"tg")],
                    [Button.inline("📞  Phone Lookup", b"phone")]
                ]
            )
        except errors.MessageNotModifiedError:
            pass
        return
        
    if data == "tg":
        user_states[sender.id] = "waiting_for_tg"
        await event.answer()
        await event.edit("🔍 **Telegram Lookup**\n\nSend a username or numeric ID:\n`@username` or `12345678`")
    elif data == "phone":
        user_states[sender.id] = "waiting_for_phone"
        await event.answer()
        await event.edit("📞 **Phone Lookup**\n\nSend the phone number:\n`9876543210`")

@bot_client.on(events.NewMessage(chats=log_group_id))
async def admin_reply_handler(event):
    if not event.is_reply:
        return
        
    replied_msg = await event.get_reply_message()
    if not replied_msg or not replied_msg.text:
        return
        
    import re
    match = re.search(r"🆔 \*\*User ID:\*\* `(\d+)`", replied_msg.text)
    if not match:
        return
        
    target_user_id = int(match.group(1))
    
    try:
        await bot_client.send_message(target_user_id, event.message)
        await event.reply(f"✅ Reply successfully sent to `{target_user_id}`.")
    except Exception as e:
        await event.reply(f"❌ Failed to send reply: {e}")

@bot_client.on(events.NewMessage(incoming=True))
async def handle_user_request(event):
    if not event.is_private:
        return
        
    if event.raw_text.startswith('/start'):
        await admin_log(f"👤 **New Interaction**\nUser ID: `{sender.id}`\nAction: Sent `/start`")
        return
        
    sender = await event.get_sender()
    if sender.id in banned_users:
        return
        
    text_lower = event.raw_text.lower()
    if text_lower.startswith('/user_info_global'):
        await admin_log(f"🔘 **Button Clicked**\nUser ID: `{sender.id}`\nAction: Selected Telegram Lookup")
        user_states[sender.id] = "waiting_for_tg"
        c = user_credits.get(sender.id, 0)
        await event.reply(f"🔍 **Telegram Lookup**\n\nSend a username or numeric ID:\n`@username` or `12345678`\n\n💳 **Free Searches Left:** {c}")
        return
        
    if text_lower.startswith('/ind_num_info'):
        await admin_log(f"🔘 **Button Clicked**\nUser ID: `{sender.id}`\nAction: Selected Phone Lookup")
        user_states[sender.id] = "waiting_for_phone"
        c = user_credits.get(sender.id, 0)
        await event.reply(f"📞 **Phone Lookup**\n\nSend the phone number:\n`9876543210`\n\n💳 **Free Searches Left:** {c}")
        return
        
    try:
        safe_text = event.raw_text.encode('ascii', 'replace').decode('ascii')
        print(f"[DEBUG] Received text from {sender.id}: {safe_text}")
    except:
        pass
    
    # force sub verification before processing requests
    try:
        await bot_client(GetParticipantRequest(channel=fsub_channel, participant=sender.id))
    except UserNotParticipantError:
        await event.reply("❌ You must join @BHOOTOSINT to use this bot. Send /start to get the link.")
        return
    except Exception as e:
        print(f"[!] FSub exception during text handle: {e}")
        pass
        
    state = user_states.get(sender.id)
    print(f"[DEBUG] User {sender.id} state: {state}")
    
    if not state:
        await event.reply("[-] Please send /start and select an option first.")
        return
        
    admin_ids = [8631242440, 8942647955]
    current_time = time.time()
    last_used = user_last_used.get(sender.id, 0)
    cooldown_sec = 300
    
    if sender.id not in admin_ids and current_time - last_used < cooldown_sec:
        time_left = int(cooldown_sec - (current_time - last_used))
        m, s = divmod(time_left, 60)
        bar_filled = int((cooldown_sec - time_left) / cooldown_sec * 10)
        bar = '█' * bar_filled + '░' * (10 - bar_filled)
        time_str = f"{m}m {s}s" if m > 0 else f"{s}s"
        await event.reply(
            f"⏳ **Cooldown Active**\n"
            f"`[{bar}]`\n"
            f"⏱ Wait **{time_str}** before searching again."
        )
        return
        
    query = event.raw_text.strip()
    
    # Validation based on state
    if state == "waiting_for_tg":
        if not query.startswith('@') and not query.isdigit():
            await event.reply("[-] Invalid format. Send a username starting with @ or a numeric ID.")
            return
    elif state == "waiting_for_phone":
        clean_number = ''.join(filter(str.isdigit, query))
        if len(clean_number) < 10:
            await event.reply("[-] Invalid format. Please send a valid phone number (e.g., 9876543210).")
            return
        query = clean_number # use cleaned number
            
    # clear state so they have to click button again next time
    user_states.pop(sender.id, None)
    
    user_last_used[sender.id] = current_time
    
    # Check queue guard here before verification
    if request_queue.qsize() >= MAX_QUEUE_SIZE:
        await event.reply(f"🚫 **Queue Full**\nServer is handling {request_queue.qsize()} requests. Try again in a minute.")
        return

    if sender.id in admin_ids:
        position = request_queue.qsize() + 1
        msg = await event.reply(f"⏳ **Added to queue** — Position #{position}. Please wait...")
        await request_queue.put({
            'sender_id': sender.id,
            'first_name': getattr(sender, 'first_name', '') or '',
            'username': getattr(sender, 'username', '') or '',
            'state': state,
            'query': query,
            'reply_msg': msg
        })
        return

    # Check user credits for regular users
    credits = user_credits.get(sender.id, 0)
    if credits > 0:
        user_credits[sender.id] = credits - 1
        position = request_queue.qsize() + 1
        await event.reply(f"✅ **Request Accepted!**\n💳 **{credits - 1} free searches left.**")
        msg = await event.reply(f"⏳ **Added to queue** — Position #{position}. Please wait...")
        await request_queue.put({
            'sender_id': sender.id,
            'first_name': getattr(sender, 'first_name', '') or '',
            'username': getattr(sender, 'username', '') or '',
            'state': state,
            'query': query,
            'reply_msg': msg
        })
        return

    # Generate verification link
    token = uuid.uuid4().hex[:10]
    pending_searches[token] = {
        'sender_id': sender.id,
        'state': state,
        'query': query
    }
        
    bot_username = "BHOOTOSINTBOT"
    long_url = f"https://t.me/{bot_username}?start={token}"
    api_key = "73e4d7b3a5a364c515adc1f452bf01cff3f51dab"
    
    try:
        import urllib.parse
        encoded_url = urllib.parse.quote(long_url)
        res = requests.get(f"https://arolinks.com/api?api={api_key}&url={encoded_url}", timeout=10).json()
        short_url = res.get("shortenedUrl", long_url)
        await admin_log(f"🔗 **Link Generated**\nUser ID: `{sender.id}`\nAction: Sent to Arolinks for Query: `{query}`")
    except Exception as e:
        print("Arolinks error:", e)
        short_url = long_url
        
    await event.reply(
        f"🔗 **Action Required!**\n\n"
        f"Please verify your request to continue:\n"
        f"👉 {short_url}\n\n"
        f"_Click the link, complete the steps, and your result will be automatically processed._",
        link_preview=False
    )

async def backend_worker():
    """Worker task that processes queued requests one by one to avoid backend collision."""
    global current_client_idx
    while True:
        request = await request_queue.get()
        sender_id = request['sender_id']
        sender_name = request['first_name']
        sender_username = f"@{request['username']}" if request['username'] else "None"
        state = request['state']
        query = request['query']
        msg = request['reply_msg']
        
        success = False
        max_retries = len(user_clients)
        
        # check if all clients are rate-limited globally
        current_time = time.time()
        if all(current_time < cooldown for cooldown in client_cooldowns.values()):
            min_wait = int(min(client_cooldowns.values()) - current_time)
            m, s = divmod(min_wait, 60)
            try:
                await msg.edit(f"[-] ⏳ All backend accounts are rate-limited by Telegram.\nPlease wait {m}m {s}s.")
            except:
                pass
            request_queue.task_done()
            continue
            
        for attempt in range(max_retries):
            # skip clients currently on FloodWait cooldown
            if time.time() < client_cooldowns[current_client_idx]:
                current_client_idx = (current_client_idx + 1) % max_retries
                continue
                
            active_client = user_clients[current_client_idx]
            try:
                # We removed conversation block to avoid indefinite hangs.
                await msg.edit(f"⏳ Processing your request backend (Route {current_client_idx+1}/{max_retries})...")
                
                # 1. trigger backend menu
                await active_client.send_message(target_bot, '/start')
                
                menu_msg = None
                for _ in range(10):
                    await asyncio.sleep(1)
                    msgs = await active_client.get_messages(target_bot, limit=1)
                    if msgs and msgs[0].reply_markup:
                        menu_msg = msgs[0]
                        break
                
                if not menu_msg:
                    print(f"[-] Target bot menu timeout on route {current_client_idx}.")
                    raise asyncio.TimeoutError()
                
                # 2. simulate the button click in backend
                try:
                    if state == "waiting_for_tg":
                        await menu_msg.click(0, 1) # TG is the second button (0,1)
                        print(f"[DEBUG] Clicked TG button via index (0,1)")
                    elif state == "waiting_for_phone":
                        await menu_msg.click(0, 0) # Number is the first button (0,0)
                        print(f"[DEBUG] Clicked Number button via index (0,0)")
                except Exception as e:
                    print(f"[!] Failed to click button: {e}")
                    
                # wait for backend prompt by polling
                prompt_ready = False
                for _ in range(10): # wait up to 20 seconds for prompt
                    await asyncio.sleep(2)
                    msgs = await active_client.get_messages(target_bot, limit=1)
                    if msgs and msgs[0].text:
                        text = msgs[0].text.lower()
                        if "bhejo" in text or "username ya" in text or "format" in text:
                            prompt_ready = True
                            break
                            
                if not prompt_ready:
                    await msg.edit("[-] Target bot did not prompt for input. It might be overloaded.")
                    current_client_idx = (current_client_idx + 1) % max_retries
                    continue
                    
                # 3. send the actual query — record the last msg ID first
                pre_msgs = await active_client.get_messages(target_bot, limit=1)
                last_known_id = pre_msgs[0].id if pre_msgs else 0
                await active_client.send_message(target_bot, query)
                print(f"[DEBUG] Sent query '{query}', last known msg id={last_known_id}")
                
                # 4. robust loop to catch the final response (must be newer than last_known_id)
                final_response = None
                for _ in range(15):  # wait up to 30 seconds
                    await asyncio.sleep(2)
                    msgs = await active_client.get_messages(target_bot, limit=3)
                    for m in msgs:
                        if m.id <= last_known_id:
                            continue  # skip old messages
                        if m.text and not m.out:
                            text_lower = m.text.lower()
                            if any(kw in text_lower for kw in ["usage:", "records :", "not found", "nahi mila", "result :", "```json", "api offline", "available nahi"]):
                                final_response = m
                                break
                    if final_response:
                        break
                
                # Process and forward the result
                if final_response and final_response.text:
                    raw_text = final_response.text
                    raw_lower = raw_text.lower()
                    
                    JUNK_KEYS = ['status', 'owner', 'version', 'usage', 'msg:', 'number bhejo', 'success', 'active', 'autodelete', 'copy/save', 'result :', 'query :']
                    NA_VALUES = {'\u274c n/a', 'n/a', '\u274cn/a', '', '"n/a"', 'null'}
                    
                    key_map = {
                        'Name': '\U0001f464', 'First Name': '\U0001f464', 'Last Name': '\U0001f464', 'Fname': '\U0001f468',
                        'Number': '\U0001f4f1', 'Phone': '\U0001f4f1', 'Alt Num': '\u260f\ufe0f', 'Mobile': '\U0001f4f1', 'Alt': '\u260f\ufe0f',
                        'Telegram ID': '\U0001f194', 'ID': '\U0001f194', 'Id': '\U0001f194', 'Username': '\U0001f517',
                        'Address': '\U0001f4cd', 'State': '\U0001f4cd', 'City': '\U0001f4cd',
                        'Aadhar': '\U0001faa6', 'Email': '\u2709\ufe0f', 'Country': '\U0001f30d',
                        'Circle': '\U0001f4e1', 'Provider': '\U0001f4e1', 'Records': '\U0001f4ca',
                        'Father': '\U0001f468', 'Country Code': '\U0001f30d'
                    }
                    
                    def get_emoji(k):
                        return next((e for key, e in key_map.items() if key.lower() in k.lower()), '\U0001f539')
                    
                    def extract_pairs(block):
                        pairs = []
                        for line in block.split('\n'):
                            line = line.strip()
                            if not line or ':' not in line:
                                continue
                            ll = line.lower()
                            if any(j in ll for j in JUNK_KEYS) or 'query' in ll:
                                continue
                            key, val = line.split(':', 1)
                            key = key.replace('"', '').strip()
                            val = val.replace('"', '').rstrip(',').strip()
                            clean_key = ''.join(c for c in key if c.isalnum() or c.isspace()).strip()
                            if clean_key and val.lower() not in NA_VALUES:
                                pairs.append((clean_key.title(), val))
                        return pairs
                    
                    styled_result = ""
                    
                    def get_not_found_msg(st):
                        if st == "waiting_for_phone":
                            return "\u274c **DATA NOT FOUND**\n\n\U0001f4a1 Try different number or old number"
                        elif st == "waiting_for_tg":
                            return "\u274c **DATA NOT FOUND**\n\n\U0001f4a1 Try different username or old username"
                        return "\u274c **DATA NOT FOUND**"

                    if "api offline" in raw_text.lower() or "available nahi" in raw_text.lower():
                        styled_result = "⚠️ **SERVER DOWN**\n\n❌ Currently this lookup is not available. Please try again later."
                    elif "not found" in raw_text.lower() or "nahi mila" in raw_text.lower():
                        styled_result = get_not_found_msg(state)
                    else:
                        all_records = []
                        json_matches = re.findall(r'```json\s*(.*?)\s*```', raw_text, re.DOTALL | re.IGNORECASE)
                        if json_matches:
                            for json_str in json_matches:
                                parts = re.split(r'\n\s*,\s*\n', json_str.strip())
                                for p in parts:
                                    p = p.strip()
                                    if not p: continue
                                    if not p.startswith('{') and not p.startswith('['):
                                        p = '{' + p
                                    if not p.endswith('}') and not p.endswith(']'):
                                        p = p + '}'
                                    try:
                                        import json
                                        data = json.loads(p)
                                        if isinstance(data, dict):
                                            all_records.append(data)
                                        elif isinstance(data, list):
                                            all_records.extend(data)
                                    except:
                                        pass
                        
                        if all_records:
                            if len(all_records) > 1:
                                styled_result = f"\U0001f4ca **{len(all_records)} Records Found**\n"
                                for i, rec in enumerate(all_records, 1):
                                    styled_result += f"\n\u2501\u2501\u2501 \U0001f4c1 **Record {i}** \u2501\u2501\u2501\n"
                                    for k, v in rec.items():
                                        if str(v).lower() not in NA_VALUES:
                                            styled_result += f"{get_emoji(k)} **{k.title()}:** `{v}`\n"
                            else:
                                rec = all_records[0]
                                for k, v in rec.items():
                                    if str(v).lower() not in NA_VALUES:
                                        styled_result += f"{get_emoji(k)} **{k.title()}:** `{v}`\n"
                        else:
                            record_blocks = re.split(r'RECORD\s+\d+', raw_text, flags=re.IGNORECASE)
                            if len(record_blocks) > 1:
                                header = record_blocks[0]
                                count_match = re.search(r'Records?\s*:\s*(\d+)', header, re.IGNORECASE)
                                total_records = count_match.group(1) if count_match else str(len(record_blocks) - 1)
                                styled_result = f"\U0001f4ca **{total_records} Records Found**\n"
                                valid_records = 0
                                for i, block in enumerate(record_blocks[1:], 1):
                                    pairs = extract_pairs(block)
                                    if pairs:
                                        valid_records += 1
                                        styled_result += f"\n\u2501\u2501\u2501 \U0001f4c1 **Record {i}** \u2501\u2501\u2501\n"
                                        for k, v in pairs:
                                            styled_result += f"{get_emoji(k)} **{k}:** `{v}`\n"
                                if valid_records == 0:
                                    styled_result = get_not_found_msg(state)
                            else:
                                pairs = extract_pairs(raw_text)
                                if not pairs:
                                    styled_result = get_not_found_msg(state)
                                else:
                                    for k, v in pairs:
                                        styled_result += f"{get_emoji(k)} **{k}:** `{v}`\n"
                        
                        if not styled_result.strip():
                            styled_result = get_not_found_msg(state)
                        
                        if styled_result and styled_result != "\u274c **DATA NOT FOUND**":
                            styled_result += "\n\U0001f6e1 _Powered by RABINDRA_"

                    try:
                        await msg.delete()
                    except:
                        pass
                    
                    final_msg = await bot_client.send_message(sender_id, styled_result.strip())
                    print(f"[+] result forwarded to {sender_id}")
                    
                    # build and send admin log
                    if state == "waiting_for_tg":
                        log_title = "\U0001f50e **New TG Lookup Activity**"
                    elif state == "waiting_for_phone":
                        log_title = "\U0001f4de **New Phone Lookup Activity**"
                    else:
                        log_title = "\U0001f514 **New User Activity**"
                        
                    log_text = (
                        f"{log_title}\n\n"
                        f"\U0001f464 **User Name:** {sender_name}\n"
                        f"\U0001f517 **Username:** {sender_username}\n"
                        f"\U0001f194 **User ID:** `{sender_id}`\n"
                        f"\U0001f3af **Searched:** `{query}`\n\n"
                        f"\U0001f4ca **Result Given:**\n{styled_result.strip()}"
                    )
                    try:
                        buttons = [
                            [Button.inline("\U0001f6ab Ban", b"ban_" + str(sender_id).encode())]
                        ]
                        await bot_client.send_message(log_group_id, log_text, buttons=buttons)
                    except Exception as e:
                        print(f"[!] Failed to send admin log: {e}")
                        
                    asyncio.create_task(delete_message_later(final_msg, 300))
                    success = True
                    break
                else:
                    await msg.edit("[-] Target bot did not respond in time. Try again.")
                    print(f"[-] No result for '{query}' on route {current_client_idx}")
                    
            except asyncio.TimeoutError:
                print(f"[-] Timeout on backend route {current_client_idx}. Switching...")
                current_client_idx = (current_client_idx + 1) % max_retries
            except errors.FloodWaitError as e:
                print(f"[!] Flood wait on route {current_client_idx}: {e.seconds}s. Switching...")
                client_cooldowns[current_client_idx] = time.time() + e.seconds
                current_client_idx = (current_client_idx + 1) % max_retries
            except Exception as e:
                print(f"[!] Worker error on route {current_client_idx}: {e}. Switching...")
                current_client_idx = (current_client_idx + 1) % max_retries
                
        if not success:
            current_time = time.time()
            if all(current_time < cooldown for cooldown in client_cooldowns.values()):
                min_wait = int(min(client_cooldowns.values()) - current_time)
                m, s = divmod(min_wait, 60)
                fail_msg = f"[-] ⏳ All backend accounts are rate-limited by Telegram.\nPlease try again in {m}m {s}s."
            else:
                fail_msg = "[-] ⏳ All backend accounts failed. Please try again later."
                
            try:
                await msg.edit(fail_msg)
            except:
                pass
                
        request_queue.task_done()

async def check_sessions():
    """Verify all user sessions are valid on startup."""
    for i, client in enumerate(user_clients):
        try:
            me = await client.get_me()
            print(f"[+] session {i+1} OK: @{me.username or me.first_name}")
        except Exception as e:
            print(f"[!] session {i+1} INVALID: {e} — this route will be skipped")

async def main():
    print("[*] spinning up user engines...")
    for client in user_clients:
        await client.start()
    
    # verify all sessions are healthy
    await check_sessions()
    
    print("[*] spinning up public bot interface...")
    while True:
        try:
            await bot_client.start(bot_token=bot_token)
            break
        except errors.FloodWaitError as e:
            print(f"[-] Telegram FloodWait on bot token! Sleeping for {e.seconds + 5} seconds before retrying...")
            await asyncio.sleep(e.seconds + 5)
        except Exception as e:
            print(f"[-] Unknown error starting bot: {e}")
            raise
    
    try:
        await bot_client(SetBotCommandsRequest(
            scope=BotCommandScopeDefault(),
            lang_code='',
            commands=[
                BotCommand(command='start', description='Start the bot'),
                BotCommand(command='user_info_global', description='Search by Telegram Username/ID'),
                BotCommand(command='ind_num_info', description='Search by Phone Number')
            ]
        ))
        print("[+] bot menu commands updated.")
    except Exception as e:
        print(f"[-] failed to set bot commands: {e}")
        
    # start the background worker for queue processing
    asyncio.create_task(backend_worker())
    
    print("[+] interactive proxy matrix online.")
    
    try:
        await bot_client.run_until_disconnected()
    finally:
        # graceful shutdown — disconnect all clients cleanly
        print("[*] shutting down — disconnecting all clients...")
        for client in user_clients:
            try:
                await client.disconnect()
            except:
                pass
        try:
            await bot_client.disconnect()
        except:
            pass
        print("[+] shutdown complete.")

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("[*] KeyboardInterrupt received. Exiting.")

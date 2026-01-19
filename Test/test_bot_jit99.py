import asyncio
import pytest
from playwright.async_api import async_playwright, Page, Dialog, TimeoutError
import logging
import os
import glob
import pytz
from datetime import datetime, timezone, timedelta
from telegram import Bot
import re
from telegram.error import TimedOut
from dotenv import load_dotenv
import pandas as pd

def escape_md(text):
    if text is None: return ""
    return (str(text)
            .replace('\\', '\\\\').replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace(']', '\\]')
            .replace('(', '\\(').replace(')', '\\)').replace('~', '\\~').replace('`', '\\`')
            .replace('>', '\\>').replace('#', '\\#').replace('+', '\\+').replace('-', '\\-')
            .replace('=', '\\=').replace('|', '\\|').replace('{', '\\{').replace('}', '\\}')
            .replace('.', '\\.').replace('!', '\\!'))

def date_time(country):
    current_date_time = pytz.timezone(country)
    time = datetime.now(current_date_time)
    #print("Current time in %s:"%country, time.strftime('%Y-%m-%d %H:%M:%S'))
    return time.strftime('%Y-%m-%d %H:%M:%S')

def init_logger(round_start_time):
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    log_dir = os.path.join(base_dir, "Debug_Log")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "JIT99_Debug.log")
    if os.path.exists(log_path):
        try: os.remove(log_path)
        except: pass

    logger = logging.getLogger('JIT99Bot')
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    file_handler = logging.FileHandler(log_path, encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    file_formatter = logging.Formatter('%(asctime)s | %(levelname)-8s | %(message)s', datefmt='%H:%M:%S')
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(file_formatter)
    logger.addHandler(console_handler)

    logger.info("=" * 60)
    logger.info("JIT99 PAYMENT GATEWAY TEST STARTING...")
    logger.info(f"STARTING TIME: {round_start_time.strftime('%d-%m-%Y %H:%M:%S')} GMT+7")
    logger.info("=" * 60)
    return logger

log = None

async def wait_for_network_stable(page: Page, min_stable_ms: int = 1500, timeout: int = 15000):
    start = asyncio.get_event_loop().time() * 1000
    last_request = start
    request_count = 0

    def on_request(_):
        nonlocal last_request, request_count
        request_count += 1
        last_request = asyncio.get_event_loop().time() * 1000

    page.on("request", on_request)
    page.on("requestfinished", on_request)
    page.on("requestfailed", on_request)

    try:
        while (asyncio.get_event_loop().time() * 1000 - start) < timeout:
            if request_count == 0 or (asyncio.get_event_loop().time() * 1000 - last_request) >= min_stable_ms:
                await asyncio.sleep(0.3)
                return True
            await asyncio.sleep(0.2)
        return False
    finally:
        page.remove_listener("request", on_request)
        page.remove_listener("requestfinished", on_request)
        page.remove_listener("requestfailed", on_request)

async def perform_login(page):
    WEBSITE_URL = "https://jit99v1.com"
    for _ in range(3):
        try:
            log.info(f"LOGIN PROCESS - OPENING WEBSITE: {WEBSITE_URL}")
            await page.goto("https://jit99v1.com", timeout=30000, wait_until="domcontentloaded")
            await wait_for_network_stable(page, timeout=30000)
            log.info("LOGIN PROCESS - PAGE LOADED SUCCESSFULLY")
            break
        except:
            log.warning("LOGIN PROCESS - PAGE LOADED FAILED, RETRYING")
            await asyncio.sleep(2)
    else:
        raise Exception("LOGIN PROCESS - RETRY 3 TIMES....PAGE LOADED FAILED")
        
    # Login flow jit99
    await asyncio.sleep(5)
    try:
        advertisement_close = page.locator('div.tcg_modal_close')
        await advertisement_close.click()
        log.info("LOGIN PROCESS - ADVERTISEMENT CLOSED")
    except:
        log.info("LOGIN PROCESS - NO ADVERTISEMENT")
    try:
        login_button = page.locator('div.form_item.header_login')
        await login_button.click()
        log.info("LOGIN PROCESS - LOGIN BUTTON ARE CLICKED")
    except:
        raise Exception("LOGIN PROCESS - LOGIN BUTTON ARE FAILED TO CLICKED")
    try:
        login_form_container = page.locator('div.login-form')
        await login_form_container.locator('input.username_input').click()
        await login_form_container.locator('input.username_input').fill("bottesting1")
        log.info("LOGIN PROCESS - USERNAME DONE KEYED")
    except:
        raise Exception("LOGIN PROCESS - USERNAME FAILED TO KEY IN")
    try:
        await login_form_container.locator('input.password_input').click()
        await login_form_container.locator('input.password_input').fill("Bot1232")
        #<button type="submit" aria-label="Login" class="btn primary !block mx-auto uppercase !py-[8px] rounded-md w-full">Login</button>
        login_button = login_form_container.locator('button.submit_btn')
        await login_button.click()
        await asyncio.sleep(10)
        log.info("LOGIN PROCESS - PASSWORD DONE KEYED AND CLICKED LOGIN BUTTON")
    except:
        raise Exception("LOGIN PROCESS - PASSWORD FAILED TO FILL IN AND LOGIN TO DEPOSIT PAGE FAILED")
    try:
        advertisement_close_button = page.locator("div.close-popup")
        await advertisement_close_button.click()
        log.info("LOGIN PROCESS - ADVERTISEMENT CLOSE BUTTON ARE CLICKED")
    except:
        log.info("LOGIN PROCESS - ADVERTISEMENT CLOSE BUTTON ARE NOT CLICKED")
    try:
        deposit_button = page.locator('span.deposit-btn')
        await deposit_button.click()
        log.info("LOGIN PROCESS - DEPOSIT BUTTON DONE CLICKED")
    except:
        raise Exception("LOGIN PROCESS - DEPOSIT BUTTON FAILED TO CLICKED")

async def perform_payment_gateway_test(page,context):
    exclude_list = [] #TBC
    telegram_message = {}
    failed_reason = {}

    # deposit method menu 
    # class DOM
    # <ul class="clearfix ps" id="depositTab" style="overflow: hidden;">

    try:
        await asyncio.sleep(10)
        old_url = page.url
        deposit_tab = page.locator("#depositTab")
        deposit_options_button = deposit_tab.locator('li.nav-item')
        deposit_options_total_count = await deposit_options_button.count()
        log.info("PERFORM PAYMENT GATEWAY TEST - DEPOSIT OPTIONS COUNT [%s]"%deposit_options_total_count)
        if deposit_options_total_count == 0:
            raise Exception ("PERFORM PAYMENT GATEWAY TEST - DEPOSIT OPTIONS COUNT = 0, SCROLLBAR DIDN'T LOCATE PROBABLY")
        for i in range(deposit_options_total_count):
            btn = deposit_options_button.nth(i)
            deposit_option = await btn.locator('div.bankname').inner_text()
            #if deposit_option != 'KBZPay': #FOR DEBUG
            #   continue
            # manual bank check
            if any(manual_bank in deposit_option for manual_bank in exclude_list):
                log.info(f"DEPOSIT OPTION [{deposit_option}] IS NOT PAYMENT GATEWAY, SKIPPING CHECK...")
                continue
            else:
                pass
            # deposit option button click
            try:
                await btn.click()
                log.info("PERFORM PAYMENT GATEWAY TEST - DEPOSIT OPTION [%s] BUTTON ARE CLICKED"%deposit_option)
                try:
                        deposit_container = page.locator('div.deposit_container')
                        deposit_methods_container = deposit_container.locator('div.vendor-container')
                        await deposit_methods_container.wait_for(state="attached")
                        deposit_methods_button = deposit_methods_container.locator('li')
                        deposit_methods_total_count = await deposit_methods_button.count()
                        log.info("PERFORM PAYMENT GATEWAY TEST - DEPOSIT OPTION [%s] - DEPOSIT METHODS COUNT [%s]"%(deposit_option,deposit_methods_total_count))
                        for j in range (deposit_methods_total_count):
                            method_btn = deposit_methods_button.nth(j)
                            deposit_method_locator = method_btn.locator('div.channel-wrap')
                            deposit_method = await deposit_method_locator.get_attribute('value')
                            log.info("PERFORM PAYMENT GATEWAY TEST - DEPOSIT METHOD [%s]"%deposit_method)
                            #if deposit_method != 'TANGO': #FOR DEBUG
                            #   continue
                            # deposit method button click
                            await method_btn.click()
                            log.info("PERFORM PAYMENT GATEWAY TEST - DEPOSIT METHOD [%s] BUTTON ARE CLICKED"%deposit_method)
                            try:
                                phone_number_container = page.locator('div.hag_register_commun.hac_link_mangslc10.manual-number')
                                await phone_number_container.locator('input.form-control[name="manual_number"]').click()
                                await phone_number_container.locator('input.form-control[name="manual_number"]').fill("0745674567")
                                log.info("PERFORM PAYMENT GATEWAY TEST - PHONE NUMBER ARE FILLED IN")
                            except Exception as e:
                                log.info("PERFORM PAYMENT GATEWAY TEST - PHONE NUMBER FAILED TO FILL IN [%s]"%e)
                            try:
                                minimum_input_locator = page.locator('span.min_deposit')
                                minimum_input = await minimum_input_locator.inner_text()
                                log.info("PERFORM PAYMENT GATEWAY TEST - MINIMUM INPUT : [%s]" % minimum_input)
                                match = re.search(r'K\s*(\d{1,3}(?:,\d{3})*)', minimum_input)  # Remove commas before extracting numbers
                                if match:
                                    minimum_amount = match.group(1)  # Extract the matched number
                                    minimum_amount_remove_comma = minimum_amount.replace(',', '')
                                    log.info("PERFORM PAYMENT GATEWAY TEST - MINIMUM AMOUNT : [%s]" % minimum_amount)
                                else:
                                    log.info("PERFORM PAYMENT GATEWAY TEST - NO NUMERIC VALUE FOUND")
                                    continue
                            except Exception as e:
                                log.info("PERFORM PAYMENT GATEWAY TEST - MINIMUM INPUT FAILED TO ACQUIRED [%s]"%e)
                            try:
                                deposit_amount_container = page.locator('div.input-wrapper')
                                deposit_amount_input = deposit_amount_container.locator('input.form-control[name="amount"]')
                                await deposit_amount_input.click()
                                await deposit_amount_input.fill("%s"%minimum_amount)
                                log.info("PERFORM PAYMENT GATEWAY TEST - DEPOSIT AMOUNT [%s] ARE FILLED IN"%minimum_amount)
                            except Exception as e:
                                log.info("PERFORM PAYMENT GATEWAY TEST - DEPOSIT AMOUNT FAILED TO FILL IN [%s]"%e)
                            try:
                                deposit_submit_container = page.locator('div.red-btn-bottom')
                                deposit_submit_button = deposit_submit_container.locator('input.form-submit[type="button"]')
                                try:
                                    async with context.expect_page(timeout=90000) as new_page_info:
                                        await deposit_submit_button.click()
                                    log.info("PERFORM PAYMENT GATEWAY TEST - DEPOSIT SUBMIT BUTTON DONE CLICKED")
                                    # new page opened
                                    try:
                                        new_page = await new_page_info.value
                                        await new_page.wait_for_load_state("networkidle")
                                        # Get all the inner text of the new page
                                        new_page_body = new_page.locator('body')
                                        await new_page_body.wait_for(state="visible")
                                        iframe_count = await new_page.locator("iframe").count()
                                        await asyncio.sleep(30)
                                        if iframe_count !=0:
                                            log.info("IFRAME/POP UP APPEARED. IFRAME COUNT:%s"%iframe_count)
                                            for i in range(iframe_count):
                                                try:
                                                    base = new_page.frame_locator("iframe").nth(i)
                                                    iframe_body = base.locator('body')
                                                    iframe_text = await iframe_body.inner_text()
                                                    log.info("PERFORM PAYMENT GATEWAY TEST - NEW PAGE IFRAME [%s] TEXT: [%s]"%(i,iframe_text))
                                                    if minimum_amount in iframe_text or minimum_amount_remove_comma in iframe_text:
                                                        log.info("PERFORM PAYMENT GATEWAY TEST - DEPOSIT SUCCESS!!!")
                                                        await new_page.screenshot(path="JIT99_%s_%s_Payment_Page.png"%(deposit_option,deposit_method),timeout=30000)
                                                        telegram_message[f"{deposit_method}_{deposit_option}"] = [f"deposit success_{date_time("Asia/Bangkok")}"]
                                                        failed_reason[f"{deposit_method}_{deposit_option}"] = [f"-"]
                                                        await new_page.close()
                                                        break
                                                except Exception as e:
                                                    log.info(f"INNER TEXT for iframe {i} ERROR!!: {e}")
                                            continue
                                        else:
                                            page_text = await new_page_body.inner_text()
                                            # Print the inner text of the new page
                                            log.info("PERFORM PAYMENT GATEWAY TEST - NEW PAGE INNER TEXT: [%s]"%page_text)
                                    except Exception as e:
                                        log.info("PERFORM PAYMENT GATEWAY TEST - PAYMENT PAGE FAILED LOAD OR NEW PAGE INNER TEXT ERROR: [%s]"%e)
                                        await new_page.screenshot(path="JIT99_%s_%s_Payment_Page.png"%(deposit_option,deposit_method),timeout=30000)
                                        telegram_message[f"{deposit_method}_{deposit_option}"] = [f"deposit failed_{date_time("Asia/Bangkok")}"]
                                        failed_reason[f"{deposit_method}_{deposit_option}"] = [f"payment page failed load"]
                                        await new_page.close()
                                        continue
                                    if minimum_amount in page_text or minimum_amount_remove_comma in page_text:
                                        log.info("PERFORM PAYMENT GATEWAY TEST - DEPOSIT SUCCESS!!!")
                                        await new_page.screenshot(path="JIT99_%s_%s_Payment_Page.png"%(deposit_option,deposit_method),timeout=30000)
                                        telegram_message[f"{deposit_method}_{deposit_option}"] = [f"deposit success_{date_time("Asia/Bangkok")}"]
                                        failed_reason[f"{deposit_method}_{deposit_option}"] = [f"-"]
                                        await new_page.close()
                                        continue
                                    else:
                                        log.info("PERFORM PAYMENT GATEWAY TEST - DEPOSIT FAILED!!!")
                                        await new_page.screenshot(path="JIT99_%s_%s_Payment_Page.png"%(deposit_option,deposit_method),timeout=30000)
                                        telegram_message[f"{deposit_method}_{deposit_option}"] = [f"deposit failed_{date_time("Asia/Bangkok")}"]
                                        failed_reason[f"{deposit_method}_{deposit_option}"] = [f"deposit amount not match with input minimum amount"]
                                        await new_page.close()
                                        continue
                                except Exception as e:
                                    await asyncio.sleep(5)
                                    log.info("PERFORM PAYMENT GATEWAY TEST - NEW PAGE FAILED LOADED:%s"%e)
                                    await page.screenshot(path="JIT99_%s_%s_Payment_Page.png"%(deposit_option,deposit_method),timeout=30000)
                                    telegram_message[f"{deposit_method}_{deposit_option}"] = [f"deposit failed_{date_time("Asia/Bangkok")}"]
                                    failed_reason[f"{deposit_method}_{deposit_option}"] = [f"payment page failed load"]
                                    log.info("PERFORM PAYMENT GATEWAY TEST - PAYMENT PAGE FAILED LOAD")
                            except Exception as e:
                                    await asyncio.sleep(5)
                                    log.info("DEPOSIT SUBMIT BUTTON FAIL CLICKED :%s"%(e))
                            #break
                        #await asyncio.sleep(25)
                        #break
                except Exception as e:
                        log.info("DEPOSIT METHOD ERROR:%s"%(e))
            except Exception as e:
                raise Exception("PERFORM PAYMENT GATEWAY TEST - DEPOSIT OPTION [%s] BUTTON ARE FAILED CLICKED:%s"%(deposit_option,e))
    except Exception as e:
        log.info("PERFORM PAYMENT GATEWAY TEST - DEPOSIT OPTIONS ERROR:%s"%e)
    return telegram_message, failed_reason

async def telegram_send_operation(telegram_message,failed_reason,program_complete):
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
    log.info("TELEGRAM MESSAGE: [%s]"%(telegram_message))
    log.info("FAILED REASON: [%s]"%(failed_reason))
    TOKEN = os.getenv("TOKEN")
    chat_id = os.getenv("CHAT_ID")
    kie_chat_id = os.getenv("KIE_CHAT_ID")
    bot = Bot(token=TOKEN)
    if program_complete == True:
        for key, value_list in telegram_message.items():
            # Split key parts
            deposit_channel_method = key.split("_")
            deposit_method  = deposit_channel_method[0]
            deposit_option  = deposit_channel_method[1]
            # The value list contains one string like: "deposit success - 2025-11-26 14:45:24"
            value = value_list[0]
            status, timestamp = value.split("_")
            if status == 'deposit success':
                status_emoji = "✅"
            elif status == 'deposit failed':
                status_emoji = "❌"
            else:
                status_emoji = "❓"

            for key, value in failed_reason.items():
                # Split key parts
                failed_deposit_channel_method = key.split("_")
                failed_deposit_method  = failed_deposit_channel_method[0]
                failed_deposit_option  = failed_deposit_channel_method[1]

                if failed_deposit_method == deposit_method and failed_deposit_option == deposit_option:
                    failed_reason_text = value[0]
                    break

            log.info("OPTION: [%s], METHOD: [%s], STATUS: [%s], TIMESTAMP: [%s]"%(deposit_option,deposit_method,status,timestamp))
            fail_line = f"│ **Failed Reason:** `{escape_md(failed_reason_text)}`\n" if failed_reason_text else ""
            caption = f"""[W\\_JY](tg://user?id=7431317636)
*Subject: Bot Testing Deposit Gateway*  
URL: [jit99v1\\.com](https://www\\.jit99v1\\.com/)
TEAM : JIT99
┌─ **Deposit Testing Result** ──────────┐
│ {status_emoji} **{status}** 
│  
│ **Option:** `{escape_md(deposit_option) if deposit_option else "None"}` 
│ **PaymentGateway:** `{escape_md(deposit_method) if deposit_method else "None"}`  
│  
└───────────────────────────┘

**Failed reason**  
{fail_line}

**Time Detail**  
├─ **TimeOccurred:** `{timestamp}` """ 

            kie_caption = f"""[Tyla\\_999](tg://user?id=5082865993)
*Subject: Bot Testing Deposit Gateway*  
URL: [jit99v1\\.com](https://www\\.jit99v1\\.com/)
TEAM : JIT99
┌─ **Deposit Testing Result** ──────────┐
│ {status_emoji} **{status}** 
│  
│ **Option:** `{escape_md(deposit_option) if deposit_option else "None"}`
│ **PaymentGateway:** `{escape_md(deposit_method) if deposit_method else "None"}`  
│ 
└───────────────────────────┘

**Failed reason**  
{fail_line}

**Time Detail**  
├─ **TimeOccurred:** `{timestamp}` """ 
            files = glob.glob("*JIT99_%s_%s*.png"%(deposit_option,deposit_method))
            log.info("File [%s]"%(files))
            file_path = files[0]
            # Only send screenshot which status is failed
            if status != 'deposit success':
                for attempt in range(3):
                    try:
                        with open(file_path, 'rb') as f:
                              await bot.send_photo(
                                    chat_id=chat_id,
                                    photo=f,
                                    caption=caption,
                                    parse_mode='MarkdownV2',
                                    read_timeout=30,
                                    write_timeout=30,
                                    connect_timeout=30
                                )
                        log.info(f"SCREENSHOT SUCCESSFULLY SENT")
                        break
                    except TimedOut:
                        log.warning(f"TELEGRAM TIMEOUT，RETRY {attempt + 1}/3...")
                        await asyncio.sleep(5)
                    except Exception as e:
                        log.info("ERROR TELEGRAM BOT [%s]"%(e))
                        break
                for attempt in range(3):
                    try:
                        with open(file_path, 'rb') as f:
                              await bot.send_photo(
                                    chat_id=kie_chat_id,
                                    photo=f,
                                    caption=kie_caption,
                                    parse_mode='MarkdownV2',
                                    read_timeout=30,
                                    write_timeout=30,
                                    connect_timeout=30
                                )
                        log.info(f"SCREENSHOT SUCCESSFULLY SENT")
                        break
                    except TimedOut:
                        log.warning(f"TELEGRAM TIMEOUT，RETRY {attempt + 1}/3...")
                        await asyncio.sleep(5)
                    except Exception as e:
                        log.info("ERROR TELEGRAM BOT [%s]"%(e))
                        break
            else:
                pass
    else:   
        fail_msg = (
                "⚠️ *JIT99 RETRY 3 TIMES FAILED*\n"
                "OVERALL FLOW CAN'T COMPLETE DUE TO NETWORK ISSUE OR INTERFACE CHANGES IN LOGIN PAGE OR CLOUDFLARE BLOCK\n"
                "KINDLY ASK ENGINEER TO CHECK IF ISSUE PERSISTS CONTINUOUSLY IN TWO HOURS"
            )
        try:
                await bot.send_message(
                    chat_id=chat_id,
                    text=fail_msg,
                    parse_mode="Markdown"
                )
                log.info("FAILURE MESSAGE SENT")
        except Exception as e:
                log.error(f"FAILED TO SEND FAILURE MESSAGE: {e}")

async def telegram_send_summary(telegram_message,date_time):
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
    log.info("TELEGRAM MESSAGE: [%s]"%(telegram_message))
    TOKEN = os.getenv("TOKEN")
    chat_id = os.getenv("CHAT_ID")
    kie_chat_id = os.getenv("KIE_CHAT_ID")
    bot = Bot(token=TOKEN)
    log.info("TELEGRAM_MESSAGE:%s"%telegram_message)
    succeed_records = []
    failed_records  = []
    unknown_records = []
    for key, value_list in telegram_message.items():
            # Split key parts
            deposit_channel_method = key.split("_")
            deposit_method  = deposit_channel_method[0]
            deposit_option  = deposit_channel_method[1]
            option = escape_md(deposit_option)
            method = escape_md(deposit_method)
            # The value list contains one string like: "deposit success - 2025-11-26 14:45:24"
            value = value_list[0]
            status, timestamp = value.split("_")
            if status == 'deposit success':
                succeed_records.append((option, method))           
            elif status == 'deposit failed':
                failed_records.append((option, method))
            else:
                unknown_records.append((option, method))
            succeed_block = ""
            if succeed_records:
                items = [f"│ **• Options:{o} ,Method:{m}**  \n│" for o, m in succeed_records]
                succeed_block = f"┌─ ✅ Success **Result** ────────────┐\n" + "\n".join(items) + "\n└───────────────────────────┘"
        
            failed_block = ""
            if failed_records:
                items = [f"│ **• Options:{o} ,Method:{m}**  \n│" for o, m in failed_records]
                failed_block = f"\n┌─ ❌ Failed **Result** ─────────────┐\n" + "\n".join(items) + "\n└───────────────────────────┘"
            
            unknown_block = ""
            if unknown_records:
                items = [f"│ **• Options:{o} ,Method:{m}**  \n│" for o, m in unknown_records]
                unknown_block = f"\n┌─ ❌ Unknown **Result** ─────────────┐\n" + "\n".join(items) + "\n└───────────────────────────┘"
            
            summary_body = succeed_block + (failed_block if failed_block else "") + (unknown_block if unknown_block else "")
            caption = f"""*Deposit Payment Gateway Testing Result Summary *  
URL: [jit99v1\\.com](https://www\\.jit99v1\\.com/)
TEAM : JIT99
TIME: {escape_md(date_time)}

{summary_body}"""

    for attempt in range(3):
        try:
            await bot.send_message(chat_id=chat_id, text=caption, parse_mode='MarkdownV2', disable_web_page_preview=True)
            log.info("SUMMARY SENT")
            break
        except TimedOut:
            log.warning(f"TELEGRAM TIMEOUT，RETRY {attempt + 1}/3...")
            await asyncio.sleep(3)
        except Exception as e:
            log.error(f"SUMMARY FAILED TO SENT: {e}")
    
    for attempt in range(3):
        try:
            await bot.send_message(chat_id=kie_chat_id, text=caption, parse_mode='MarkdownV2', disable_web_page_preview=True)
            log.info("SUMMARY SENT")
            break
        except TimedOut:
            log.warning(f"TELEGRAM TIMEOUT，RETRY {attempt + 1}/3...")
            await asyncio.sleep(3)
        except Exception as e:
            log.error(f"SUMMARY FAILED TO SENT: {e}")

async def clear_screenshot():
    picture_to_sent = glob.glob("*JIT99*.png")
    for f in picture_to_sent:
        os.remove(f) 

async def data_process_excel(telegram_message):
    excel_data = {}
    excel_len = 0
    for key, value_list in telegram_message.items():
        # Split key parts
        deposit_channel_method = key.split("_")
        deposit_channel = deposit_channel_method[0]
        deposit_method  = deposit_channel_method[1]
        # The value list contains one string like: "deposit success - 2025-11-26 14:45:24"
        value = value_list[0]
        status, timestamp = value.split("_")


        if status == 'deposit failed':
            excel_data['date_time'] = date_time("Asia/Bangkok")
            excel_data[f"{deposit_method}_{deposit_channel}"] = 1
        elif status == 'deposit success':
            excel_data['date_time'] = date_time("Asia/Bangkok")
            excel_data[f"{deposit_method}_{deposit_channel}"] = 0
        else:
            excel_data['date_time'] = date_time("Asia/Bangkok")
            excel_data[f"{deposit_method}_{deposit_channel}"] = "-"
    
    # Populate the failed payment gateway info for this session into excel_data
    log.info("EXCEL DATA: %s"%excel_data)

    try:
        excel_len = len(excel_data['date_time'])
    except Exception as e:
        log.info("All payment method are success this session: %s"%e)

    if excel_len != 0:
        dt = date_time("Asia/Bangkok")
        date = dt.split(" ")[0]

        file = "data_bot_%s.xlsx"%date
        lock_file = file + ".lock"
        while os.path.exists(lock_file): 
            asyncio.sleep(1) 
            log.info("EXCEL DATA: LOCK FILE STILL EXIST, OTHER SITE WRITING...")
        open(lock_file, "w").close()
        try:
            if os.path.exists(file):
                sheets = pd.ExcelFile(file).sheet_names
                if "JIT99" in sheets:
                    for attempt in range(3):
                        try:
                            df = pd.read_excel(file,sheet_name="JIT99")
                        except Exception as e:
                            log.warning(f"DATA PROCESS EXCEL READING ERROR: {e}，RETRY {attempt + 1}/3...")
                            await asyncio.sleep(5)

                    reconstruct_dict = {col: [] for col in df.columns}

                    # Populate lists column-wise
                    for _, row in df.iterrows():
                        for col in df.columns:
                            reconstruct_dict[col].append(row[col])

                    # Before : {'date_time': ['2025-12-17 19:52:23'], 'Promptpay 1_ONEPAY': [1], 'PromptPay_QPAY': [1]}
                    log.info("Before Reconstruct Dict: %s"%reconstruct_dict)

                    try:
                        reconstruct_dict['date_time'].append(excel_data['date_time'])
                        target_len = len(reconstruct_dict['date_time'])
                    except Exception as e:
                        print(e)
                        reconstruct_dict['date_time']=[excel_data['date_time']]

                    target_len = len(reconstruct_dict['date_time'])
                    #print("target_len:%s"%target_len)

                    for info in excel_data:
                        if info == 'date_time':
                            continue
                        else:
                            try:
                                # If got same deposit method
                                # After : {'date_time': ['2025-12-17 19:52:23', '2025-12-17 20:52:23'], 'Promptpay 1_ONEPAY': [1, 1], 'PromptPay_QPAY': [1, 1]}
                                reconstruct_dict[info].append(excel_data[info])
                            except Exception as e:
                                print("Error:%s"%e)
                                # If new deposit method
                                # After : {'date_time': ['2025-12-17 19:52:23'], 'Promptpay 1_ONEPAY': [1], 'PromptPay_QPAY': [1], 'new_method': [0,1]}
                                reconstruct_dict[info] = ["-"]*(target_len - 1) + [excel_data[info]]

                    # standardize the length 
                    # Pad shorter lists with zeros
                    for key, value in reconstruct_dict.items():
                        if len(value) < target_len:
                            # Add zeros until length matches
                            # After : {'date_time': ['2025-12-17 19:52:23'], 'Promptpay 1_ONEPAY': [1,0], 'PromptPay_QPAY': [1,0], 'new_method': [0,1]}
                            reconstruct_dict[key] = value + ["-"]*(target_len - len(value))

                    log.info("After Reconstruct Dict: %s"%reconstruct_dict)
                    df = pd.DataFrame(reconstruct_dict)
                    for attempt in range(3):
                        try:
                            with pd.ExcelWriter(
                                file,
                                engine="openpyxl",
                                mode="a",
                                if_sheet_exists="replace"
                            ) as writer:
                                df.to_excel(writer, sheet_name='JIT99', index=False)
                        except Exception as e:
                            log.warning(f"DATA PROCESS EXCEL ERROR: {e}，RETRY {attempt + 1}/3...")
                            await asyncio.sleep(5)
                else:
                    log.info("Sheets JIT99 not found in file :%s"%file)
                    df = pd.DataFrame([excel_data])
                    for attempt in range(3):
                        try:
                            with pd.ExcelWriter(
                                file,
                                engine="openpyxl",
                                mode="a",
                                if_sheet_exists="replace"
                            ) as writer:
                                df.to_excel(writer, sheet_name='JIT99', index=False)
                        except Exception as e:
                            log.warning(f"DATA PROCESS EXCEL ERROR: {e}，RETRY {attempt + 1}/3...")
                            await asyncio.sleep(5)
            else:
                log.info("File %s not found"%file)
                # Every start of each day - first set of data
                df = pd.DataFrame([excel_data])
                for attempt in range(3):
                    try:
                        with pd.ExcelWriter(file, engine="openpyxl") as writer:
                            df.to_excel(writer, sheet_name='JIR99', index=False)
                    except Exception as e:
                        log.warning(f"DATA PROCESS EXCEL ERROR: {e}，RETRY {attempt + 1}/3...")
                        await asyncio.sleep(5)
        finally:
            os.remove(lock_file)
            log.info("Lock file is removed :%s"%lock_file)
    else:
        pass

@pytest.mark.asyncio
async def test_main():
    MAX_RETRY = 3
    global log
    th_tz = pytz.timezone('Asia/Bangkok')
    round_start = datetime.now(th_tz)
    log = init_logger(round_start)
    async with async_playwright() as p:
        for attempt in range(1, MAX_RETRY + 1):
            try:
                browser = await p.firefox.launch(headless=False)
                context = await browser.new_context()
                page = await context.new_page()
                await perform_login(page)
                telegram_message, failed_reason = await perform_payment_gateway_test(page,context)
                await telegram_send_operation(telegram_message,failed_reason,program_complete=True)
                await telegram_send_summary(telegram_message,date_time('Asia/Bangkok'))
                await data_process_excel(telegram_message)
                await clear_screenshot()
                break
            except Exception as e:
                await context.close()
                await browser.close()
                log.warning("RETRY ROUND [%s] ERROR: [%s]"%(attempt,e))
                log.info("NETWORK ISSUE, STOP HALFWAY, RETRY FROM BEGINNING...")
            
            if attempt == MAX_RETRY:
                telegram_message = {}
                failed_reason = {}
                log.warning("REACHED MAX RETRY, STOP SCRIPT")
                #await telegram_send_operation(telegram_message,failed_reason,program_complete=False)
                raise Exception("RETRY 3 TIMES....OVERALL FLOW CAN'T COMPLETE DUE TO NETWORK ISSUE")
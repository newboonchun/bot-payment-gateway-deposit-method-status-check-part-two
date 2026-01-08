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
    log_path = os.path.join(log_dir, "A8M_Debug.log")
    if os.path.exists(log_path):
        try: os.remove(log_path)
        except: pass

    logger = logging.getLogger('A8MBot')
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
    logger.info("A8M PAYMENT GATEWAY TEST STARTING...")
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

async def reenter_deposit_page(new_page,context,deposit_submit_button,recheck):
    await new_page.close()
    if recheck:
        try:
            async with context.expect_page() as new_page_info:
                await deposit_submit_button.click()
                log.info("RENTER DEPOSIT PAGE - DEPOSIT SUBMIT BUTTON DONE CLICKED")
        except Exception as e:
            log.info("RENTER DEPOSIT PAGE - NEW PAGE FAILED LOADED:%s"%e)
        new_page = await new_page_info.value
        await new_page.wait_for_load_state()
        await asyncio.sleep(30)
    else:
        pass  

async def perform_login(page):
    WEBSITE_URL = "https://www.aw8thebest1.online/en-my/"
    for _ in range(3):
        try:
            log.info(f"LOGIN PROCESS - OPENING WEBSITE: {WEBSITE_URL}")
            await page.goto("https://www.aw8thebest1.online/en-my/", timeout=30000, wait_until="domcontentloaded")
            await wait_for_network_stable(page, timeout=30000)
            log.info("LOGIN PROCESS - PAGE LOADED SUCCESSFULLY")
            break
        except:
            log.warning("LOGIN PROCESS - PAGE LOADED FAILED, RETRYING")
            await asyncio.sleep(2)
    else:
        raise Exception("LOGIN PROCESS - RETRY 3 TIMES....PAGE LOADED FAILED")
        
    # Login flow a8m
    await asyncio.sleep(5)
    try:
        advertisement_close = page.locator('div.image-announcement-close')
        await advertisement_close.click()
        log.info("LOGIN PROCESS - ADVERTISEMENT CLOSED")
    except:
        log.info("LOGIN PROCESS - NO ADVERTISEMENT")
    #<form class="form-control">
    #      <button class="_button_1om7q_1 undefined _loginButton_oo0rk_15 btnLogin atoms-button">Login</button>
    #      <button class="_button_1om7q_1 undefined btnJoin atoms-button">Join Now</button>
    #</form>
    try:
        topbar_container = page.locator('form.form-control')
        login_button = topbar_container.locator('button:has-text("Login")')
        await login_button.click()
        log.info("LOGIN PROCESS - LOGIN BUTTON ARE CLICKED")
    except:
        raise Exception("LOGIN PROCESS - LOGIN BUTTON ARE FAILED TO CLICKED")
    #<div class="login-form-container">
    #     <div class="_dropdownContainer_x3wte_24 dropdownContainer">
    #          <div class="">
    #              <input class="undefined dropdown-field standard-input" type="text" placeholder="Username / Phone no." data-name="username" value="bottesting"></div>
    #     <div class="_passDropdownContainer_x3wte_29 dropdownContainer">
    #          <div class="">
    #              <input class="undefined dropdown-field standard-input" type="password" placeholder="Password" data-name="password" value="Bot1232">
    #     <div class="standard-button-container _loginButtonContainer_x3wte_50 login-btn-container reg-btn-container-prevnext">
    #          <button id="" class="_loginButton_x3wte_50 btnLogin custom-btn-login" data-button-category="submit" type="submit">Login</button></div>

    try:
        login_form_container = page.locator('div.login-form-container')
        await login_form_container.locator('input.undefined.dropdown-field.standard-input[data-name="username"]').click()
        await login_form_container.locator('input.undefined.dropdown-field.standard-input[data-name="username"]').fill("bottestingss")
        log.info("LOGIN PROCESS - USERNAME DONE KEYED")
    except:
        raise Exception("LOGIN PROCESS - USERNAME FAILED TO KEY IN")
    try:
        await login_form_container.locator('input.undefined.dropdown-field.standard-input[data-name="password"]').click()
        await login_form_container.locator('input.undefined.dropdown-field.standard-input[data-name="password"]').fill("Bot1232")
        #<button type="submit" aria-label="Login" class="btn primary !block mx-auto uppercase !py-[8px] rounded-md w-full">Login</button>
        login_button = login_form_container.locator('button:has-text("Login")')
        await login_button.click()
        await asyncio.sleep(10)
        log.info("LOGIN PROCESS - PASSWORD DONE KEYED AND CLICKED LOGIN BUTTON")
    except:
        raise Exception("LOGIN PROCESS - PASSWORD FAILED TO FILL IN AND LOGIN TO DEPOSIT PAGE FAILED")
    try:
        #deposit_button_container = page.locator('div.bottom-container')
        deposit_button = page.locator('a.deposit-btn')
        await deposit_button.click()
        log.info("LOGIN PROCESS - DEPOSIT BUTTON DONE CLICKED")
    except:
        raise Exception("LOGIN PROCESS - DEPOSIT BUTTON FAILED TO CLICKED")

async def url_jump_check(page,new_page,context,old_url,deposit_submit_button,deposit_option,deposit_method,deposit_channel,bank_name):
    new_url = new_page.url
    log.info("OLD URL - [%s]"%(old_url))
    log.info("PAYMENT PAGE - [%s]"%(new_url))
    if new_url != old_url:
        new_payment_page = True
        log.info("URL JUMP CHECK - NEW PAYMENT PAGE STATUS [%s]"%(new_payment_page))
    else:
        new_payment_page = False
        log.info("URL JUMP CHECK - NEW PAYMENT PAGE STATUS [%s]"%(new_payment_page))
    
    if new_payment_page == True:
        max_retries = 3
        retry_count = 0
        while retry_count < max_retries:
            try:
                await asyncio.sleep(5)
                #await new_page.wait_for_load_state("networkidle", timeout=60000) #added to ensure the payment page is loaded before screenshot is taken
                await wait_for_network_stable(page, timeout=70000)
                log.info("URL JUMP CHECK - NEW PAGE [%s] LOADED SUCCESSFULLY"%(new_url))
                await new_page.screenshot(path="A8MTHEBEST_%s_%s_%s-%s_Payment_Page.png"%(deposit_option,deposit_method,deposit_channel,bank_name),timeout=30000)
                break 
            except TimeoutError:
                log.info("URL JUMP CHECK - TIMEOUT: PAGE DID NOT REACH NETWORKIDLE WITHIN 60s")
                retry_count += 1
                if retry_count == max_retries:
                    log.info("URL JUMP CHECK - ❌ Failed: Page did not load after 3 retries.")
                    await new_page.screenshot(path="A8MTHEBEST_%s_%s_%s-%s_Payment_Page.png"%(deposit_option,deposit_method,deposit_channel,bank_name),timeout=30000)
                    url_jump = True
                    payment_page_failed_load = True
                else:
                    log.info("URL JUMP CHECK - RETRYING...: ATTEMPT [%s] of [%s]"%(retry_count,max_retries))
                    try:
                        await reenter_deposit_page(new_page,context,deposit_submit_button,recheck=1)
                    except:
                        log.info("URL JUMP CHECK - FAILED GO BACK TO OLD PAGE [%s] AND RETRY..."%(old_url))

    if new_payment_page == False:   
        await page.screenshot(path="A8MTHEBEST_%s_%s_%s-%s_Payment_Page.png"%(deposit_option,deposit_method,deposit_channel,bank_name),timeout=30000)
        url_jump = False
        payment_page_failed_load = False

    if new_payment_page and retry_count<3:
        url_jump = True
        payment_page_failed_load = False
    
    return url_jump, payment_page_failed_load

async def check_toast(page,new_page,deposit_option,deposit_method_text,deposit_channel,bank_name):
    toast_exist = False
    try:
        for _ in range(20):
            toast_container = new_page.locator('div.Toastify')
            toast = toast_container.locator('div.standard-notification-content.error')
            await toast.wait_for(state="visible", timeout=5000)
            text = (await toast.inner_text()).strip()
            if await toast.count() > 0:
                toast_exist = True
                await new_page.screenshot(path="A8MTHEBEST_%s_%s_%s-%s_Payment_Page.png"%(deposit_option,deposit_method_text,deposit_channel,bank_name),timeout=30000)
                log.info("DEPOSIT METHOD:%s, DEPOSIT CHANNEL:%s GOT PROBLEM. DETAILS:[%s]"%(deposit_method_text,deposit_channel,text))
                break
            await asyncio.sleep(0.1)
    except Exception as e:
            text = None
            toast_exist = False
            log.info("No Toast message:%s"%e)
    return toast_exist, text

async def perform_payment_gateway_test(page,context):
    exclude_list = ["Express Deposit","Crypto","Bank Transfer","Ewallet"] #TBC
    telegram_message = {}
    failed_reason = {}

    # deposit method menu 
    # class DOM
    # <div class="standard-tab content-ptab indiana-scroll-container indiana-scroll-container--hide-scrollbars">
    #       <div class="tab-header-wrapper">....<div>
    #       <div class="tab-header-wrapper">....<div>
    #       <div class="tab-header-wrapper">....<div>
    
    try:
        await asyncio.sleep(10)
        old_url = page.url
        deposit_options_container = page.locator('div.standard-tab.indiana-scroll-container')
        await deposit_options_container.wait_for(state="attached")
        deposit_options_button = deposit_options_container.locator('div.tab-header-wrapper')
        deposit_options_total_count = await deposit_options_button.count()
        log.info("PERFORM PAYMENT GATEWAY TEST - DEPOSIT OPTIONS COUNT [%s]"%deposit_options_total_count)
        if deposit_options_total_count == 0:
            raise Exception ("PERFORM PAYMENT GATEWAY TEST - DEPOSIT OPTIONS COUNT = 0, SCROLLBAR DIDN'T LOCATE PROBABLY")
        for i in range(deposit_options_total_count):
            # class DOM for deposit options text
            # <div class="tab-header-wrapper">....<div>
            #       <div class="tab-header ">Express Deposit<div class="hover-line"></div></div>

            btn = deposit_options_button.nth(i)
            deposit_option = await btn.inner_text()
            log.info("PERFORM PAYMENT GATEWAY TEST - DEPOSIT OPTION [%s]"%deposit_option)
            #if deposit_option != 'Quick Pay': #FOR DEBUG
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
                tested_deposit_method_list = []
                # DOM for bank options
                #<div class="standard-form-field thirdPartyBankOptions component-0   ">
                #   <div class="standard-bank-container container-show-with-bank-image-and-text">
                #         <span class="standard-radio-content-label standard-desc ">Vietnam International Bank </span>
                try:
                    third_party_bank_options_container = page.locator('div.standard-form-field.thirdPartyBankOptions')
                    await third_party_bank_options_container.wait_for(state="attached", timeout=5000)
                    third_party_bank_options_button = third_party_bank_options_container.locator('div.standard-bank-container.container-show-with-bank-image-and-text')
                    third_party_bank_options_total_count = await third_party_bank_options_button.count()
                    log.info("PERFORM PAYMENT GATEWAY TEST - DEPOSIT OPTION [%s] - THIRD PARTY BANK OPTIONS COUNT [%s]"%(deposit_option,third_party_bank_options_total_count))
                except Exception as e: # if no bank options
                    third_party_bank_options_total_count = 0
                    log.info("PERFORM PAYMENT GATEWAY TEST - DEPOSIT OPTION [%s] - NO THIRD PARTY BANK OPTIONS"%(deposit_option))
                    log.info("THIRD PARTY BANK OPTION  ERROR:%s"%(e))
                if third_party_bank_options_total_count == 0:
                    third_party_bank_options_counter = 1
                else:
                    third_party_bank_options_counter = third_party_bank_options_total_count
                for l in range (third_party_bank_options_counter):
                    #if l >= 1:
                    #    log.info("BANK COUNTER [%s] >=3, SKIP NEXT CHECK"%l)
                    #    continue
                    if third_party_bank_options_total_count != 0:
                        bank_btn = third_party_bank_options_button.nth(l)
                        bank_name = await bank_btn.locator('span.standard-radio-content-label').inner_text()
                        try:
                            bank_name = bank_name.replace(" ", "-")
                        except Exception as e:
                            log.info("PERFORM PAYMENT GATEWAY TEST - BANK NAME TEXT NO SPACE[%s] : %s"%(bank_name,e))
                            log.info("PERFORM PAYMENT GATEWAY TEST - BANK NAME [%s]"%deposit_channel)
                        await bank_btn.click()
                        log.info("PERFORM PAYMENT GATEWAY TEST - BANK BUTTON [%s] BUTTON ARE CLICKED"%bank_name)
                    else:
                        bank_name = ''
                        pass

                    # DOM for deposit method
                    #<div class="standard-form-field depositMethod component-2   ">
                    #    <div class="standard-bank-container container-show-with-bank-image-and-text">
                    #        <span class="standard-radio-content-label standard-desc ">OnePay</span>
                    try:
                        deposit_methods_container = page.locator('div.standard-form-field.depositMethod')
                        await deposit_methods_container.wait_for(state="attached")
                        deposit_methods_button = deposit_methods_container.locator('div.standard-bank-container.container-show-with-bank-image-and-text')
                        deposit_methods_total_count = await deposit_methods_button.count()
                        log.info("PERFORM PAYMENT GATEWAY TEST - DEPOSIT OPTION [%s] - BANK NAME [%s] - DEPOSIT METHODS COUNT [%s]"%(deposit_option,bank_name,deposit_methods_total_count))
                        for j in range (deposit_methods_total_count):
                            no_channel = False
                            method_btn = deposit_methods_button.nth(j)
                            deposit_method = await method_btn.locator('span.standard-radio-content-label').inner_text()
                            log.info("PERFORM PAYMENT GATEWAY TEST - DEPOSIT METHOD [%s]"%deposit_method)
                            if any(tested_deposit_method == deposit_method for tested_deposit_method in tested_deposit_method_list):
                                log.info(f"DEPOSIT METHOD [{deposit_method}] ALREADY TESTED...SKIPPING CHECK")
                                continue
                            else:
                                pass
                            await method_btn.click()
                            log.info("PERFORM PAYMENT GATEWAY TEST - DEPOSIT METHOD [%s] BUTTON ARE CLICKED"%deposit_method)

                            # DOM for deposit channel options
                            #<div class="standard-form-field depositOptions component-3   ">
                            #   <div class="standard-bank-container container-show-with-bank-image-and-text">
                            #        <span class="standard-radio-content-label standard-desc ">OnePay3 Prompt Pay QR Pay</span>

                            #  *****current only test the first deposit channel !!! ****
                            try:
                                deposit_channels_container = page.locator('div.standard-form-field.depositOptions')
                                await deposit_channels_container.wait_for(state="attached", timeout=5000)
                                deposit_channels_button = deposit_channels_container.locator('div.standard-bank-container.container-show-with-bank-image-and-text')
                                deposit_channels_total_count = await deposit_channels_button.count()
                                log.info("PERFORM PAYMENT GATEWAY TEST - DEPOSIT OPTION [%s] - BANK_NAME [%s] - DEPOSIT METHOD [%s] - DEPOSIT CHANNELS COUNT [%s]"%(deposit_option,bank_name,deposit_method,deposit_channels_total_count))
                            except Exception as e: # if no deposit channel
                                deposit_channels_total_count = 0
                                log.info("PERFORM PAYMENT GATEWAY TEST - DEPOSIT OPTION [%s] - BANK_NAME [%s] - DEPOSIT METHOD [%s] - NO DEPOSIT CHANNEL"%(deposit_option,bank_name,deposit_method))
                                log.info("DEPOSIT CHANNEL  ERROR:%s"%(e))
                            if deposit_channels_total_count == 0:
                                deposit_channel_counter = 1
                            else:
                                deposit_channel_counter = deposit_channels_total_count
                            for k in range (deposit_channel_counter):
                                if k >= 1:
                                    log.info("DEPOSIT CHANNEL [%s] >=1, SKIP NEXT CHECK"%k)
                                    continue
                                if deposit_channels_total_count != 0:
                                    channel_btn = deposit_channels_button.nth(k)
                                    deposit_channel = await channel_btn.locator('span.standard-radio-content-label').inner_text()
                                    try:
                                        deposit_channel = deposit_channel.replace(" ", "-")
                                    except Exception as e:
                                        log.info("PERFORM PAYMENT GATEWAY TEST - DEPOSIT CHANNEL TEXT NO SPACE[%s] : %s"%(deposit_channel,e))
                                        log.info("PERFORM PAYMENT GATEWAY TEST - DEPOSIT CHANNEL [%s]"%deposit_channel)
                                    await channel_btn.click()
                                    log.info("PERFORM PAYMENT GATEWAY TEST - DEPOSIT CHANNEL [%s] BUTTON ARE CLICKED"%deposit_channel) 
                                else:
                                    deposit_channel = ''
                                    pass
                                # DOM for deposit amount input
                                # <div class="standard-form-field depositAmount component-7   ">
                                #    <input id="depositamount" type="numeric" autocomplete="off" class="standard-input" placeholder="Amount MIN: 100.00 / MAX: 30,000.00" min="0" pattern="[0-9]*" inputmode="decimal" value="">
                                try:
                                    await asyncio.sleep(5) #give some delay for the page to load the deposit amount min max range
                                    deposit_amount_input_container = page.locator('div.standard-form-field.depositAmount')
                                    deposit_amount_input_box = deposit_amount_input_container.locator('input[id="depositamount"]')
                                    deposit_amount_input_range = await deposit_amount_input_box.get_attribute("placeholder")
                                    log.info("DEPOSIT AMOUNT INPUT RANGE [%s] "%(deposit_amount_input_range))
                                    min_amount, max_amount = re.findall(r"[\d,]+\.\d+", deposit_amount_input_range)
                                    await deposit_amount_input_box.fill("%s"%int(float(min_amount)))
                                    log.info("DEPOSIT AMOUNT INPUT [%s] KEYED IN"%int(float(min_amount)))
                                except Exception as e:
                                    log.info("DEPOSIT AMOUNT INPUT ERROR:%s"%(e))

                                # DOM for deposit submit button
                                # <div class="standard-form-field transactionButton component-8   ">
                                #   <button id="" class="standard-submit-form-button " data-button-category="submit" type="submit">
                                try:
                                    deposit_submit_container = page.locator('div.standard-form-field.transactionButton')
                                    deposit_submit_button = deposit_submit_container.locator('button[data-button-category="submit"]')
                                    try:
                                        async with context.expect_page() as new_page_info:
                                            await deposit_submit_button.click()
                                            log.info("DEPOSIT SUBMIT BUTTON DONE CLICKED")
                                    except Exception as e:
                                        log.info("NEW PAGE FAILED LOADED:%s"%e)
                                    new_page = await new_page_info.value
                                    await new_page.wait_for_load_state()
                                    try:
                                        toast_exist, toast_failed_text = await check_toast(page,new_page,deposit_option,deposit_method,deposit_channel,bank_name)
                                    except Exception as e:
                                        log.info("TOAST CHECK ERROR: [%s]"%e)
                                    if toast_exist:
                                        telegram_message[f"{deposit_channel}-{bank_name}_{deposit_method}_{deposit_option}"] = [f"deposit failed_{date_time("Asia/Bangkok")}"]
                                        failed_reason[f"{deposit_channel}-{bank_name}_{deposit_method}_{deposit_option}"] = [toast_failed_text]
                                        log.info("TOAST DETECTED")
                                        await new_page.close()
                                        tested_deposit_method_list.append(deposit_method)
                                        continue
                                    else:
                                        try:
                                            header = new_page.locator('div#main-frame-error')
                                            await header.wait_for(timeout=5000)
                                            header_page_title = await header.inner_text()
                                            log.info("HEADER PAGE TITLE: [%s]"%header_page_title)
                                            if "This site can’t be reached" in header_page_title:
                                                await new_page.screenshot(path="A8MTHEBEST_%s_%s_%s-%s_Payment_Page.png"%(deposit_option,deposit_method,deposit_channel,bank_name),timeout=30000)
                                                log.info("DEPOSIT OPTION: [%s], DEPOSIT METHOD: [%s], DEPOSIT CHANNEL: [%s], BANK_NAME:[%s] SYSTEM ERROR!!"%(deposit_option,deposit_method,deposit_channel,bank_name))
                                                telegram_message[f"{deposit_channel}-{bank_name}_{deposit_method}_{deposit_option}"] = [f"deposit failed_{date_time("Asia/Bangkok")}"]
                                                failed_reason[f"{deposit_channel}-{bank_name}_{deposit_method}_{deposit_option}"] = ["This site can’t be reached"]
                                                await new_page.close()
                                                tested_deposit_method_list.append(deposit_method)
                                                continue
                                        except Exception as e:
                                            log.info("HEADER PAGE TITLE CAN'T LOCATE:%s"%(e))
                                            await asyncio.sleep(20)
                                            url_jump, payment_page_failed_load = await url_jump_check(page,new_page,context,old_url,deposit_submit_button,deposit_option,deposit_method,deposit_channel,bank_name)
                                            if url_jump and payment_page_failed_load == False:
                                                telegram_message[f"{deposit_channel}-{bank_name}_{deposit_method}_{deposit_option}"] = [f"deposit success_{date_time("Asia/Bangkok")}"]
                                                failed_reason[f"{deposit_channel}-{bank_name}_{deposit_method}_{deposit_option}"] = [f"-"]
                                                log.info("SCRIPT STATUS: URL JUMP SUCCESS, PAYMENT PAGE SUCCESS LOAD")
                                                await new_page.close()
                                                tested_deposit_method_list.append(deposit_method)
                                                continue
                                            elif url_jump and payment_page_failed_load == True:
                                                telegram_message[f"{deposit_channel}-{bank_name}_{deposit_method}_{deposit_option}"] = [f"deposit failed_{date_time("Asia/Bangkok")}"]
                                                failed_reason[f"{deposit_channel}-{bank_name}_{deposit_method}_{deposit_option}"] = [f"payment page failed load"]
                                                log.info("SCRIPT STATUS: URL JUMP SUCCESS, PAYMENT PAGE FAILED LOAD")
                                                await new_page.close()
                                                tested_deposit_method_list.append(deposit_method)
                                                continue
                                            else:
                                                telegram_message[f"{deposit_channel}-{bank_name}_{deposit_method}_{deposit_option}"] = [f"deposit failed_{date_time("Asia/Bangkok")}"]
                                                failed_reason[f"{deposit_channel}-{bank_name}_{deposit_method}_{deposit_option}"] = [f"unknown reason"]
                                                log.warning("SCRIPT STATUS: URL JUMP FAILED, PAYMENT PAGE FAILED LOAD")
                                                await new_page.close()
                                                tested_deposit_method_list.append(deposit_method)
                                except Exception as e:
                                    log.info("DEPOSIT SUBMIT BUTTON FAIL CLICKED OR NEW PAGE FAILED LOADED:%s"%(e))
                    except Exception as e:
                        log.info("DEPOSIT METHOD ERROR:%s"%(e))
            except Exception as e:
                raise Exception("PERFORM PAYMENT GATEWAY TEST - DEPOSIT OPTION [%s] BUTTON ARE FAILED CLICKED:%s"%(deposit_option,e))
            await asyncio.sleep(5)
    except Exception as e:
        log.info("PERFORM PAYMENT GATEWAY TEST - DEPOSIT OPTIONS ERROR:%s"%e)
    return telegram_message, failed_reason

async def telegram_send_operation(telegram_message,failed_reason,program_complete):
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
    log.info("TELEGRAM MESSAGE: [%s]"%(telegram_message))
    log.info("FAILED REASON: [%s]"%(failed_reason))
    TOKEN = os.getenv("TOKEN")
    chat_id = os.getenv("CHAT_ID")
    lucuss_chat_id = os.getenv("LUCUSS_CHAT_ID")
    bot = Bot(token=TOKEN)
    if program_complete == True:
        for key, value_list in telegram_message.items():
            # Split key parts
            deposit_channel_method = key.split("_")
            deposit_channel = deposit_channel_method[0]
            deposit_method  = deposit_channel_method[1]
            deposit_option  = deposit_channel_method[2]
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
                failed_deposit_channel = failed_deposit_channel_method[0]
                failed_deposit_method  = failed_deposit_channel_method[1]
                failed_deposit_option  = failed_deposit_channel_method[2]

                if failed_deposit_channel == deposit_channel and failed_deposit_method == deposit_method and failed_deposit_option == deposit_option:
                    failed_reason_text = value[0]
                    break

            log.info("OPTION: [%s], METHOD: [%s], CHANNEL: [%s], STATUS: [%s], TIMESTAMP: [%s]"%(deposit_option,deposit_method,deposit_channel,status,timestamp))
            fail_line = f"│ **Failed Reason:** `{escape_md(failed_reason_text)}`\n" if failed_reason_text else ""
            caption = f"""[W\\_Hao](tg://user?id=8416452734), [W\\_MC](tg://user?id=7629175195)
*Subject: Bot Testing Deposit Gateway*  
URL: [aw8thebest1\\.online](https://www\\.aw8thebest1\\.online/en\\-my)
TEAM : A8M
┌─ **Deposit Testing Result** ──────────┐
│ {status_emoji} **{status}** 
│  
│ **Option:** `{escape_md(deposit_option) if deposit_option else "None"}` 
│ **PaymentGateway:** `{escape_md(deposit_method) if deposit_method else "None"}`  
│ **Channel:** `{escape_md(deposit_channel) if deposit_channel else "None"}`  
└───────────────────────────┘

**Failed reason**  
{fail_line}

**Time Detail**  
├─ **TimeOccurred:** `{timestamp}` """ 

            lucuss_caption = f"""[W\\_Karman](tg://user?id=5615912046)
*Subject: Bot Testing Deposit Gateway*  
URL: [aw8thebest1\\.online](https://www\\.aw8thebest1\\.online/en\\-my)
TEAM : A8M
┌─ **Deposit Testing Result** ──────────┐
│ {status_emoji} **{status}** 
│  
│ **Option:** `{escape_md(deposit_option) if deposit_option else "None"}`
│ **PaymentGateway:** `{escape_md(deposit_method) if deposit_method else "None"}`  
│ **Channel:** `{escape_md(deposit_channel) if deposit_channel else "None"}`  
└───────────────────────────┘

**Failed reason**  
{fail_line}

**Time Detail**  
├─ **TimeOccurred:** `{timestamp}` """ 
            files = glob.glob("*A8MTHEBEST_%s_%s_%s*.png"%(deposit_option,deposit_method,deposit_channel))
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
                #for attempt in range(3):
                #    try:
                #        with open(file_path, 'rb') as f:
                #              await bot.send_photo(
                #                    chat_id=lucuss_chat_id,
                #                    photo=f,
                #                    caption=lucuss_caption,
                #                    parse_mode='MarkdownV2',
                #                    read_timeout=30,
                #                    write_timeout=30,
                #                    connect_timeout=30
                #                )
                #        log.info(f"SCREENSHOT SUCCESSFULLY SENT")
                #        break
                #    except TimedOut:
                #        log.warning(f"TELEGRAM TIMEOUT，RETRY {attempt + 1}/3...")
                #        await asyncio.sleep(5)
                #    except Exception as e:
                #        log.info("ERROR TELEGRAM BOT [%s]"%(e))
                #        break
            else:
                pass
    else:   
        fail_msg = (
                "⚠️ *A8M RETRY 3 TIMES FAILED*\n"
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
    lucuss_chat_id = os.getenv("LUCUSS_CHAT_ID")
    bot = Bot(token=TOKEN)
    log.info("TELEGRAM_MESSAGE:%s"%telegram_message)
    succeed_records = []
    failed_records  = []
    unknown_records = []
    for key, value_list in telegram_message.items():
            # Split key parts
            deposit_channel_method = key.split("_")
            deposit_channel = deposit_channel_method[0]
            deposit_method  = deposit_channel_method[1]
            deposit_option  = deposit_channel_method[2]
            option = escape_md(deposit_option)
            method = escape_md(deposit_method)
            channel = escape_md(deposit_channel)
            # The value list contains one string like: "deposit success - 2025-11-26 14:45:24"
            value = value_list[0]
            status, timestamp = value.split("_")
            if status == 'deposit success':
                succeed_records.append((option, method, channel))           
            elif status == 'deposit failed':
                failed_records.append((option, method, channel))
            else:
                unknown_records.append((option, method, channel))
            succeed_block = ""
            if succeed_records:
                items = [f"│ **• Options:{o} ,Method:{m}**  \n│   ├─ Channel:{c}  \n│" for o, m, c in succeed_records]
                succeed_block = f"┌─ ✅ Success **Result** ────────────┐\n" + "\n".join(items) + "\n└───────────────────────────┘"
        
            failed_block = ""
            if failed_records:
                items = [f"│ **• Options:{o} ,Method:{m}**  \n│   ├─ Channel:{c}  \n│" for o, m, c in failed_records]
                failed_block = f"\n┌─ ❌ Failed **Result** ─────────────┐\n" + "\n".join(items) + "\n└───────────────────────────┘"
            
            unknown_block = ""
            if unknown_records:
                items = [f"│ **• Options:{o} ,Method:{m}**  \n│   ├─ Channel:{c}  \n│" for o, m, c in unknown_records]
                unknown_block = f"\n┌─ ❌ Unknown **Result** ─────────────┐\n" + "\n".join(items) + "\n└───────────────────────────┘"
            
            summary_body = succeed_block + (failed_block if failed_block else "") + (unknown_block if unknown_block else "")
            caption = f"""*Deposit Payment Gateway Testing Result Summary *  
URL: [aw8thebest1\\.online](https://www\\.aw8thebest1\\.online/en\\-my)
TEAM : A8M
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
    
    #for attempt in range(3):
    #    try:
    #        await bot.send_message(chat_id=lucuss_chat_id, text=caption, parse_mode='MarkdownV2', disable_web_page_preview=True)
    #        log.info("SUMMARY SENT")
    #        break
    #    except TimedOut:
    #        log.warning(f"TELEGRAM TIMEOUT，RETRY {attempt + 1}/3...")
    #        await asyncio.sleep(3)
    #    except Exception as e:
    #        log.error(f"SUMMARY FAILED TO SENT: {e}")

async def clear_screenshot():
    picture_to_sent = glob.glob("*A8MTHEBEST*.png")
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
                if "AW8M" in sheets:
                    for attempt in range(3):
                        try:
                            df = pd.read_excel(file,sheet_name="AW8M")
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
                                df.to_excel(writer, sheet_name='AW8M', index=False)
                        except Exception as e:
                            log.warning(f"DATA PROCESS EXCEL ERROR: {e}，RETRY {attempt + 1}/3...")
                            await asyncio.sleep(5)
                else:
                    log.info("Sheets AW8M not found in file :%s"%file)
                    df = pd.DataFrame([excel_data])
                    for attempt in range(3):
                        try:
                            with pd.ExcelWriter(
                                file,
                                engine="openpyxl",
                                mode="a",
                                if_sheet_exists="replace"
                            ) as writer:
                                df.to_excel(writer, sheet_name='AW8M', index=False)
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
                            df.to_excel(writer, sheet_name='AW8M', index=False)
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
                browser = await p.chromium.launch(headless=False)
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
                await telegram_send_operation(telegram_message,failed_reason,program_complete=False)
                raise Exception("RETRY 3 TIMES....OVERALL FLOW CAN'T COMPLETE DUE TO NETWORK ISSUE")
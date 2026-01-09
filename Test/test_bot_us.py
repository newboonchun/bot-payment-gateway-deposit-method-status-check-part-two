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
    log_path = os.path.join(log_dir, "US_Debug.log")
    if os.path.exists(log_path):
        try: os.remove(log_path)
        except: pass

    logger = logging.getLogger('USBot')
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
    logger.info("US PAYMENT GATEWAY TEST STARTING...")
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

async def reenter_deposit_page(page,new_page,context,old_url,deposit_submit_button,btn,method_btn,channel_btn,pop_up_page,same_page_jump_url,recheck):
    log.info("REENTER DEPOSIT PAGE : POP UP PAGE - [%s], SAME_PAGE_URL_JUMP - [%s]"%(pop_up_page, same_page_jump_url))
    if pop_up_page == 1:
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
            await asyncio.sleep(50)
        else:
            pass  
    elif same_page_jump_url == 1:
        for attempt in range(1, 3):
            try:
                log.info(f"Trying to goto URL attempt {attempt}/{3}: {old_url}")

                response = await page.goto(old_url, timeout=30000, wait_until="domcontentloaded")
                await asyncio.sleep(2)
                await wait_for_network_stable(page, timeout=30000)

                if response and response.ok:
                    log.info("REENTER DEPOSIT PAGE - PAGE LOADED SUCCESSFULLY")
                    break
                else:
                    # if response is None or not ok
                    log.warning("Navigation response not OK")
            except:
                log.info("REENTER DEPOSIT PAGE - NETWORK NOT STABLE YET, CURRENT PAGE URL:%s"%page.url)
        
        ## important, must click back the same deposit option, method and channel button every time re-enter deposit page
        ## if not will make confuse of the current test sequence !!!
        await asyncio.sleep(5) # this delay is important !!! CANNOT REMOVED, IF REMOVED WILL CAUSE ERROR
        try:
            advertisement_close_button = page.locator(".image-announcement-close")
            await advertisement_close_button.click()
            log.info("REENTER DEPOSIT PAGE - ADVERTISEMENT CLOSE BUTTON ARE CLICKED")
        except:
            log.info("REENTER DEPOSIT PAGE - ADVERTISEMENT CLOSE BUTTON ARE NOT CLICKED")
        await asyncio.sleep(1)
        try:
            await btn.click()
            log.info("REENTER DEPOSIT PAGE - OPTION BUTTON ARE CLICKED")
        except Exception as e:
            log.info("REENTER DEPOSIT PAGE - OPTION BUTTON FAILED TO CLICKED: [%s]"%e)
        await asyncio.sleep(1)
        try:
            advertisement_close_button = page.locator(".image-announcement-close")
            await advertisement_close_button.click()
            log.info("REENTER DEPOSIT PAGE - ADVERTISEMENT CLOSE BUTTON ARE CLICKED")
        except:
            log.info("REENTER DEPOSIT PAGE - ADVERTISEMENT CLOSE BUTTON ARE NOT CLICKED")
        await asyncio.sleep(1)
        try:
            await method_btn.click()
            log.info("REENTER DEPOSIT PAGE - METHOD BUTTON ARE CLICKED")
        except Exception as e:
            log.info("REENTER DEPOSIT PAGE - METHOD BUTTON FAILED TO CLICKED: [%s]"%e)
        await asyncio.sleep(1)
        try:
            await channel_btn.click()
            log.info("REENTER DEPOSIT PAGE - CHANNEL BUTTON ARE CLICKED")
        except Exception as e:
            log.info("REENTER DEPOSIT PAGE - CHANNEL BUTTON FAILED TO CLICKED: [%s]"%e)

async def perform_login(page):
    WEBSITE_URL = "https://www.uea8sg2.com/en-sg/"
    for _ in range(3):
        try:
            log.info(f"LOGIN PROCESS - OPENING WEBSITE: {WEBSITE_URL}")
            await page.goto("https://www.uea8sg2.com/en-sg/", timeout=30000, wait_until="domcontentloaded")
            await wait_for_network_stable(page, timeout=30000)
            log.info("LOGIN PROCESS - PAGE LOADED SUCCESSFULLY")
            break
        except:
            log.warning("LOGIN PROCESS - PAGE LOADED FAILED, RETRYING")
            await asyncio.sleep(2)
    else:
        raise Exception("LOGIN PROCESS - RETRY 3 TIMES....PAGE LOADED FAILED")
        
    # Login flow um
    # Login flow uea8
    await asyncio.sleep(5)
    #<div class="image-announcement-close ">
    #     <img src="/public/html/default_whitelabel/shared-image/icons/close-btn.png" alt="announcement-close-icon"></div>
    try:
        advertisement_close_button = page.locator(".image-announcement-close")
        await advertisement_close_button.click()
        log.info("LOGIN PROCESS - ADVERTISEMENT CLOSE BUTTON ARE CLICKED")
    except:
        log.info("LOGIN PROCESS - ADVERTISEMENT CLOSE BUTTON ARE NOT CLICKED")
    #<form class="form-control">
    #      <div class="_usernamePasswordLoginContainer_oo0rk_1 username PasswordLoginContainer">
    #            <div class="_loginInput_oo0rk_5 standard-form-field">
    #                 <input class="undefined standard-input" type="text" placeholder="Username" data-name="username" value="bottesting"></div>
    #            <div class="_passwordInput_oo0rk_10 standard-form-field">
    #                 <input class="undefined standard-input" type="password" placeholder="Password" data-name="password" value="Bot1232">
    #            <button class="_button_1om7q_1 undefined _loginButton_oo0rk_15 btnLogin atoms-button">Login</button>
    #</form>
    try:
        topbar_container = page.locator('form.form-control')
        username_password_login_container = topbar_container.locator('div._usernamePasswordLoginContainer_oo0rk_1.username')
        await username_password_login_container.locator('input.undefined.standard-input[data-name="username"]').click()
        await username_password_login_container.locator('input.undefined.standard-input[data-name="username"]').fill("bottestings")
        await username_password_login_container.locator('input.undefined.standard-input[data-name="password"]').click()
        await username_password_login_container.locator('input.undefined.standard-input[data-name="password"]').fill("Bot1232")
        login_button = username_password_login_container.locator('button:has-text("Login")')
        await login_button.click()
        log.info("LOGIN PROCESS - LOGIN PROCESS SUCCESSFUL")
    except Exception as e:
        raise Exception("LOGIN PROCESS - LOGIN PROCESS FAILED:%s"%e)
    try:
        advertisement_close_button = page.locator(".image-announcement-close")
        await advertisement_close_button.click()
        log.info("LOGIN PROCESS - ADVERTISEMENT CLOSE BUTTON ARE CLICKED")
    except:
        log.info("LOGIN PROCESS - ADVERTISEMENT CLOSE BUTTON ARE NOT CLICKED")
    #try:
    #    #deposit_button_container = page.locator('div.bottom-container')
    #    deposit_button = page.locator('a.deposit-btn')
    #    await deposit_button.click()
    #    log.info("LOGIN PROCESS - DEPOSIT TOPBAR BUTTON ARE NOT CLICKED")
    #except:
    #    raise Exception("LOGIN PROCESS - DEPOSIT BUTTON FAILED TO CLICKED")
    try:
        advertisement_close_button = page.locator(".image-announcement-close")
        await advertisement_close_button.click()
        log.info("LOGIN PROCESS - ADVERTISEMENT CLOSE BUTTON ARE CLICKED")
    except:
        log.info("LOGIN PROCESS - ADVERTISEMENT CLOSE BUTTON ARE NOT CLICKED")
    
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
                try:
                    await new_page.screenshot(path="US_%s_%s_%s-%s_Payment_Page.png"%(deposit_option,deposit_method_text,deposit_channel,bank_name),timeout=60000)
                    log.info("CHECK TOAST DETECTED: SCREENSHOT SUCCESS")
                except Exception as e:
                    log.info("CHECK TOAST DETECTED: SCREENSHOT FAILED:%s"%e)
                log.info("DEPOSIT METHOD:%s, DEPOSIT CHANNEL:%s GOT PROBLEM. DETAILS:[%s]"%(deposit_method_text,deposit_channel,text))
                break
            await asyncio.sleep(0.1)
    except Exception as e:
            text = None
            toast_exist = False
            log.info("No Toast message:%s"%e)
    return toast_exist, text

async def perform_payment_gateway_test(page,context):
    exclude_list = ["Express Deposit","Bank Transfer","Ewallet","Mobile Card","PayNow"] #TBC
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
            #if deposit_option != 'P2P Transfer': #FOR DEBUG
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
                    advertisement_close_button = page.locator(".image-announcement-close")
                    await advertisement_close_button.click()
                    log.info("PERFORM PAYMENT GATEWAY TEST - ADVERTISEMENT CLOSE BUTTON ARE CLICKED")
                except:
                    log.info("PERFORM PAYMENT GATEWAY TEST - ADVERTISEMENT CLOSE BUTTON ARE NOT CLICKED")

                # DOM for deposit method
                #<div class="standard-form-field depositMethod component-2   ">
                #    <div class="standard-bank-container container-show-with-bank-image-and-text">
                #        <span class="standard-radio-content-label standard-desc ">OnePay</span>
                try:
                    deposit_methods_container = page.locator('div.standard-form-field.depositMethod')
                    await deposit_methods_container.wait_for(state="attached")
                    deposit_methods_button = deposit_methods_container.locator('div.standard-bank-container.container-show-with-bank-image-and-text')
                    deposit_methods_total_count = await deposit_methods_button.count()
                    log.info("PERFORM PAYMENT GATEWAY TEST - DEPOSIT OPTION [%s] - DEPOSIT METHODS COUNT [%s]"%(deposit_option,deposit_methods_total_count))
                    for j in range (deposit_methods_total_count):
                        no_channel = False
                        method_btn = deposit_methods_button.nth(j)
                        deposit_method = await method_btn.locator('span.standard-radio-content-label').inner_text()
                        log.info("PERFORM PAYMENT GATEWAY TEST - DEPOSIT METHOD [%s]"%deposit_method)
                        #if deposit_method != 'Vn Pay': #FOR DEBUG
                        #    continue
                        await method_btn.click()
                        log.info("PERFORM PAYMENT GATEWAY TEST - DEPOSIT METHOD [%s] BUTTON ARE CLICKED"%deposit_method)

                        # DOM for deposit channel options 
                        # there might be no deposit channel at all (Ex: Quick Pay : Fpay)
                        #<div class="standard-form-field depositOptions component-3   ">
                        #   <div class="standard-bank-container container-show-with-bank-image-and-text">
                        #        <span class="standard-radio-content-label standard-desc ">OnePay3 Prompt Pay QR Pay</span>

                        try:
                            deposit_channels_container = page.locator('div.standard-form-field.depositOptions')
                            await deposit_channels_container.wait_for(state="attached")
                            deposit_channels_button = deposit_channels_container.locator('div.standard-bank-container.container-show-with-bank-image-and-text')
                            deposit_channels_total_count = await deposit_channels_button.count()
                            log.info("PERFORM PAYMENT GATEWAY TEST - DEPOSIT OPTION [%s] - DEPOSIT METHOD [%s] - DEPOSIT CHANNELS COUNT [%s]"%(deposit_option,deposit_method,deposit_channels_total_count))
                        except Exception as e:
                            log.info("DEPOSIT CHANNEL ERROR:%s"%(e))
                            deposit_channels_total_count = 0
                            log.info("PERFORM PAYMENT GATEWAY TEST - DEPOSIT OPTION [%s] - DEPOSIT METHOD [%s] - NO DEPOSIT CHANNEL"%(deposit_option,deposit_method))
                        if deposit_channels_total_count == 0:
                            deposit_channel_counter = 1
                        else:
                            deposit_channel_counter = deposit_channels_total_count
                        for k in range (deposit_channel_counter):
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
                                deposit_channel = "-"
                                pass

                            # DOM for bank options
                            #<div class="standard-form-field thirdPartyBankOptions component-5   ">
                            #   <div class="standard-bank-container container-show-with-bank-image-and-text">
                            #         <span class="standard-radio-content-label standard-desc ">Vietnam International Bank </span>
                            try:
                                third_party_bank_options_container = page.locator('div.standard-form-field.thirdPartyBankOptions')
                                await third_party_bank_options_container.wait_for(state="attached", timeout=5000)
                                third_party_bank_options_button = third_party_bank_options_container.locator('div.standard-bank-container.container-show-with-bank-image-and-text')
                                third_party_bank_options_total_count = await third_party_bank_options_button.count()
                                log.info("PERFORM PAYMENT GATEWAY TEST - DEPOSIT OPTION [%s] - DEPOSIT METHOD [%s] - DEPOSIT CHANNEL [%s] - THIRD PARTY BANK OPTIONS COUNT [%s]"%(deposit_option,deposit_method,deposit_channel,third_party_bank_options_total_count))
                            except Exception as e: # if no bank options
                                third_party_bank_options_total_count = 0
                                log.info("PERFORM PAYMENT GATEWAY TEST - DEPOSIT OPTION [%s] - DEPOSIT METHOD [%s] - DEPOSIT CHANNEL [%s] - NO THIRD PARTY BANK OPTIONS"%(deposit_option,deposit_method,deposit_channel))
                                log.info("THIRD PARTY BANK OPTION  ERROR:%s"%(e))
                            if third_party_bank_options_total_count == 0:
                                third_party_bank_options_counter = 1
                            else:
                                third_party_bank_options_counter = third_party_bank_options_total_count
                            for l in range (third_party_bank_options_counter):
                                if l >= 1:
                                    log.info("BANK COUNTER [%s] >=3, SKIP NEXT CHECK"%l)
                                    continue
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
                                ## DOM for deposit amount input
                                # <div class="standard-form-field depositAmount component-7   ">
                                #    <input id="depositamount" type="numeric" autocomplete="off" class="standard-input" placeholder="Amount MIN: 100.00 / MAX: 30,000.00" min="0" pattern="[0-9]*" inputmode="decimal" value="">
                                try:
                                    await asyncio.sleep(5) #give some delay for the page to load the deposit amount min max range
                                    deposit_amount_input_container = page.locator('div.standard-form-field.depositAmount')
                                    deposit_amount_input_box = deposit_amount_input_container.locator('input[id="depositamount"]')
                                    deposit_amount_input_range = await deposit_amount_input_box.get_attribute("placeholder")
                                    log.info("DEPOSIT AMOUNT INPUT RANGE [%s] "%(deposit_amount_input_range))
                                    matches = re.findall(r"(\d[\d,]*\.\d+|\d+)", deposit_amount_input_range)
                                    min_amount = matches[0]  # The first match is the minimum value
                                    await deposit_amount_input_box.fill("%s"%int(float(min_amount)))
                                    log.info("DEPOSIT AMOUNT INPUT [%s] KEYED IN"%int(float(min_amount)))
                                except Exception as e:
                                    log.info("DEPOSIT AMOUNT INPUT ERROR:%s"%(e))
                                    log.info("PROCEED TO NEXT CHANNEL TEST:%s"%(e))
                                    break ## go to next method if deposit amount input cannot locate
                                
                   ################### to decide either there is pop up page, or stays at same page ####################
                                deposit_submit_button_no_action = 0
                                max_retries = 2
                                retry_count = 0
                                while retry_count < max_retries:
                                    if retry_count == 0:
                                        timeout_time = 30000
                                    else:
                                        timeout_time = 5000
                                    new_page = page
                                    pop_up_page = 0
                                    same_page_jump_url = 0
                                    current_old_url = page.url
                                    popup_future = asyncio.create_task(page.context.wait_for_event("page", timeout=timeout_time))     
                                    navigation_future = asyncio.create_task(
                                                                            page.wait_for_url(lambda url: url != current_old_url, timeout=timeout_time)
                                                                        )

                                    ## DOM for deposit submit button
                                        # <div class="standard-form-field transactionButton component-8   ">
                                        #   <button id="" class="standard-submit-form-button " data-button-category="submit" type="submit">
                                    try:
                                        deposit_submit_container = page.locator('div.standard-form-field.transactionButton')
                                        deposit_submit_button = deposit_submit_container.locator('button[data-button-category="submit"]')
                                        await deposit_submit_button.wait_for(state="visible", timeout=30000)
                                        await deposit_submit_button.click()
                                        log.info("DEPOSIT BUTTON CLICKED")
                                    except Exception as e:
                                        raise Exception("URL_JUMP_CHECK: DEPOSIT BUTTON FAILED TO CLICKED:%s"%e)

                                    try:
                                        done, pending = await asyncio.wait(
                                                                [popup_future, navigation_future],
                                                                return_when=asyncio.FIRST_COMPLETED,
                                                            )
                                        for task in pending:
                                            task.cancel()

                                        if popup_future in done:
                                            pop_up_page = 1
                                            new_page = popup_future.result()
                                            #new_page = await popup_info.value
                                            new_url = new_page.url
                                            log.info("POPUP PAGE OPENED: %s", new_page.url)
                                            break
                                        elif navigation_future in done:
                                            same_page_jump_url = 1
                                            new_url = page.url
                                            new_page = page
                                            log.info("SAME PAGE NAVIGATION DETECTED: %s", page.url)
                                            break
                                        else:
                                            log.info("DEPOSIT CLICK DID NOT TRIGGER ANY ACTION")
                                            retry_count += 1
                                            if retry_count == max_retries:
                                                log.info("❌ Failed: DEPOSIT CLICK DID NOT TRIGGER ANY ACTION AFTER 1 RETRY.")
                                                await new_page.screenshot(path="USTHEBEST_%s_%s_%s-%s_Payment_Page.png"%(deposit_option,deposit_method,deposit_channel,bank_name),timeout=60000)
                                                telegram_message[f"{deposit_channel}-{bank_name}_{deposit_method}_{deposit_option}"] = [f"deposit failed_{date_time("Asia/Bangkok")}"]
                                                failed_reason[f"{deposit_channel}-{bank_name}_{deposit_method}_{deposit_option}"] = [f"payment page failed load"]
                                                deposit_submit_button_no_action = 1
                                                break
                                            else:
                                                log.info("RETRYING...: ATTEMPT [%s] of [%s]"%(retry_count,max_retries))
                                                await asyncio.sleep(5)

                                    except Exception as e:
                                        log.info("ERROR:%s"%e)
                                        log.info("DEPOSIT CLICK DID NOT TRIGGER ANY ACTION")
                                        if new_page.url != current_old_url:
                                            log.info("NO NAVIGATION HAPPENED & NO POP UP PAGE,BUT OLD URL [%s] ARE DIFFERENT WITH CURRENT PAGE URL [%s]"%(current_old_url,new_page.url))
                                            raise Exception ("NO NAVIGATION HAPPENED & NO POP UP PAGE,BUT OLD URL [%s] ARE DIFFERENT WITH CURRENT PAGE URL [%s]"%(current_old_url,new_page.url))
                                        retry_count += 1
                                        if retry_count == max_retries:
                                            log.info("❌ Failed: DEPOSIT CLICK DID NOT TRIGGER ANY ACTION AFTER %s RETRY."%retry_count)
                                            await new_page.screenshot(path="US_%s_%s_%s-%s_Payment_Page.png"%(deposit_option,deposit_method,deposit_channel,bank_name),timeout=60000)
                                            telegram_message[f"{deposit_channel}-{bank_name}_{deposit_method}_{deposit_option}"] = [f"deposit failed_{date_time("Asia/Bangkok")}"]
                                            failed_reason[f"{deposit_channel}-{bank_name}_{deposit_method}_{deposit_option}"] = [f"payment page failed load"]
                                            deposit_submit_button_no_action = 1
                                            break
                                        else:
                                            log.info("RETRYING...: ATTEMPT [%s] of [%s]"%(retry_count,max_retries))
                                            await asyncio.sleep(5)
                                    
                                if deposit_submit_button_no_action == 1:
                                    continue

                                log.info("POP UP PAGE - [%s], SAME_PAGE_URL_JUMP - [%s]"%(pop_up_page, same_page_jump_url))
                                log.info("OLD URL - [%s]"%(old_url))
                                log.info("PAYMENT PAGE - [%s]"%(new_url))
                    ################### to decide either there is pop up page, or stays at same page ####################
                                try:
                                    toast_exist, toast_failed_text = await check_toast(page,new_page,deposit_option,deposit_method,deposit_channel,bank_name)
                                except Exception as e:
                                    log.info("TOAST CHECK ERROR: [%s]"%e)
                                if toast_exist:
                                    telegram_message[f"{deposit_channel}-{bank_name}_{deposit_method}_{deposit_option}"] = [f"deposit failed_{date_time("Asia/Bangkok")}"]
                                    failed_reason[f"{deposit_channel}-{bank_name}_{deposit_method}_{deposit_option}"] = [toast_failed_text]
                                    log.info("TOAST DETECTED")
                                    if pop_up_page:
                                        await new_page.close()
                                    elif same_page_jump_url:
                                        await reenter_deposit_page(page,new_page,context,current_old_url,deposit_submit_button,btn,method_btn,channel_btn,pop_up_page,same_page_jump_url,recheck=0)
                                    await asyncio.sleep(30)
                                    continue
                                else:
                                    log.info("NO TOAST DETECTED")
                                    await new_page.screenshot(path="US_%s_%s_%s-%s_Payment_Page.png"%(deposit_option,deposit_method,deposit_channel,bank_name),timeout=60000)
                                    telegram_message[f"{deposit_channel}-{bank_name}_{deposit_method}_{deposit_option}"] = [f"deposit success_{date_time("Asia/Bangkok")}"]
                                    failed_reason[f"{deposit_channel}-{bank_name}_{deposit_method}_{deposit_option}"] = [f"-"]
                                    if pop_up_page:
                                        await new_page.close()
                                    elif same_page_jump_url:
                                        await reenter_deposit_page(page,new_page,context,current_old_url,deposit_submit_button,btn,method_btn,channel_btn,pop_up_page,same_page_jump_url,recheck=0)
                                    await asyncio.sleep(30)
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
    jr_raymond_chat_id = os.getenv("JR_RAYMOND_CHAT_ID")
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
URL: [uea8sg2\\.com](https://www\\.uea8sg2\\.com/en\\-sg)
TEAM : US
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

            jr_raymond_caption = f"""[W\\_Karman](tg://user?id=5615912046)
*Subject: Bot Testing Deposit Gateway*  
URL: [uea8sg2\\.com](https://www\\.uea8sg2\\.com/en\\-sg)
TEAM : US
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
            files = glob.glob("*US_%s_%s_%s*.png"%(deposit_option,deposit_method,deposit_channel))
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
                #                    chat_id=jr_raymond_chat_id,
                #                    photo=f,
                #                    caption=jr_raymond_caption,
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
                "⚠️ *US RETRY 3 TIMES FAILED*\n"
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
    jr_raymond_chat_id = os.getenv("JR_RAYMOND_CHAT_ID")
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
URL: [uea8sg2\\.com](https://www\\.uea8sg2\\.com/en\\-sg)
TEAM : US
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
    #        await bot.send_message(chat_id=jr_raymond_chat_id, text=caption, parse_mode='MarkdownV2', disable_web_page_preview=True)
    #        log.info("SUMMARY SENT")
    #        break
    #    except TimedOut:
    #        log.warning(f"TELEGRAM TIMEOUT，RETRY {attempt + 1}/3...")
    #        await asyncio.sleep(3)
    #    except Exception as e:
    #        log.error(f"SUMMARY FAILED TO SENT: {e}")

async def clear_screenshot():
    picture_to_sent = glob.glob("*US*.png")
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
                if "US" in sheets:
                    for attempt in range(3):
                        try:
                            df = pd.read_excel(file,sheet_name="US")
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
                                df.to_excel(writer, sheet_name='US', index=False)
                        except Exception as e:
                            log.warning(f"DATA PROCESS EXCEL ERROR: {e}，RETRY {attempt + 1}/3...")
                            await asyncio.sleep(5)
                else:
                    log.info("Sheets US not found in file :%s"%file)
                    df = pd.DataFrame([excel_data])
                    for attempt in range(3):
                        try:
                            with pd.ExcelWriter(
                                file,
                                engine="openpyxl",
                                mode="a",
                                if_sheet_exists="replace"
                            ) as writer:
                                df.to_excel(writer, sheet_name='US', index=False)
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
                            df.to_excel(writer, sheet_name='US', index=False)
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
                #log.info("TELEGRAM MESSAGE :%s"%telegram_message)
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
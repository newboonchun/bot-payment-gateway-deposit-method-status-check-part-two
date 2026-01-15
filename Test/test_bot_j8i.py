import asyncio
import pytest
from playwright.async_api import async_playwright, Page, Dialog, TimeoutError
import logging
import os
import glob
import requests
import time
import pytz
from datetime import datetime, timezone, timedelta
from telegram import Bot
import re
from telegram.error import TimedOut
from dotenv import load_dotenv
import pandas as pd
from urllib.parse import unquote

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
    log_path = os.path.join(log_dir, "J8I_Debug.log")
    if os.path.exists(log_path):
        try: os.remove(log_path)
        except: pass

    logger = logging.getLogger('J8IBot')
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
    logger.info("J8I PAYMENT GATEWAY TEST STARTING...")
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

async def reenter_deposit_page(page,old_url,deposit_method,deposit_channel,bank_name,bank_btn,min_amount,recheck):
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
    try:
        await page.get_by_role("button", name="%s"%deposit_method).click()
        log.info("REENTER DEPOSIT PAGE - DEPOSIT METHOD [%s] BUTTON ARE CLICKED"%deposit_method)
    except:
        raise Exception("REENTER DEPOSIT PAGE - DEPOSIT METHOD [%s] BUTTON ARE FAILED CLICKED"%deposit_method)
    try:
        await page.get_by_role("button", name="%s"%deposit_channel).click()
        log.info("REENTER DEPOSIT PAGE - DEPOSIT CHANNEL [%s] BUTTON ARE CLICKED"%deposit_channel)
    except:
        raise Exception("REENTER DEPOSIT PAGE - DEPOSIT CHANNEL [%s] BUTTON ARE FAILED CLICKED"%deposit_channel)
    if bank_btn !=None:
        try:
            await bank_btn.click()
            log.info("REENTER DEPOSIT PAGE - BANK [%s] BUTTON ARE CLICKED"%bank_name)
        except:
            raise Exception("REENTER DEPOSIT PAGE - BANK [%s] BUTTON ARE FAILED CLICKED"%bank_name)
    try:
        await page.get_by_placeholder("0").click()
        await page.get_by_placeholder("0").fill("%s"%min_amount)
        log.info("REENTER DEPOSIT PAGE - MIN AMOUNT [%s] ARE KEYED IN"%min_amount)
    except:
        raise Exception("PERFORM PAYMENT GATEWAY TEST - MIN AMOUNT [%s] ARE NOT KEYED IN"%min_amount)
    if recheck:
        try:
            deposit_submit_button = page.locator('button.btn_deposits.uppercase:has-text("Deposit")')
            await deposit_submit_button.click()
            log.info("REENTER DEPOSIT PAGE - เติมเงิน/DEPOSIT TOP UP BUTTON ARE CLICKED")
        except:
            raise Exception("REENTER DEPOSIT PAGE - เติมเงิน/DEPOSIT TOP UP BUTTON ARE FAILED TO CLICK")
    else:
        pass  

async def perform_login(page):
    WEBSITE_URL = "https://www.jw8my.com/en-in"
    for _ in range(3):
        try:
            log.info(f"LOGIN PROCESS - OPENING WEBSITE: {WEBSITE_URL}")
            await page.goto("https://www.jw8my.com/en-in", timeout=30000, wait_until="domcontentloaded")
            await wait_for_network_stable(page, timeout=30000)
            log.info("LOGIN PROCESS - PAGE LOADED SUCCESSFULLY")
            break
        except:
            log.warning("LOGIN PROCESS - PAGE LOADED FAILED, RETRYING")
            await asyncio.sleep(2)
    else:
        raise Exception("LOGIN PROCESS - RETRY 3 TIMES....PAGE LOADED FAILED")
    #<div id="normal-slidedown">
    #   <div class="slidedown-body" id="slidedown-body">
    #   <div class="slidedown-footer" id="slidedown-footer">
    #           <button class="align-right primary slidedown-button" id="onesignal-slidedown-allow-button">Yes, I am</button>
    #           <button class="align-right secondary slidedown-button" id="onesignal-slidedown-cancel-button">No, I am not</button><div class="clearfix"></div></div></div>
    await asyncio.sleep(5)
    try:
        slidedown = page.locator("div.slidedown-footer")
        await slidedown.locator('button.align-right.primary.slidedown-button').click()
        log.info("LOGIN PROCESS - NOTIFICATION OVER 18 YEARS OLD ARE CLOSED")
    except:
        log.info("NO SLIDEDOWN, SKIP")
    try:
        first_advertisement_dont_show_checkbox = page.locator(".o-checkbox").first
        await first_advertisement_dont_show_checkbox.wait_for(state="visible", timeout=10000)
        await first_advertisement_dont_show_checkbox.click()
        close_button = page.get_by_role("button", name="Close")
        close_button_count = await close_button.count()
        for i in range(close_button_count):
            try:
                await close_button.nth(i).click()
                log.info("LOGIN PROCESS - CLOSE BUTTON ARE CLICKED")
                break
            except Exception as e:
                log.info("LOGIN PROCESS - CLOSE BUTTON ERROR:%s"%e)
    except Exception as e:
        log.info("LOGIN PROCESS - FIRST ADVERTISEMENT DIDN'T APPEARED:%s"%e)
        
    # Login flow j8i
    # <button data-v-4fff4a3f="" type="button" class="topbar_btn_1" aria-label="Login">Login</button> -> has more than 1, cannot locate directly
    
    login_button = page.locator('button.topbar_btn_1')
    login_button_count = await login_button.count()
    for i in range(login_button_count):
        try:
            await login_button.nth(i).click()
            log.info("LOGIN PROCESS - LOGIN BUTTON ARE CLICKED")
            break
        except Exception as e:
            log.info("LOGIN PROCESS - LOGIN BUTTON ERROR:%s"%e)
    await asyncio.sleep(1)
    #class DOM: <button type="button" aria-label="account" class="reg-tab">
    try:
        account_button = page.locator('button.reg-tab[aria-label="account"]')
        await account_button.click()
        log.info("LOGIN PROCESS -  Account BUTTON ARE CLICKED")
    except:
        raise Exception("LOGIN PROCESS -  Account BUTTON ARE FAILED TO CLICKED")
    await asyncio.sleep(1)
    try:
        await page.get_by_role("textbox", name="Username").click()
        log.info("LOGIN PROCESS - USERNAME TEXTBOX ARE CLICKED")
    except:
        raise Exception("LOGIN PROCESS - USERNAME TEXTBOX ARE FAILED TO CLICK")
    await asyncio.sleep(1)
    try:
        await page.get_by_role("textbox", name="Username").fill("bottestingsssss")
        log.info("LOGIN PROCESS - USERNAME DONE KEYED")
    except:
        raise Exception("LOGIN PROCESS - USERNAME FAILED TO KEY IN")
    await asyncio.sleep(1)
    try:
        await page.get_by_role("textbox", name="Password").click()
        log.info("LOGIN PROCESS - PASSWORD TEXTBOX ARE CLICKED")
    except:
        raise Exception("LOGIN PROCESS - PASSWORD TEXTBOX ARE FAILED TO CLICK")
    await asyncio.sleep(1)
    try:
        await page.get_by_role("textbox", name="Password").fill("123456")
        log.info("LOGIN PROCESS - PASSWORD DONE KEYED")
    except:
        raise Exception("LOGIN PROCESS - PASSWORD FAILED TO KEY IN")
    await asyncio.sleep(1)
    #class DOM: <button type="submit" class="btn primary w-full new-reg-buttons">Login</button>
    try:
        login_button = page.locator('button.btn.primary.new-reg-buttons:has-text("Login")')
        await login_button.click()
        log.info("LOGIN PROCESS - LOGIN BUTTON ARE CLICKED")
    except:
        raise Exception("LOGIN PROCESS - LOGIN BUTTON ARE FAILED TO CLICKED")
    await asyncio.sleep(1)
    try:
        advertisement_close_button = page.locator(".icon-close.text-lg")
        await advertisement_close_button.click()
        log.info("LOGIN PROCESS - ADVERTISEMENT CLOSE BUTTON ARE CLICKED")
    except:
        log.info("LOGIN PROCESS - ADVERTISEMENT CLOSE BUTTON ARE NOT CLICKED")
    #class DOM: <div data-v-4fff4a3f="" class="deposit_topbar">
    #                <button data-v-4fff4a3f="" type="button" class="topbar_btn_2 mx-2 md:mx-[10px] flex items-center justify-center deposit_display_big" aria-label="Deposit" id="deposit_btn_12">Deposit</button> -->this is
    #                <button data-v-4fff4a3f="" type="button" class="mr-3 deposit_display_small rounded-md topbar_deposit_icon_btn" aria-label="Deposit" id="deposit_btn_13"> --> this is not
    try:
        deposit_topbar_container = page.locator('div.deposit_topbar')
        deposit_topbar_button = deposit_topbar_container.locator('button.topbar_btn_2:has-text("Deposit")')
        await deposit_topbar_button.click()
        log.info("LOGIN PROCESS - DEPOSIT BUTTON ARE CLICKED")
    except:
        raise Exception("LOGIN PROCESS - DEPOSIT BUTTON ARE FAILED TO CLICK")

async def confirmation_deposit_success_check(page):
    #<div data-v-e931c5d4="" class="pb-4 flex flex-col items-center justify-center">
    #    <div data-v-e931c5d4="" class="px-4 py-2 md:text-base font-bold">Confirmation</div>
    #     <div data-v-e931c5d4="">Success! Please go to the deposit page.</div></div>
    #<button data-v-e931c5d4="" class="btn-redirect w-[280px] h-[60px]">
    #     <p data-v-e931c5d4="" class="text-center uppercase">go</p></button>
    try:
        confirmation_deposit_button= page.locator('button.btn-redirect:has-text("go")')
        await confirmation_deposit_button.wait_for(state='visible', timeout=30000)
        confirmation_deposit_button_count = 1
        is_visible = True
    except Exception as e:
        confirmation_deposit_button_count = 0
        is_visible = False
        log.info("CONFIRMATION DEPOSIT SUCCESS CHECK ERROR : %e")
    
    log.info("CONFIRMATION DEPOSIT SUCCESS CHECK: confirmation_deposit_button_count = [%s], visible = [%s]"%(confirmation_deposit_button_count, is_visible))
    await asyncio.sleep(5)

    return confirmation_deposit_button_count

async def payment_iframe_check(page):
    ## DETECT PAYMENT IFRAME BASED ON HTML CONTENT !!! ##
    payment_iframe_count = 0
    error_text = 0
    try:
        #await page.wait_for_selector("iframe", timeout=3000)
        iframe_count = await page.locator("iframe").count()
        log.info("IFRAME/POP UP APPEARED. IFRAME COUNT:%s"%iframe_count)
        for i in range(iframe_count):
            try:
                base = page.locator("iframe").nth(i)
                sandbox_attribute = await base.get_attribute('sandbox')
                log.info(f"Sandbox attribute for iframe {i}: {sandbox_attribute}")
                if sandbox_attribute == None:
                    pass
                elif 'allow-forms allow-scripts' in sandbox_attribute:
                    payment_iframe_count = 1
                    break
                #log.info("IFRAME PAYMENT APPEARED. IFRAME PAYMENT COUNT:%s"%payment_iframe_count)
            except Exception as e:
                log.info(f"Sandbox attribute for iframe {i} ERROR!!: {e}")
                #log.info("IFRAME PAYMENT CANNOT LOCATE FOR %s IFRAME : [%s]"%(i,e))
    except Exception as e:
        log.info("No IFRAME/POP UP APPEARED:%s"%e)
    
    log.info(f"PAYMENT IFRAME COUNT : {payment_iframe_count}")

    ## locate certain text error
    if payment_iframe_count != 0:
        try:
            base = page.frame_locator("iframe").nth(i)
            iframe_q_container = base.locator("div.q-page-container")
            iframe_text = await iframe_q_container.inner_text(timeout=5000)
            log.info(f"INNER TEXT for iframe {i} : {iframe_text}")
            if '404 Page Not Found' in iframe_text:
                log.info("404 Page Not Found !!!")
                error_text = 1
        except Exception as e:
            log.info(f"INNER TEXT for iframe {i} ERROR!!: {e}")
            #log.info("IFRAME PAYMENT CANNOT LOCATE FOR %s IFRAME : [%s]"%(i,e))

    log.info(f"ERROR TEXT  : {error_text}")

    return payment_iframe_count,error_text

async def qr_code_check(page):
    ## DETECT QR CODE BASED ON HTML CONTENT !!! ##
    try:
        #await page.wait_for_selector("iframe", timeout=3000)
        iframe_count = await page.locator("iframe").count()
        if iframe_count == 1:
            await page.wait_for_selector("iframe", timeout=3000)
        else:
            pass
        log.info("IFRAME/POP UP APPEARED. IFRAME COUNT:%s"%iframe_count)
    except Exception as e:
        iframe_count = 0
        log.info("No IFRAME/POP UP APPEARED:%s"%e)

    qr_selector = [
        "div.qr-image",
        "div.qr-image.position-relative",
        "div.payFrame", #for fpay-crypto
        "div[id*='qr' i]",
        "div[class*='qrcode']",
        "div#qrcode-container",
        "div#dowloadQr"
    ]

    qr_code_count = 0

    if iframe_count != 0:
        for i in range(iframe_count):
            if qr_code_count != 0:
                break
            try:
                base = page.frame_locator("iframe").nth(i)
                for selector in qr_selector:
                    try:
                        qr_code = base.locator(selector)
                        qr_code_count = await qr_code.count()
                        log.info("QR_CODE:%s QR_CODE_COUNT:%s"%(qr_code,qr_code_count))
                        if qr_code_count != 0:
                            break
                    except Exception as e:
                        qr_code_count = 0 
                        log.info("QR_CODE_CHECK LOOP SELECTOR:%s"%e)
            except Exception as e:
                log.info("QR_CODE_CHECK ERROR:%s"%e)
                pass

    # second stage check
    if qr_code_count == 0:
        base = page
        for selector in qr_selector:
            try:
                qr_code = base.locator(selector)
                qr_code_count = await qr_code.count()
                log.info("QR_CODE:%s , QR_CODE_COUNT:%s"%(qr_code,qr_code_count))
                if qr_code_count != 0:
                    break
            except Exception as e:
                qr_code_count = 0 
                log.info("QR_CODE_CHECK LOOP SELECTOR:%s"%e)
    
    if qr_code_count != 0:
        log.info("QR DETECTED")
    else:
        log.info("NO QR DETECTED")
    return qr_code_count

async def url_jump_check(page,old_url,deposit_method,deposit_channel,bank_name,bank_btn,money_button_text,telegram_message):
    try:
        async with page.expect_navigation(wait_until="load", timeout=30000):
            #class DOM: <button data-v-7a9f759f="" type="button" aria-label="Deposit" class="btn_deposits uppercase font-semibold rounded-md">Deposit</button>
            try:
                deposit_submit_button = page.locator('button.btn_deposits.uppercase:has-text("Deposit")')
                await deposit_submit_button.wait_for(state="visible", timeout=60000)
                await deposit_submit_button.click()
                log.info("URL JUMP CHECK - เติมเงิน/DEPOSIT TOP UP BUTTON ARE CLICKED")
            except:
                raise Exception("URL JUMP CHECK - เติมเงิน/DEPOSIT TOP UP BUTTON ARE FAILED TO CLICK")
            #await page.get_by_role("button", name="เติมเงิน").nth(2).click()
        
        # Wait until the URL actually changes (final page)
        await page.wait_for_function(
            "url => window.location.href !== url",
            arg=old_url,
            timeout=60000
        )
        new_url = page.url
        if new_url != old_url:
            log.info("LOADING INTO NEW PAGE [%s]"%(new_url))
            new_payment_page = True
    except TimeoutError:
        # If no navigation happened, page stays the same
        new_payment_page = False
        log.info("NO NAVIGATION HAPPENED, STAYS ON SAME PAGE [%s]"%(page.url))
    
    if new_payment_page == True:
        max_retries = 3
        retry_count = 0
        while retry_count < max_retries:
            try:
                await asyncio.sleep(10)
                await page.wait_for_load_state("networkidle", timeout=70000) #added to ensure the payment page is loaded before screenshot is taken
                log.info("NEW PAGE [%s] LOADED SUCCESSFULLY"%(new_url))
                await page.screenshot(path="J8I_%s_%s-%s_Payment_Page.png"%(deposit_method,deposit_channel,bank_name),timeout=30000)
                break 
            except TimeoutError:
                log.info("TIMEOUT: PAGE DID NOT REACH NETWORKIDLE WITHIN 70s")
                qr_code_count = await qr_code_check(page)
                if qr_code_count != 0:
                    log.info("NEW PAGE [%s] STILL LOADING, BUT PAY FRAME IS LOADED"%(new_url))
                    await page.screenshot(path="J8I_%s_%s-%s_Payment_Page.png"%(deposit_method,deposit_channel,bank_name),timeout=30000)
                    break
                else:
                    retry_count += 1
                    if retry_count == max_retries:
                        log.info("❌ Failed: Page did not load after 3 retries.")
                        await page.screenshot(path="J8I_%s_%s-%s_Payment_Page.png"%(deposit_method,deposit_channel,bank_name),timeout=30000)
                        url_jump = True
                        payment_page_failed_load = True
                    else:
                        log.info("RETRYING...: ATTEMPT [%s] of [%s]"%(retry_count,max_retries))
                        try:
                            await reenter_deposit_page(page,old_url,deposit_method,deposit_channel,bank_name,bank_btn,money_button_text,recheck=1)
                        except:
                            log.info("FAILED GO BACK TO OLD PAGE [%s] AND RETRY..."%(old_url))

    if new_payment_page == False:   
        await page.screenshot(path="J8I_%s_%s-%s_Payment_Page.png"%(deposit_method,deposit_channel,bank_name),timeout=30000)
        url_jump = False
        payment_page_failed_load = False

    if new_payment_page and retry_count<3:
        url_jump = True
        payment_page_failed_load = False
    
    return url_jump, payment_page_failed_load

async def check_toast(page,deposit_method,deposit_channel,bank_name):
    toast_exist = False
    try:
        await page.get_by_role("button", name="%s"%deposit_method, exact=True).click()
        log.info("CHECK TOAST - DEPOSIT METHOD [%s] BUTTON ARE CLICKED"%deposit_method)
    except:
        raise Exception("CHECK TOAST - DEPOSIT METHOD [%s] BUTTON ARE FAILED CLICKED"%deposit_method)
    try:
        await page.get_by_role("button", name="%s"%deposit_channel, exact=True).click()
        log.info("CHECK TOAST - DEPOSIT CHANNEL [%s] BUTTON ARE CLICKED"%deposit_channel)
    except:
        raise Exception("CHECK TOAST - DEPOSIT CHANNEL [%s] BUTTON ARE FAILED CLICKED"%deposit_channel)
    money_input_range = page.locator('div.deposit_channel_title_text.flex.justify-between')
    await money_input_range.wait_for(state="attached", timeout=3000)
    money_input_range_text = (await money_input_range.inner_text())
    matches = re.findall(r"₹\s*([\d,]+)", money_input_range_text)
    if matches:
        min_amount = matches[0]            
        min_amount = min_amount.replace(",", "")  # remove comma if any
        print(min_amount)
    else:
        log.warning("NO MINIMUM DEPOSIT AMOUNT INPUT")
    try:
        await page.get_by_placeholder("0").click()
        await page.get_by_placeholder("0").fill("%s"%min_amount)
        log.info("CHECK TOAST - MIN AMOUNT [%s] ARE KEYED IN"%min_amount)
    except:
        raise Exception("CHECK TOAST - MIN AMOUNT [%s] ARE NOT KEYED IN"%min_amount)
    try:
        deposit_submit_button = page.locator('button.btn_deposits.uppercase:has-text("Deposit")')
        await deposit_submit_button.wait_for(state="visible", timeout=60000)
        await deposit_submit_button.click()
        log.info("CHECK TOAST - เติมเงิน/DEPOSIT TOP UP BUTTON ARE CLICKED")
    except Exception as e:
        raise Exception("CHECK TOAST - เติมเงิน/DEPOSIT TOP UP BUTTON ARE FAILED TO CLICK:%s"%e)
    try:
        for _ in range(20):
            toast = page.locator('div.toast-message.text-sm')
            await toast.wait_for(state="attached", timeout=10000)
            text = (await toast.inner_text()).strip()
            if await toast.count() > 0:
                toast_exist = True
                await page.screenshot(path="J8I_%s_%s-%s_Payment_Page.png"%(deposit_method,deposit_channel,bank_name),timeout=30000)
                log.info("DEPOSIT METHOD:%s, DEPOSIT CHANNEL:%s GOT PROBLEM. DETAILS:[%s]"%(deposit_channel,deposit_method,text))
                break
            await asyncio.sleep(0.1)
    except:
            text = None
            toast_exist = False
            await page.screenshot(path="J8I_%s_%s-%s_Payment_Page.png"%(deposit_method,deposit_channel,bank_name),timeout=30000)
            log.info("No Toast message, no proceed to payment page, no qr code, please check what reason manually.")
    return toast_exist, text

async def perform_payment_gateway_test(page):
    method_exclude_list = ["Phone Card","Telco","Bank Transfer","Crypto"]
    exclude_list = ["Bank Transfer", "Government Savings Bank", "Government Saving Bank", "ธ.", "ธนาคารออมสิน", "ธนาคารกสิกรไทย", "ธนาคารไทยพาณิชย์","ธนาคาร","กสิกรไทย"]
    telegram_message = {}
    failed_reason = {}
    deposit_method_container = page.locator(".deposit-method-container")
    await deposit_method_container.wait_for(state="attached")
    deposit_method_button = deposit_method_container.locator("button")
    deposit_method_total_count = await deposit_method_button.count()
    for i in range(deposit_method_total_count):
        old_url = page.url
        btn = deposit_method_button.nth(i)
        deposit_method = await btn.get_attribute("aria-label")
        if any(method_exclude in deposit_method for method_exclude in method_exclude_list):
            log.info(f"DEPOSIT METHOD [{deposit_method}] IS NOT PAYMENT GATEWAY, SKIPPING CHECK...")
            continue
        else:
            pass
        #if deposit_method != 'Bkash': #FOR DEBUG
        #    continue
        # deposit method click
        try:
            await page.get_by_role("button", name="%s"%deposit_method, exact=True).click()
            log.info("PERFORM PAYMENT GATEWAY TEST - DEPOSIT METHOD [%s] BUTTON ARE CLICKED"%deposit_method)
        except:
            raise Exception("PERFORM PAYMENT GATEWAY TEST - DEPOSIT METHOD [%s] BUTTON ARE FAILED CLICKED"%deposit_method)
        log.info("URL AFTER DEPOSIT METHOD [%s] BUTTON CLICK: [%s]"%(deposit_method,old_url))
        deposit_channel_container = page.locator(".deposit-channel-container")
        ## the first is deposit channel container, second is bank container
        deposit_channel_container_count = await deposit_channel_container.count()
        log.info("FOUND [%s] DEPOSIT CHANNEL CONTAINER COUNT"%(deposit_channel_container_count))
        await deposit_channel_container.first.wait_for(state="attached")
        deposit_channel_button = deposit_channel_container.locator("button")
        deposit_channel_count = await deposit_channel_button.count()
        log.info("FOUND [%s] DEPOSIT CHANNEL FOR DEPOSIT METHOD [%s]"%(deposit_channel_count,deposit_method))
        for j in range(deposit_channel_count):
            manual_bank = False
            btn = deposit_channel_button.nth(j)
            deposit_channel = await btn.get_attribute("aria-label")
            #if deposit_channel != 'GOPAY': #FOR DEBUG
            #    continue
            log.info("DEPOSIT CHANNEL [%s] "%(deposit_channel))
            if any(manual_bank in deposit_channel for manual_bank in exclude_list):
                log.info(f"DEPOSIT CHANNEL [{deposit_channel}] IS NOT PAYMENT GATEWAY, SKIPPING CHECK...")
                continue
            else:
                pass
            # click deposit button...start load to payment page
            try:
                await page.get_by_role("button", name="%s"%deposit_channel, exact=True).click()
                log.info("PERFORM PAYMENT GATEWAY TEST - DEPOSIT CHANNEL [%s] BUTTON ARE CLICKED"%deposit_channel)
            except Exception as e:
                raise Exception("PERFORM PAYMENT GATEWAY TEST - DEPOSIT CHANNEL [%s] BUTTON ARE FAILED CLICKED [%s]"%(deposit_channel,e))
            # DOM for select bank
            # <div data-v-b4a2ad53="" class="grid grid-cols-3 deposit-channel-container">
            #       <div data-v-b4a2ad53="" class="text-center">...<div>
            #       <div data-v-b4a2ad53="" class="text-center">...<div>
            #       <div data-v-b4a2ad53="" class="text-center">...<div>
            #       <div data-v-b4a2ad53="" class="text-center">...<div>
            try:
                select_bank_container = page.locator(".deposit-channel-container").nth(1)
                bank_buttons = select_bank_container.locator('div.text-center')
                bank_buttons_count = await bank_buttons.count()
                log.info("FOUND [%s] BANK BUTTONS COUNT"%(bank_buttons_count))
                if bank_buttons_count == 0:
                    bank_counter = 1
                else:
                    bank_counter = bank_buttons_count
                for k in range(bank_counter):
                    if k >= 1:
                        log.info("BANK COUNTER [%s] >=1, SKIP NEXT CHECK"%k)
                        continue
                    if bank_buttons_count != 0:
                        bank_btn = bank_buttons.nth(k)
                        await bank_btn.click()
                        # with bank name get from image
                        try:
                            image_link = await bank_btn.locator('img').get_attribute("src")
                            log.info(f"BANK IMAGE LINK - [{image_link}]")
                            bank_name = os.path.splitext(os.path.basename(unquote(image_link.split("?")[0])))[0]
                            bank_name = bank_name.replace("_", "-")
                            log.info(f"BANK NAME - [{bank_name}]")
                        # with bank name get from text
                        except Exception as e:
                            bank_name = await bank_btn.inner_text()
                            log.info(f"BANK NAME - [{bank_name}]")
                    else:
                        bank_btn = None
                        bank_name = ''
                        pass
                    # input the minimum deposit amount
                    money_input_range = page.locator('div.deposit_channel_title_text.flex.justify-between')
                    await money_input_range.wait_for(state="attached", timeout=3000)
                    money_input_range_text = (await money_input_range.inner_text())
                    log.info("MONEY INPUT RANGE AMOUNT: [%s]"%money_input_range_text)
                    matches = re.findall(r"₹\s*([\d,]+)", money_input_range_text)
                    if matches:
                        min_amount = matches[0]            
                        min_amount = min_amount.replace(",", "")  # remove comma if any
                        log.info("MINIMUM INPUT AMOUNT TO TEST: [%s]"%min_amount)
                    else:
                        log.warning("NO MINIMUM DEPOSIT AMOUNT INPUT")
                    try:
                        await page.get_by_placeholder("0").click()
                        await page.get_by_placeholder("0").fill("%s"%min_amount)
                        log.info("PERFORM PAYMENT GATEWAY TEST - MIN AMOUNT [%s] ARE KEYED IN"%min_amount)
                    except:
                        raise Exception("PERFORM PAYMENT GATEWAY TEST - MIN AMOUNT [%s] ARE NOT KEYED IN"%min_amount)
                    # no need check url jump anymore, template has changed since 1/13/2026
                    #url_jump, payment_page_failed_load = await url_jump_check(page,old_url,deposit_method,deposit_channel,bank_name,bank_btn,min_amount,telegram_message)
                    try:
                        deposit_submit_button = page.locator('button.btn_deposits.uppercase:has-text("Deposit")')
                        await deposit_submit_button.wait_for(state="visible", timeout=60000)
                        await deposit_submit_button.click()
                        log.info("PERFORM PAYMENT GATEWAY TEST - เติมเงิน/DEPOSIT TOP UP BUTTON ARE CLICKED")
                    except:
                        raise Exception("PERFORM PAYMENT GATEWAY TEST - เติมเงิน/DEPOSIT TOP UP BUTTON ARE FAILED TO CLICK")
                    # check deposit confirmation window is it got pop up
                    confirmation_deposit_button_count = await confirmation_deposit_success_check(page)
                    if confirmation_deposit_button_count != 0:
                        log.info("PERFORM PAYMENT GATEWAY TEST - CONFIRMATION DEPOSIT POP UP FOUND !!!")
                        telegram_message[f"{deposit_channel}-{bank_name}_{deposit_method}"] = [f"deposit success_{date_time("Asia/Bangkok")}"]
                        failed_reason[f"{deposit_channel}-{bank_name}_{deposit_method}"] = [f"-"]
                        await page.screenshot(path="J8I_%s_%s-%s_Payment_Page.png"%(deposit_method,deposit_channel,bank_name),timeout=30000)
                        await reenter_deposit_page(page,old_url,deposit_method,deposit_channel,bank_name,bank_btn,min_amount,recheck=0)
                        continue
                    else:
                        await page.screenshot(path="J8I_%s_%s-%s_Payment_Page.png"%(deposit_method,deposit_channel,bank_name),timeout=30000)
                        pass
                    # EXTRA MANUAL BANK CHECK ##
                    try:
                       manual_bank_text_count = await page.locator('div.deposit_information_content_labels').count()
                       for count in range(manual_bank_text_count):
                           manual_bank_text = await page.locator('div.deposit_information_content_labels').nth(count).inner_text(timeout=3000)
                           log.info("MANUAL BANK TEXT:%s"%manual_bank_text)
                           if "Bank Name" in manual_bank_text:
                               await reenter_deposit_page(page,old_url,deposit_method,deposit_channel,bank_name,bank_btn,min_amount,recheck=0)
                               log.info("MANUAL BANK TEXT FOUND:%s"%manual_bank_text)
                               manual_bank = True
                               break
                           elif "ชื่อธนาคาร" in manual_bank_text:
                               await reenter_deposit_page(page,old_url,deposit_method,deposit_channel,bank_name,bank_btn,min_amount,recheck=0)
                               log.info("MANUAL BANK TEXT FOUND:%s"%manual_bank_text)
                               manual_bank = True
                               break
                       if manual_bank == True:
                           log.info(f"DEPOSIT CHANNEL [{deposit_channel}] IS NOT PAYMENT GATEWAY, SKIPPING CHECK...")
                           continue
                       else:
                           log.info("NO MANUAL BANK TEXT FOUND")
                           pass
                    except Exception as e:
                       log.info("NO MANUAL BANK TEXT FOUND:%s"%e)
                       pass
                    ## EXTRA MANUAL BANK CHECK ##
                    #if url_jump and payment_page_failed_load == False:
                    #    telegram_message[f"{deposit_channel}-{bank_name}_{deposit_method}"] = [f"deposit success_{date_time("Asia/Bangkok")}"]
                    #    failed_reason[f"{deposit_channel}-{bank_name}_{deposit_method}"] = [f"-"]
                    #    log.info("SCRIPT STATUS: URL JUMP SUCCESS, PAYMENT PAGE SUCCESS LOAD")
                    #    await reenter_deposit_page(page,old_url,deposit_method,deposit_channel,bank_name,bank_btn,min_amount,recheck=0)
                    #    continue
                    #elif url_jump and payment_page_failed_load == True:
                    #    telegram_message[f"{deposit_channel}-{bank_name}_{deposit_method}"] = [f"deposit failed_{date_time("Asia/Bangkok")}"]
                    #    failed_reason[f"{deposit_channel}-{bank_name}_{deposit_method}"] = [f"payment page failed load"]
                    #    log.info("SCRIPT STATUS: URL JUMP SUCCESS, PAYMENT PAGE FAILED LOAD")
                    #    await reenter_deposit_page(page,old_url,deposit_method,deposit_channel,bank_name,bank_btn,min_amount,recheck=0)
                    #    continue
                    #else:
                    #    pass
                    payment_iframe_count, error_text = await payment_iframe_check(page)
                    if error_text == 1:
                        telegram_message[f"{deposit_channel}-{bank_name}_{deposit_method}"] = [f"deposit failed_{date_time("Asia/Bangkok")}"]
                        failed_reason[f"{deposit_channel}-{bank_name}_{deposit_method}"] = [f"GOT ERROR TEXT"]
                        await reenter_deposit_page(page,old_url,deposit_method,deposit_channel,bank_name,bank_btn,min_amount,recheck=0)
                        continue
                    elif payment_iframe_count != 0:
                        telegram_message[f"{deposit_channel}-{bank_name}_{deposit_method}"] = [f"deposit success_{date_time("Asia/Bangkok")}"]
                        failed_reason[f"{deposit_channel}-{bank_name}_{deposit_method}"] = [f"-"]
                        await reenter_deposit_page(page,old_url,deposit_method,deposit_channel,bank_name,bank_btn,min_amount,recheck=0)
                        continue
                    else:
                        pass
                    toast_exist, toast_failed_text = await check_toast(page,deposit_method,deposit_channel,bank_name)
                    if toast_exist:
                        telegram_message[f"{deposit_channel}-{bank_name}_{deposit_method}"] = [f"deposit failed_{date_time("Asia/Bangkok")}"]
                        failed_reason[f"{deposit_channel}-{bank_name}_{deposit_method}"] = [toast_failed_text]
                        log.info("TOAST DETECTED")
                        continue
                    else:
                        telegram_message[f"{deposit_channel}-{bank_name}_{deposit_method}"] = [f"no reason found, check manually_{date_time("Asia/Bangkok")}"]
                        failed_reason[f"{deposit_channel}-{bank_name}_{deposit_method}"] = [f"unknown reason"]
                        log.warning("UNIDENTIFIED REASON")
            except Exception as e:
                log.info("SELECT BANK ERROR:%s"%e)
                

    return telegram_message, failed_reason


async def telegram_send_operation(telegram_message, failed_reason, program_complete):
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
    log.info("TELEGRAM MESSAGE: [%s]"%(telegram_message))
    log.info("FAILED REASON: [%s]"%(failed_reason))
    TOKEN = os.getenv("TOKEN")
    chat_id = os.getenv("CHAT_ID")
    tom_jerry_chat_id = os.getenv("TOM_JERRY_CHAT_ID")
    bot = Bot(token=TOKEN)
    if program_complete == True:
        for key, value_list in telegram_message.items():
            # Split key parts
            deposit_channel_method = key.split("_")
            deposit_channel = deposit_channel_method[0]
            deposit_method  = deposit_channel_method[1]
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

                if failed_deposit_channel == deposit_channel and failed_deposit_method == deposit_method:
                    failed_reason_text = value[0]
                    break
            
            log.info("METHOD: [%s], CHANNEL: [%s], STATUS: [%s], TIMESTAMP: [%s]"%(deposit_method,deposit_channel,status,timestamp))
            fail_line = f"│ **Failed Reason:** `{escape_md(failed_reason_text)}`\n" if failed_reason_text else ""
            caption = f"""[W\\_JY](tg://user?id=7431317636)
*Subject: Bot Testing Deposit Gateway*  
URL: [jw8my\\.com](https://www\\.jw8my\\.com/en\\-in)
TEAM : J8I
┌─ **Deposit Testing Result** ──────────┐
│ {status_emoji} **{status}** 
│  
│ **PaymentGateway:** `{escape_md(deposit_method) if deposit_method else "None"}`  
│ **Channel:** `{escape_md(deposit_channel) if deposit_channel else "None"}`  
└───────────────────────────┘
            
**Failed reason**  
{fail_line}

**Time Detail**  
├─ **TimeOccurred:** `{timestamp}` """ 

            tom_jerry_caption = f"""[W\\_Karman](tg://user?id=5615912046)
*Subject: Bot Testing Deposit Gateway*  
URL: [jw8my\\.com](https://www\\.jw8my\\.com/en\\-in)
TEAM : J8I
┌─ **Deposit Testing Result** ──────────┐
│ {status_emoji} **{status}** 
│  
│ **PaymentGateway:** `{escape_md(deposit_method) if deposit_method else "None"}`  
│ **Channel:** `{escape_md(deposit_channel) if deposit_channel else "None"}`  
└───────────────────────────┘
            
**Failed reason**  
{fail_line}

**Time Detail**  
├─ **TimeOccurred:** `{timestamp}` """
            files = glob.glob("*J8I_%s_%s*.png"%(deposit_method,deposit_channel))
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
                #                    chat_id=tom_jerry_chat_id,
                #                    photo=f,
                #                    caption=tom_jerry_caption,
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
                "⚠️ *J8I RETRY 3 TIMES FAILED*\n"
                "OVERALL FLOW CAN'T COMPLETE DUE TO NETWORK ISSUE OR INTERFACE CHANGES IN LOGIN PAGE OR CLOUDFLARE BLOCK\n"
                "KINDLY CONTACT PAYMENT TEAM TO CHECK IF ISSUE PERSISTS CONTINUOUSLY IN TWO HOURS"
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
    tom_jerry_chat_id = os.getenv("TOM_JERRY_CHAT_ID")
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
            method = escape_md(deposit_method)
            channel = escape_md(deposit_channel)
            # The value list contains one string like: "deposit success - 2025-11-26 14:45:24"
            value = value_list[0]
            status, timestamp = value.split("_")
            if status == 'deposit success':
                succeed_records.append((method, channel))           
            elif status == 'deposit failed':
                failed_records.append((method, channel))
            else:
                unknown_records.append((method, channel))
            succeed_block = ""
            if succeed_records:
                items = [f"│ **• Method:{m}**  \n│   ├─ Channel:{c}  \n│" for m, c in succeed_records]
                succeed_block = f"┌─ ✅ Success **Result** ────────────┐\n" + "\n".join(items) + "\n└───────────────────────────┘"
        
            failed_block = ""
            if failed_records:
                items = [f"│ **• Method:{m}**  \n│   ├─ Channel:{c}  \n│" for m, c in failed_records]
                failed_block = f"\n┌─ ❌ Failed **Result** ─────────────┐\n" + "\n".join(items) + "\n└───────────────────────────┘"
            
            unknown_block = ""
            if unknown_records:
                items = [f"│ **• Method:{m}**  \n│   ├─ Channel:{c}  \n│" for m, c in unknown_records]
                unknown_block = f"\n┌─ ❓ Failed **Result** ─────────────┐\n" + "\n".join(items) + "\n└───────────────────────────┘"
            
            summary_body = succeed_block + (failed_block if failed_block else "") + (unknown_block if unknown_block else "")
            caption = f"""*Deposit Payment Gateway Testing Result Summary *  
URL: [jw8my\\.com](https://www\\.jw8my\\.com/en\\-in)
TEAM : J8I
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
    #        await bot.send_message(chat_id=tom_jerry_chat_id, text=caption, parse_mode='MarkdownV2', disable_web_page_preview=True)
    #        log.info("SUMMARY SENT")
    #        break
    #    except TimedOut:
    #        log.warning(f"TELEGRAM TIMEOUT，RETRY {attempt + 1}/3...")
    #        await asyncio.sleep(3)
    #    except Exception as e:
    #        log.error(f"SUMMARY FAILED TO SENT: {e}")

async def clear_screenshot():
    picture_to_sent = glob.glob("*J8I*.png")
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
        elif status == 'no reason found, check manually':
            excel_data['date_time'] = date_time("Asia/Bangkok")
            excel_data[f"{deposit_method}_{deposit_channel}"] = 1
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
                if "J8I" in sheets:
                    for attempt in range(3):
                        try:
                            df = pd.read_excel(file,sheet_name="J8I")
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
                                df.to_excel(writer, sheet_name='J8I', index=False)
                        except Exception as e:
                            log.warning(f"DATA PROCESS EXCEL ERROR: {e}，RETRY {attempt + 1}/3...")
                            await asyncio.sleep(5)
                else:
                    log.info("Sheets J8I not found in file :%s"%file)
                    df = pd.DataFrame([excel_data])
                    for attempt in range(3):
                        try:
                            with pd.ExcelWriter(
                                file,
                                engine="openpyxl",
                                mode="a",
                                if_sheet_exists="replace"
                            ) as writer:
                                df.to_excel(writer, sheet_name='J8I', index=False)
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
                            df.to_excel(writer, sheet_name='J8I', index=False)
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
                telegram_message,failed_reason = await perform_payment_gateway_test(page)
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
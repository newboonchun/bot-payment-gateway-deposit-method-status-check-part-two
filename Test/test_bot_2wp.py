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
    log_path = os.path.join(log_dir, "2WP_Debug.log")
    if os.path.exists(log_path):
        try: os.remove(log_path)
        except: pass

    logger = logging.getLogger('2WPBot')
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
    logger.info("2WP PAYMENT GATEWAY TEST STARTING...")
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

async def reenter_deposit_page(page,old_url,btn,input_deposit_amount_box,submit_button,deposit_method,min_amount,recheck=1):
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
        await page.get_by_role("button", name="Deposit", exact=True).click()
        log.info("REENTER DEPOSIT PAGE - DEPOSIT BUTTON ARE CLICKED")
    except:
        log.info("REENTER DEPOSIT PAGE - DEPOSIT BUTTON ARE FAILED TO CLICK")
    #class DOM: <button type="button" class="btn btn-bonus-continue text-base font-normal !py-2 !px-10 !rounded">Continue</button>
    if recheck:
        try:
            await btn.click()
            log.info("REENTER DEPOSIT PAGE - DEPOSIT METHOD [%s] BUTTON ARE CLICKED"%deposit_method)
        except:
            raise Exception("REENTER DEPOSIT PAGE - DEPOSIT METHOD [%s] BUTTON ARE FAILED CLICKED"%deposit_method)
        try:
            await input_deposit_amount_box.click()
            await input_deposit_amount_box.fill("%s"%min_amount)
            log.info("REENTER DEPOSIT PAGE - MIN AMOUNT [%s] ARE KEYED IN"%min_amount)
        except:
            raise Exception("PERFORM PAYMENT GATEWAY TEST - MIN AMOUNT [%s] ARE NOT KEYED IN"%min_amount)
        try:
            await submit_button.wait_for(state="visible", timeout=10000)
            await submit_button.click()
            log.info("REENTER DEPOSIT PAGE - เติมเงิน/DEPOSIT TOP UP BUTTON ARE CLICKED")
        except:
            raise Exception("REENTER DEPOSIT PAGE - เติมเงิน/DEPOSIT TOP UP BUTTON ARE FAILED TO CLICK")
    else:
        pass  

async def perform_login(page):
    WEBSITE_URL = "https://www.22winth9.com/en-ph"
    for _ in range(3):
        try:
            log.info(f"LOGIN PROCESS - OPENING WEBSITE: {WEBSITE_URL}")
            await page.goto("https://www.22winth9.com/en-ph", timeout=30000, wait_until="domcontentloaded")
            await wait_for_network_stable(page, timeout=30000)
            log.info("LOGIN PROCESS - PAGE LOADED SUCCESSFULLY")
            break
        except:
            log.warning("LOGIN PROCESS - PAGE LOADED FAILED, RETRYING")
            await asyncio.sleep(2)
    else:
        raise Exception("LOGIN PROCESS - RETRY 3 TIMES....PAGE LOADED FAILED")
        
    # Login flow 2wp
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
        await page.get_by_role("button", name="close", exact=True).click()
    except:
        log.info("LOGIN PROCESS - FIRST ADVERTISEMENT DIDN'T APPEARED")
    try:
        login_button = page.locator('button.topbar_btn_1:has-text("Login")')
        await login_button.click()
        log.info("LOGIN PROCESS - LOGIN BUTTON ARE CLICKED")
    except:
        raise Exception("LOGIN PROCESS - LOGIN BUTTON ARE FAILED TO CLICKED")
    try:
        await page.get_by_role("textbox", name="Enter Your Username").click()
        await page.get_by_role("textbox", name="Enter Your Username").fill("bottestings")
        log.info("LOGIN PROCESS - USERNAME DONE KEYED")
    except:
        raise Exception("LOGIN PROCESS - USERNAME FAILED TO KEY IN")
    try:
        await page.get_by_role("textbox", name="Password").click()
        await page.get_by_role("textbox", name="Password").fill("123456")
        #<button type="submit" aria-label="Login" class="btn primary !block mx-auto uppercase !py-[8px] rounded-md w-full">Login</button>
        login_button = page.locator('button.btn.primary[aria-label="Login"]')
        await login_button.click()
        await asyncio.sleep(5)
    except:
        raise Exception("LOGIN PROCESS - PASSWORD FAILED TO FILL IN AND LOGIN SUCCESS")
    try:
        advertisement_close_button = page.locator(".icon-close.text-lg")
        await advertisement_close_button.click()
        log.info("LOGIN PROCESS - ADVERTISEMENT CLOSE BUTTON ARE CLICKED")
    except:
        log.info("LOGIN PROCESS - ADVERTISEMENT CLOSE BUTTON ARE NOT CLICKED")
    try:
        deposit_topbar_button = page.locator('a.topbar_btn_2.flex.items-center:has-text("Deposit")')
        deposit_topbar_button_count = await deposit_topbar_button.count()
        log.info("REENTER DEPOSIT PAGE: DEPOSIT TOPBAR BUTTON COUNT:%s"%deposit_topbar_button_count)
        for i in range(deposit_topbar_button_count):
            try:
                await deposit_topbar_button.nth(i).click(timeout=5000)
                log.info("REENTER DEPOSIT PAGE: DEPOSIT TOPBAR BUTTON:%s DEPOSIT TOPBAR BUTTON COUNT:%s"%(deposit_topbar_button,deposit_topbar_button_count))
            except Exception as e:
                log.info("REENTER DEPOSIT PAGE: DEPOSIT TOPBAR BUTTON:%s ERROR:%s"%(deposit_topbar_button,e))
    except Exception as e:
        raise Exception("LOGIN PROCESS - DEPOSIT TOPBAR ARE FAILED TO LOCATE:%s"%e)

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

async def url_jump_check(page,old_url,btn,input_deposit_amount_box,submit_button,deposit_method,deposit_channel,min_amount,telegram_message):
    try:
        async with page.expect_navigation(wait_until="load", timeout=30000):
            try:
                await submit_button.click()
                log.info("URL JUMP CHECK - เติมเงิน/DEPOSIT TOP UP BUTTON ARE CLICKED")
            except:
                raise Exception("URL JUMP CHECK - เติมเงิน/DEPOSIT TOP UP BUTTON ARE FAILED TO CLICK")
        
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
                await page.screenshot(path="2WP_%s_%s_Payment_Page.png"%(deposit_method,deposit_channel),timeout=30000)
                break 
            except TimeoutError:
                log.info("TIMEOUT: PAGE DID NOT REACH NETWORKIDLE WITHIN 70s")
                qr_code_count = await qr_code_check(page)
                if qr_code_count != 0:
                    log.info("NEW PAGE [%s] STILL LOADING, BUT PAY FRAME IS LOADED"%(new_url))
                    await page.screenshot(path="2WP_%s_%s_Payment_Page.png"%(deposit_method,deposit_channel),timeout=30000)
                    break
                else:
                    retry_count += 1
                    if retry_count == max_retries:
                        log.info("❌ Failed: Page did not load after 3 retries.")
                        await page.screenshot(path="2WP_%s_%s_Payment_Page.png"%(deposit_method,deposit_channel),timeout=30000)
                        url_jump = True
                        payment_page_failed_load = True
                    else:
                        log.info("RETRYING...: ATTEMPT [%s] of [%s]"%(retry_count,max_retries))
                        try:
                            await reenter_deposit_page(page,old_url,btn,input_deposit_amount_box,submit_button,deposit_method,min_amount,recheck=1)
                        except:
                            log.info("FAILED GO BACK TO OLD PAGE [%s] AND RETRY..."%(old_url))

    if new_payment_page == False:   
        await page.screenshot(path="2WP_%s_%s_Payment_Page.png"%(deposit_method,deposit_channel),timeout=30000)
        url_jump = False
        payment_page_failed_load = False

    if new_payment_page and retry_count<3:
        url_jump = True
        payment_page_failed_load = False
    
    return url_jump, payment_page_failed_load
    

async def check_toast(page,deposit_method_button,deposit_method_text,deposit_channel):
    toast_exist = False
    # deposit method click in from the scrollbar
    try:
        await deposit_method_button.click()
        log.info("CHECK TOAST - DEPOSIT METHOD [%s] BUTTON ARE CLICKED"%deposit_method_text)
    except Exception as e:
        raise Exception("CHECK TOAST - DEPOSIT METHOD [%s] BUTTON ARE FAILED CLICKED"%deposit_method_text)
    # fill in money input amount
    try:
        input_deposit_amount_box = page.locator('div.deposit_range')
        placeholder = await input_deposit_amount_box.inner_text()
        match = re.search(r'PHP\s+(\d+)', placeholder)
        min_amount = match.group(1) if match else None
        log.info("CHECK TOAST: MINIMUM INPUT AMOUNT TO TEST: [%s]"%min_amount)
        input_deposit_amount_box = page.locator("input[placeholder='PHP']")
        await input_deposit_amount_box.click()
        await input_deposit_amount_box.fill("%s"%min_amount)
    except Exception as e:
        raise Exception("CHECK TOAST - MIN AMOUNT [%s] ARE NOT KEYED IN, ERROR:%s"%(min_amount,e))
    # submit button
    # class DOM: <button type="button" class="deposit_ok_btn rounded-full text-sm md:text-base font-medium px-5 py-3 w-full md:w-[70%]">ยืนยัน</button>
    try:
        submit_button = page.locator("button.deposit_ok_btn")
        await submit_button.click()
    except Exception as e:
        raise Exception("CHECK TOAST - เติมเงิน/DEPOSIT TOP UP BUTTON ARE FAILED TO CLICK, ERROR:%s"%e)

    try:
        for _ in range(20):
            toast = page.locator('div.toast-message.text-sm')
            await toast.wait_for(state="visible", timeout=5000)
            text = (await toast.inner_text()).strip()
            if await toast.count() > 0:
                toast_exist = True
                await page.screenshot(path="2WP_%s_%s_Payment_Page.png"%(deposit_method_text,deposit_channel),timeout=30000)
                log.info("DEPOSIT METHOD:%s, DEPOSIT CHANNEL:%s GOT PROBLEM. DETAILS:[%s]"%(deposit_method_text,deposit_channel,text))
                break
            await asyncio.sleep(0.1)
    except:
            toast_exist = False
            log.info("No Toast message, no proceed to payment page, no qr code, please check what reason manually.")
    return toast_exist

async def perform_payment_gateway_test(page):
    exclude_list = ["Bank", "Government Savings Bank", "Government Saving Bank", "ธ.", "ธนาคารออมสิน", "ธนาคารกสิกรไทย", "ธนาคารไทยพาณิชย์","ธนาคาร","กสิกรไทย"]
    telegram_message = {}
    failed_reason = {}
    # deposit method menu 
    # class DOM: <div class="deposit-content my-0 md:my-4 px-4 py-4">
    #                <div id="deposit_content_nav"></div><!---->
    #                   <div class="choose-payment-method text-sm md:text-lg font-medium mb-4 md:mb-6">Choose a Payment Method</div>
    #                        <div class="deposit-meth pb-4 md:pb-5">  -----> deposit method 1
    #                        <div class="deposit-meth pb-4 md:pb-5">  -----> deposit method 2
    #                        <div class="deposit-meth pb-4 md:pb-5">  -----> deposit method 3
    
    try:
        await asyncio.sleep(5)
        old_url = page.url
        deposit_method_container = page.locator('div.deposit-content')
        await deposit_method_container.wait_for(state="attached")
        deposit_method_button = deposit_method_container.locator('div.deposit-meth')
        deposit_method_total_count = await deposit_method_button.count()
        log.info("PERFORM PAYMENT GATEWAY TEST - DEPOSIT METHOD COUNT [%s]"%deposit_method_total_count)
        if deposit_method_total_count == 0:
            raise Exception ("PERFORM PAYMENT GATEWAY TEST - DEPOSIT METHOD COUNT = 0, SCROLLBAR DIDN'T LOCATE PROBABLY")
        for i in range(deposit_method_total_count):
            # class DOM for identify manual bank/ payment gateway
            #<div class="deposit-meth pb-4 md:pb-5">
            #     <div class="flex items-center w-full gap-2 mb-2 md:mb-4">
            #         <span class="deposit_payment_method text-xs md:text-sm capitalize font-bold">Bank Express</span>

            # class DOM for deposit method text
            #<div class="deposit-meth pb-4 md:pb-5">
            #     <div class="flex flex-col items-center gap-3 w-full overflow-hidden transition-all duration-500 ease max-h-[50px]">
            #          <div class="deposit_select_bank_list">
            #                <div class="deposit_select_bank_list_left">
            #                     <div class="deposit_select_bank_list_image">
            #                            <img src="https://d2a18plfx719u2.cloudfront.net/frontend/bank_image/Bank of Ayudhya.png?v=1764310732564" alt="Krungsri"></div>
            #                     <div class="deposit_select_bank_list_line"></div>
            #                     <div class="deposit_select_bank_list_name">Krungsri</div></div>

            btn = deposit_method_button.nth(i)
            manual_bank_identifier = await btn.locator('span.deposit_payment_method').inner_text()

            inner_deposit_method = btn.locator('div.deposit_select_bank_list')
            inner_deposit_method_count = await inner_deposit_method.count()
            log.info("FOUND [%s] INNER DEPOSIT METHOD COUNT FOR DEPOSIT METHOD [%s]"%(inner_deposit_method_count,manual_bank_identifier))
            for j in range(inner_deposit_method_count):
                btn = inner_deposit_method.locator('div.deposit_select_bank_list_name').nth(j)
                deposit_method = manual_bank_identifier
                log.info("PERFORM PAYMENT GATEWAY TEST - DEPOSIT METHOD [%s]"%deposit_method)
                #if deposit_method != 'USDT-TRC20': #FOR DEBUG
                #   continue
                # manual bank check
                log.info(f"MANUAL BANK IDENTIFIER FOR DEPOSIT METHOD [{deposit_method}] IS: [***{manual_bank_identifier}***]")
                if any(manual_bank in manual_bank_identifier for manual_bank in exclude_list):
                    log.info(f"DEPOSIT METHOD [{deposit_method}] IS NOT PAYMENT GATEWAY, SKIPPING CHECK...")
                    continue
                else:
                    pass
                # deposit method click
                try:
                    await btn.click()
                    log.info("PERFORM PAYMENT GATEWAY TEST - DEPOSIT METHOD [%s] BUTTON ARE CLICKED"%deposit_method)
                    # deposit channel info
                    # input minimum deposit amount

                    # class DOM for deposit channel text
                    #<button class="w-full flex items-center justify-between bank_title_bg px-4 py-3 transition-all duration-300">
                    #     <div class="flex items-center gap-3">
                    #         <img src="https://d2a18plfx719u2.cloudfront.net/frontend/bank_image/mssthaipay.png?v=1764310732564" class="h-5 max-h-8 max-w-full md:h-9" alt="MSSTHAIPAY">
                    #              <div class="text-xs md:text-sm">MSSTHAIPAY</div>

                    # DOM for input range for deposit amount
                    #<div class="deposit-provider-entry px-4 py-6 rounded-b-xl">
                    #    <div class="relative">
                    #        <input type="number" step="any" inputmode="numeric" class="o-input !py-3 !text-xs md:!text-base o-number !bg-black" placeholder="THB 200.00 - THB 1,000,000.00">
                    try:
                        # class DOM for deposit channel text
                        #<button class="w-full flex items-center justify-between bank_title_bg px-4 py-3 transition-all duration-300">
                        #     <div class="flex items-center gap-3">
                        #         <img src="https://d2a18plfx719u2.cloudfront.net/frontend/bank_image/mssthaipay.png?v=1764310732564" class="h-5 max-h-8 max-w-full md:h-9" alt="MSSTHAIPAY">
                        #              <div class="text-xs md:text-sm">MSSTHAIPAY</div>
                        deposit_channel = await deposit_method_container.locator('button.w-full.flex.items-center.justify-between.bank_title_bg').inner_text()
                        #if deposit_channel != 'QPAY': #FOR DEBUG
                        #    continue
                        log.info("FOUND [%s] DEPOSIT CHANNEL FOR DEPOSIT METHOD [%s]"%(deposit_channel,deposit_method))
                        input_deposit_amount_box_container = page.locator('div.deposit-provider-entry')
                        input_deposit_amount_box = page.locator('div.deposit_range')
                        placeholder = await input_deposit_amount_box.inner_text()
                        match = re.search(r'PHP\s+(\d+)', placeholder)
                        if deposit_channel == 'MSSTHAIPAY':
                            min_amount = "678" if match else None
                        else:
                            min_amount = match.group(1) if match else None
                        log.info("MINIMUM INPUT AMOUNT TO TEST: [%s]"%min_amount)
                        input_deposit_amount_box = page.locator("input[placeholder='PHP']")
                        await input_deposit_amount_box.click()
                        await input_deposit_amount_box.fill("%s"%min_amount)
                        # submit button
                        # class DOM: 
                        #<div class="deposit-provider-entry px-4 py-6 rounded-b-xl">
                        #    <div class="relative">
                        #          <input type="number" step="any" inputmode="numeric" class="o-input !py-3 !text-xs md:!text-base o-number !bg-black" placeholder="THB 200.00 - THB 1,000,000.00">
                        #    <div class="mt-5 md:mt-8">
                        #          <button class="mx-auto !block btn btn-primary shining shrink-0 h-full uppercase" style="min-width: 280px;">Deposit</button></div>
                        try:
                            submit_button = input_deposit_amount_box_container.locator('button.mx-auto')
                            #await submit_button.click()
                            #await asyncio.sleep(30)
                            # Jump URL check
                            # btn = deposit method button
                            url_jump, payment_page_failed_load= await url_jump_check(page,old_url,btn,input_deposit_amount_box,submit_button,deposit_method,deposit_channel,min_amount,telegram_message)
                            if url_jump and payment_page_failed_load == False:
                                telegram_message[f"{deposit_channel}_{deposit_method}"] = [f"deposit success_{date_time("Asia/Bangkok")}"]
                                failed_reason[f"{deposit_channel}_{deposit_method}"] = [f"-"]
                                log.info("SCRIPT STATUS: URL JUMP SUCCESS, PAYMENT PAGE SUCCESS LOAD")
                                await reenter_deposit_page(page,old_url,btn,input_deposit_amount_box,submit_button,deposit_method,min_amount,recheck=0)
                                continue
                            elif url_jump and payment_page_failed_load == True:
                                telegram_message[f"{deposit_channel}_{deposit_method}"] = [f"deposit failed_{date_time("Asia/Bangkok")}"]
                                failed_reason[f"{deposit_channel}_{deposit_method}"] = [f"payment page failed load"]
                                log.info("SCRIPT STATUS: URL JUMP SUCCESS, PAYMENT PAGE FAILED LOAD")
                                await reenter_deposit_page(page,old_url,btn,input_deposit_amount_box,submit_button,deposit_method,min_amount,recheck=0)
                                continue
                            else:
                                telegram_message[f"{deposit_channel}_{deposit_method}"] = [f"deposit failed_{date_time("Asia/Bangkok")}"]
                                failed_reason[f"{deposit_channel}_{deposit_method}"] = [f"payment page failed load"]
                                log.warning("SCRIPT STATUS: URL JUMP FAILED, PAYMENT PAGE FAILED LOAD")
                                await reenter_deposit_page(page,old_url,btn,input_deposit_amount_box,submit_button,deposit_method,min_amount,recheck=0) 
                            # QR code check
                            #try:
                            #    qr_code_count = await qr_code_check(page)
                            #except Exception as e:
                            #    log.info("QR CODE CHECK ERROR: [%s]"%e)
                            #if qr_code_count != 0:
                            #    await page.screenshot(path="22FUN_%s_%s_Payment_Page.png"%(deposit_method,deposit_channel),timeout=30000)
                            #    telegram_message[f"{deposit_channel}_{deposit_method}"] = [f"deposit success_{date_time("Asia/Bangkok")}"]
                            #    await reenter_deposit_page(page,old_url,btn,input_deposit_amount_box,submit_button,deposit_method,min_amount,recheck=0)
                            #    continue
                            #else:
                            #    # toast check (no real case yet, need to verify)
                            #    # screenshot first in case there are no toast (unidentified reason)
                            #    await page.screenshot(path="22FUN_%s_%s_Payment_Page.png"%(deposit_method,deposit_channel),timeout=30000)
                            #    await reenter_deposit_page(page,old_url,btn,input_deposit_amount_box,submit_button,deposit_method,min_amount,recheck=0)
                            #    try:
                            #        toast_exist = await check_toast(page,deposit_method_button.nth(i),deposit_method,deposit_channel)
                            #    except Exception as e:
                            #        log.info("TOAST CHECK ERROR: [%s]"%e)
                            #    if toast_exist:
                            #        telegram_message[f"{deposit_channel}_{deposit_method}"] = [f"deposit failed_{date_time("Asia/Bangkok")}"]
                            #        log.info("TOAST DETECTED")
                            #        await reenter_deposit_page(page,old_url,btn,input_deposit_amount_box,submit_button,deposit_method,min_amount,recheck=0)
                            #        continue
                            #    else:
                            #        telegram_message[f"{deposit_channel}_{deposit_method}"] = [f"no reason found, check manually_{date_time("Asia/Bangkok")}"]
                            #        log.warning("UNIDENTIFIED REASON")
                            #        await reenter_deposit_page(page,old_url,btn,input_deposit_amount_box,submit_button,deposit_method,min_amount,recheck=0)   
                        except:
                            raise Exception ("SUBMIT BUTTON FAILED TO CLICK")  
                    except Exception as e:
                        log.info("DEPOSIT CHANNEL/MINIMUM INPUT AMPONT NOT FOUND:%s"%(e))
                except Exception as e:
                    raise Exception("PERFORM PAYMENT GATEWAY TEST - DEPOSIT METHOD [%s] BUTTON ARE FAILED CLICKED:%s"%(deposit_method,e))
                await asyncio.sleep(5)
    except Exception as e:
        log.info("PERFORM PAYMENT GATEWAY TEST - DEPOSIT METHOD SCROLLER/CONATINER CANNOT LOCATE:%s"%e)
    return telegram_message,failed_reason

async def telegram_send_operation(telegram_message,failed_reason,program_complete):
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
    log.info("TELEGRAM MESSAGE: [%s]"%(telegram_message))
    log.info("FAILED REASON: [%s]"%(failed_reason))
    TOKEN = os.getenv("TOKEN")
    chat_id = os.getenv("CHAT_ID")
    aris_chat_id = os.getenv("ARIS_CHAT_ID")
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
            caption = f"""[W\\_Hao](tg://user?id=8416452734), [W\\_MC](tg://user?id=7629175195)
*Subject: Bot Testing Deposit Gateway*  
URL: [22winth9\\.com](https://www\\.22winth9\\.com/en\\-pb)
TEAM : 2WP
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
            
#            aris_caption = f"""[Janeny](tg://user?id=7354557269), [Augus](tg://user?id=6886607680), [Amin22FT](tg://user?id=7071925759), [Cs22fun](tg://user?id=6886607680), [wadee](tg://user?id=7071925759), [joyjug](tg://user?id=1883477695)
#*Subject: Bot Testing Deposit Gateway*  
#URL: [22winth9\\.com](https://www\\.22winth9\\.com/en\\-pb)
#TEAM : 2WP
#┌─ **Deposit Testing Result** ──────────┐
#│ {status_emoji} **{status}** 
#│  
#│ **PaymentGateway:** `{escape_md(deposit_method) if deposit_method else "None"}`  
#│ **Channel:** `{escape_md(deposit_channel) if deposit_channel else "None"}`  
#└───────────────────────────┘
#            
#**Failed reason**  
#{fail_line}
#
#**Time Detail**  
#├─ **TimeOccurred:** `{timestamp}` """
            files = glob.glob("*2WP_%s_%s*.png"%(deposit_method,deposit_channel))
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
                #                    chat_id=aris_chat_id,
                #                    photo=f,
                #                    caption=aris_caption,
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
                "⚠️ *2WP RETRY 3 TIMES FAILED*\n"
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
    aris_chat_id = os.getenv("ARIS_CHAT_ID")
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
                unknown_block = f"\n┌─ ❓ Unknown **Result** ─────────────┐\n" + "\n".join(items) + "\n└───────────────────────────┘"
            
            summary_body = succeed_block + (failed_block if failed_block else "") + (unknown_block if unknown_block else "")
            caption = f"""*Deposit Payment Gateway Testing Result Summary *  
URL: [22winth9\\.com](https://www\\.22winth9\\.com/en\\-pb)
TEAM : 2WP
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
    #        await bot.send_message(chat_id=aris_chat_id, text=caption, parse_mode='MarkdownV2', disable_web_page_preview=True)
    #        log.info("SUMMARY SENT")
    #        break
    #    except TimedOut:
    #        log.warning(f"TELEGRAM TIMEOUT，RETRY {attempt + 1}/3...")
    #        await asyncio.sleep(3)
    #    except Exception as e:
    #        log.error(f"SUMMARY FAILED TO SENT: {e}")

async def clear_screenshot():
    picture_to_sent = glob.glob("*2WP*.png")
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
                if "2WP" in sheets:
                    for attempt in range(3):
                        try:
                            df = pd.read_excel(file,sheet_name="2WP")
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
                                df.to_excel(writer, sheet_name='2WP', index=False)
                        except Exception as e:
                            log.warning(f"DATA PROCESS EXCEL ERROR: {e}，RETRY {attempt + 1}/3...")
                            await asyncio.sleep(5)
                else:
                    log.info("Sheets 2WP not found in file :%s"%file)
                    df = pd.DataFrame([excel_data])
                    for attempt in range(3):
                        try:
                            with pd.ExcelWriter(
                                file,
                                engine="openpyxl",
                                mode="a",
                                if_sheet_exists="replace"
                            ) as writer:
                                df.to_excel(writer, sheet_name='2WP', index=False)
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
                            df.to_excel(writer, sheet_name='2WP', index=False)
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
                telegram_message, failed_reason = await perform_payment_gateway_test(page)
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
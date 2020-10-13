from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.common.exceptions import NoSuchElementException
from selenium.common.exceptions import NoAlertPresentException
from selenium.common.exceptions import WebDriverException
from selenium.common.exceptions import UnexpectedAlertPresentException
from selenium.webdriver.common.alert import Alert
from selenium.webdriver.common.by import By
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.firefox.firefox_profile import FirefoxProfile
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from ua_parser import user_agent_parser
from HTMLParser import HTMLParser
from TestConfig import TestSettings
import unittest, platform, re, json, urllib2, socket, os
import time

class TestResults():
    def __init__(self, environment, app):
        try:
            self.ip = socket.gethostbyname(app["URL"])
        except:
            self.ip = 'unknown'
        try:
            self.server = socket.gethostbyaddr(self.ip)[0]
        except:
            self.server='unknown'
        self.results = {
            "Time": str(time.strftime('%Y-%m-%d %H:%M:%S')),
            "application": {
                "item_id": app["ITEM_ID"],
                "item_name": app.get("ITEM_NAME", app["ITEM_ID"]),
                "ip": self.ip,
                "server": self.server.lower(),
                "url": app["URL"]
            },
            "results": {
                "duration": 0,
                "tests_count": len([d for d in app['TESTS'] if int(d.get('enabled',0)) == 1])
            },
            "tests": []
        }
        self.results['environment'] = environment
        self.count = 0
    def TestStart(self):
        self.transaction_start = time.time()
    def TestFinish(self):
        self.transaction_end = time.time()
        self.duration = round(self.transaction_end - self.transaction_start, 2)
        self.results['results']['duration'] = round(self.results['results']['duration'] + self.duration, 2)
    def TestResults(self, info):
        self.results['results']['status'] = info['status']
        if 'error' in info: self.results['results']['error'] = info['error']
        info['duration'] = self.duration
        self.results['tests'].append(info)
    def TestSkipped(self):
        info = {'status': 'Skipped'}
        self.results['tests'].append(info)
    def WriteResults(self):
        self.results['results']['tests_run'] = len(self.results['tests'])


class MLStripper(HTMLParser):
    def __init__(self):
        self.reset()
        self.fed = []
    def handle_data(self, d):
        self.fed.append(d)
    def get_data(self):
        return ''.join(self.fed)


def strip_tags(html):
    s = MLStripper()
    s.feed(html)
    error = s.get_data()
    error = re.sub(r'(?:\n)+', ' ', error)
    return re.sub(r'\s+', ' ', error)


def getEnvironmentDetails(driver):
    # GET BROWSER INFO
    ua_string = driver.execute_script("return navigator.userAgent")
    ua = user_agent_parser.Parse(ua_string)
    # GET NODE INFO
    try:
        session = driver.session_id
        url = "{0}://{1}:{2}/grid/api/testsession?session={3}".format(TestSettings.get('SeleniumHub', 'protocol'), TestSettings.get('SeleniumHub', 'host'), TestSettings.get('SeleniumHub', 'port'), session)
        req = urllib2.Request(url)
        req.add_header("Content-Type", "application/json")
        response = urllib2.urlopen(req)
        node = json.loads(response.read())
        response.close()
        ip = re.search('\/\/([^\:]+)\:', node.get('proxyId')).group(1)
        try:
            host = socket.gethostbyaddr(ip)[0]
        except:
            host = ip
    except:
        host = "unknown"
        ip = "unknown"
    environment = {
        'browser': {
            "name": ua['user_agent']['family'],
            "version": "{0}.{1}.{2}".format(ua['user_agent']['major'], ua['user_agent']['minor'], ua['user_agent']['patch']) if ua['user_agent']['patch'] else "{0}.{1}".format(ua['user_agent']['major'], ua['user_agent']['minor'])
        },
        'host': {
            'name': host,
            'ip': ip,
            'os': "{0} {1}.{2}".format(ua['os']['family'], ua['os']['major'], ua['os']['minor']) if ua['os']['minor'] else "{0} {1}".format(ua['os']['family'], ua['os']['major'])
        }
    }
    return environment


def getScreenshot(browser):
    try:
        img_str = browser.get_screenshot_as_base64()
    except:
        img_str = "Screenshot capture failed"
    return img_str


def TestGenerator(app, screenshot_always=False):
    def applicationTest(self):
        
        if self.browsers.get(app.get('BROWSER')) == None:
            self.browsers[app['BROWSER']] = launchBrowser(app['BROWSER'])
            self.browser_details[app['BROWSER']] = getEnvironmentDetails(self.browsers[app['BROWSER']])
        
        self.driver = self.browsers[app['BROWSER']]

        self.test = TestResults(self.browser_details[app['BROWSER']], app)

        testCommands = {
            'Open': self.go_to_url,
            'Verify title': self.check_title,
            'Find': self.find_element,
            'Click': self.click_element,
            'Type': self.enter_text,
            'Health': self.health_check
        }

        for step in app["TESTS"]:
            if int(step.get('enabled',0)) == 1:
                try:
                    # Clear performance logs before each new test
                    if app['BROWSER'] in ["Chrome","ChromeIncognito"] and step["command"] in ["Open", "Click"]:
                        while len(self.driver.get_log('performance')) > 0:
                            pass
                    # Launch appropriate command from the testCommands library
                    self.assertEquals(testCommands[step["command"]](**step), True)
                except:
                    break
            else:
                self.test.TestSkipped()
        
        if screenshot_always or self.test.results['results']['status'] == "Failed":
            if screenshot_always:
                self.test.results['screenshot'] = getScreenshot(self.driver)
            else:
                self.test.results['results']['screenshot'] = getScreenshot(self.driver)
            if app['BROWSER'] in ["Chrome","ChromeIncognito"]:
                logs = self.driver.get_log('performance')
                self.test.results['results']['logs'] = [json.loads(log['message'])['message'] for log in logs if json.loads(log['message'])['message']['method'].startswith('Network')]

        self.test.WriteResults()
    return applicationTest

def launchBrowser(browser):
    # Get Selenium Hub and Browser settings from settings.conf
    hub = "{0}://{1}:{2}/wd/hub".format(TestSettings.get('SeleniumHub', 'protocol'), TestSettings.get('SeleniumHub', 'host'), TestSettings.get('SeleniumHub', 'port'))
    sitelist = TestSettings.get("BrowserSettings", "sitelist")

    if browser in ["Chrome","ChromeIncognito"]:
        # START CHROME BROWSER
        options = webdriver.ChromeOptions()
        
        options.add_argument("auth-server-whitelist={0}".format(sitelist))
        options.add_argument("auth-negotiate-delegatewhitelist={0}".format(sitelist))
        options.add_argument("auth-schemes=digest,ntlm,negotiate")
        options.add_argument("--disable-http2")
        if browser == "ChromeIncognito":
            options.add_argument("--incognito")
        
        capabilities = options.to_capabilities()
        capabilities['goog:loggingPrefs'] = { 'performance':'ALL' }
        
        driver = webdriver.Remote(hub, capabilities)
        driver.maximize_window()
        driver.set_page_load_timeout(30)
    else:
        # START FIREFOX BROWSER
        # CREATE PROFILE
        profile = FirefoxProfile()
        # ENABLE KERBEROS
        profile.set_preference("network.negotiate-auth.trusted-uris", sitelist)
        profile.set_preference("network.negotiate-auth.delegation-uris", sitelist)
        profile.set_preference("network.automatic-ntlm-auth.trusted-uris", sitelist)
        # DISABLE CACHE
        profile.set_preference("browser.cache.disk.enable", False)
        profile.set_preference("browser.cache.memory.enable", False)
        profile.set_preference("browser.cache.offline.enable", False)
        profile.set_preference("network.http.use-cache", False)
        # DISABLE FLASH
        profile.set_preference("plugin.state.flash", 0)
        # PREVENTS FAILING ON SELF-SIGNED CERTIFICATES
        capabilities = DesiredCapabilities.FIREFOX.copy()

        driver = webdriver.Remote(hub, capabilities, browser_profile=profile)
        driver.maximize_window()
        driver.set_page_load_timeout(30)

    return driver

class TestSuite(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        self.browsers = {}
        self.browser_details = {}

    @classmethod
    def tearDownClass(self):
        time.sleep(3)
        for browser, driver in self.browsers.iteritems():
            driver.quit()

    def check_title(self, **info):
        info["description"] = "{0} {1} \"{2}\"".format(info["command"], info["assert"], info["title_expected"])
        self.test.TestStart()
        self.wait_for_page_title(info["title_expected"])
        info["title_loaded"] = self.driver.title.encode('utf-8')
        try:
            if info["assert"] == "equals": self.assertEquals(info["title_loaded"].lower(), info["title_expected"].lower())
            else: self.assertRegexpMatches(info["title_loaded"].lower(), info["title_expected"].lower())
            
            self.test.TestFinish()
            info['status'] = "Passed"
            self.test.TestResults(info)
            return True
        except AssertionError:
            self.test.TestFinish()
            info['status'] = "Failed"
            info['error'] = 'Unexpected title: "{0}" instead of "{1}"'.format(info["title_loaded"], info["title_expected"])
            self.test.TestResults(info)
            return False

    def get_element(self, name, value):
        byCommand = {
            "id": By.ID,
            "xpath": By.XPATH,
            "link_text": By.LINK_TEXT,
            "partial_link_text": By.PARTIAL_LINK_TEXT,
            "name": By.NAME,
            "tag_name": By.TAG_NAME,
            "class_name": By.CLASS_NAME,
            "css_selector": By.CSS_SELECTOR
        }
        return WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((byCommand.get(name), value)))

    def find_element(self, **info):
        info["description"] = "{0} element with {1} \"{2}\"".format(info["command"], info["element_name"], info["element_value"])
        self.test.TestStart()
        try:
            self.current_element = self.get_element(info["element_name"], info["element_value"])
            self.test.TestFinish()
            info['status'] = "Passed"
            self.test.TestResults(info)
            return True
        except:
            self.test.TestFinish()
            info['status'] = "Failed"
            info['error'] = "Unable to locate element: {0}=\"{1}\"".format(info["element_name"], info["element_value"])
            self.test.TestResults(info)
            return False

    def click_element(self, **info):
        try:
            info["description"] = "{0} element with {1} \"{2}\"".format(info["command"], info["element_name"], info["element_value"])
            self.test.TestStart()
            self.current_element = self.get_element(info["element_name"], info["element_value"])
            self.current_element.click()
            self.test.TestFinish()
            info['status'] = "Passed"
            self.test.TestResults(info)
            return True
        except TimeoutException:
            self.test.TestFinish()
            info['status'] = "Failed"
            info['error'] = "Timeout waiting for element with {0}=\"{1}\".".format(info["element_name"], info["element_value"])
            self.test.TestResults(info)
            return False
        except NoSuchElementException:
            self.test.TestFinish()
            info['status'] = "Failed"
            info['error'] = "Unable to locate element with {0}=\"{1}\".".format(info["element_name"], info["element_value"])
            self.test.TestResults(info)
            return False
        except:
            self.test.TestFinish()
            info['status'] = "Failed"
            info['error'] = "Unknown error occured"
            self.test.TestResults(info)
            return False

    def enter_text(self, **info):
        try:
            info['description'] = "Enter text \"{0}\"".format(info.get('text'))
            self.test.TestStart()
            self.current_element.click()
            self.current_element.send_keys(info['text'])
            self.assertEqual(self.current_element.get_attribute('value'),info['text'])
            self.test.TestFinish()
            info['status'] = "Passed"
            self.test.TestResults(info)
            return True
        except:
            self.test.TestFinish()
            info['status'] = "Failed"
            info['error'] = "Text entry was not successful"
            self.test.TestResults(info)
            return False

    def health_check(self, **info):
        try:
            info['description'] = "Evaluate Health Check results"
            self.test.TestStart()
            healthcheck = json.loads(strip_tags(self.driver.page_source).strip())
            failed = False
            key = info.get('key') if info.get('key') != None and len(info.get('key')) > 0 else "isHealthy"
            for category in healthcheck:
                if type(healthcheck[category]) == list:
                    for dependency in healthcheck[category]:
                        if type(dependency) == dict:
                            result = dependency.get(key)
                            if result == None:
                                failed = {"error": "The provided key was not found in the Health Check results"}
                            elif str(result).lower() not in ["true", "1"]:
                                failed = dependency
            self.assertEqual(failed, False)
            self.test.TestFinish()
            info['status'] = "Passed"
            self.test.TestResults(info)
            return True
        except AssertionError:
            self.test.TestFinish()
            info['status'] = "Failed"
            info['error'] = 'A dependency has failed the Health Check'
            info.update(failed)
            self.test.TestResults(info)
            return False
        except:
            self.test.TestFinish()
            info['status'] = "Failed"
            info['error'] = "Failed to parse Health Check results"
            self.test.TestResults(info)
            return false

    def go_to_url(self, **info):
        info['description'] = "Go to url {0}".format(info["url"])
        result = True
        neterror = False
        access_error = 0
        toast_error = 0
        try:
            self.test.TestStart()
            self.driver.get(info["url"])
            try:
                page_title = self.driver.title.encode('utf-8').lower()
            # If grabbing the title fails because of an existing alert, dismiss it
            except UnexpectedAlertPresentException:
                try:
                    while True:
                        time.sleep(1)
                        Alert(self.driver).dismiss()
                except NoAlertPresentException:
                    page_title = self.driver.title.encode('utf-8').lower()
                    if len(page_title) == 0:
                        access_error = strip_tags(self.driver.page_source).strip()

            info['url_loaded'] = self.driver.current_url
            self.test.TestFinish()

            # Look for access errors after dismissing a prompt
            self.assertEqual(access_error,0)

            #  Look for the presence of custom Toast error element being displayed on the page
            try:
                toast_message = self.driver.find_element_by_class_name("toast-message")
                toast_error = toast_message.get_attribute('innerHTML')
            except:
                toast_error = 0

            #  Check for PNNL Toast error
            self.assertEqual(toast_error,0)

            #  Check for an Apology page redirect
            self.assertNotRegexpMatches(self.driver.current_url, r'apology|outage', 1)
            
            #  Check for errors in the page title
            self.assertNotRegexpMatches(page_title, r'\D?[45]\d\d\D', 2)
            self.assertNotRegexpMatches(page_title, r'problem|failed|not\savailable|error|denied', 3)

            #  Check for neterror class on body in Chrome
            if self.test.results['environment']['browser']['name'] in ["Chrome","ChromeIncognito"]:
                try:
                    neterror = self.driver.find_element_by_xpath('/html/body[@class="neterror"]//div[@id="main-message"]').get_attribute('innerText')
                except:
                    neterror = False

            self.assertEqual(neterror, False)

            #  If no page title, check for blank page
            self.assertNotEqual(len(page_title),0)

            #  Success
            info['status'] = "Passed"
            self.test.TestResults(info)
        # Handle assertion errors
        except AssertionError as error:
            result = False
            errornum = error[0][0]
            try:
                # Check for access denied errors
                if 'page_title' in locals():
                    self.assertNotRegexpMatches(page_title, r'40[13]\D')
                    self.assertNotIn('denied',page_title)

                if access_error:
                    info['status'] = 'Warning'
                    info['error'] = access_error
                    self.test.TestResults(info)

                # Handle "Toast" errors
                elif toast_error:
                    info['status'] = 'Failed'
                    info['error'] = toast_error
                    self.test.TestResults(info)

                # Handle Chrome neterror
                elif neterror:
                    info['status'] = 'Failed'
                    info['error'] = neterror
                    self.test.TestResults(info)

                # Handle blank title
                elif errornum == "0":
                    error = strip_tags(self.driver.page_source).strip()
                    if len(error) == 0:
                        error = "Blank Page Loaded"
                    try:
                        self.assertTrue(len(error) < 1000) # Likely page loaded but page title wasn't caught in time
                        self.assertRegexpMatches(error.lower(), r'[45]\d{2}\D|error|^blank') # Check for status codes or errors in the source
                        info['status'] = 'Failed'
                        info['error'] = error
                        self.test.TestResults(info)
                    except:
                        # No page title, but source looks ok
                        result = True
                        info['status'] = "Passed"
                        self.test.TestResults(info)

                # Handle redirect to apology page
                elif errornum == "1":
                    try:
                        heading = self.driver.find_element_by_tag_name('h1').get_attribute('innerHTML')
                        self.assertRegexpMatches(heading, r'^Planned')
                        info['status'] = 'Warning'
                        info['error'] = error
                        self.test.TestResults(info)
                    except AssertionError:
                        info['status'] = 'Failed'
                        info['error'] = page_title
                        self.test.TestResults(info)

                # Handle errors found in the title
                elif errornum.isdigit():
                    info['status'] = 'Failed'
                    info['error'] = page_title
                    self.test.TestResults(info)

                #  Handle unknown errors
                else:
                    error = 'An unknown error occured: {0}'.format(page_title)
                    info['status'] = 'Failed'
                    info['error'] = error
                    self.test.TestResults(info)
            #  Handle access denied errors as a warning
            except AssertionError:
                info['status'] = 'Warning'
                info['error'] = page_title
                self.test.TestResults(info)
        #  Handle page timeout
        except TimeoutException:
            result = False
            error = 'Timeout: Page did not load within 30 seconds'
            #  Check for the presence of an alert, likely caused by login prompt
            try:
                alert = False
                while True:
                    Alert(self.driver).dismiss()
                    alert = True
            except NoAlertPresentException:
                self.test.TestFinish()
                if alert == True:
                    info['status'] = 'Warning'
                    info['error'] = 'Test account denied access'
                    self.test.TestResults(info)
                else:
                    info['status'] = 'Failed'
                    info['error'] = error
                    self.test.TestResults(info)
        # Capture neterror if Firefox fails to load the page
        except WebDriverException as error:
            result = False
            self.test.TestFinish()
            info['status'] = 'Failed'
            info['error'] = self.driver.find_element_by_id("errorLongContent").get_attribute("innerText")
            self.test.TestResults(info)
        #  Handle unknown exceptions
        except:
            result = False
            self.test.TestFinish()
            info['status'] = 'Failed'
            info['error'] = 'An unknown error occured: {0}'.format(page_title)
            self.test.TestResults(info)
            raise
        finally:
            return result

    def is_alert_present(self):
        try: self.driver.switch_to_alert()
        except NoAlertPresentException as e: return False
        return True

    def close_alert_and_get_its_text(self):
        try:
            alert = self.driver.switch_to_alert()
            alert_text = alert.text
            if self.accept_next_alert:
                alert.accept()
            else:
                alert.dismiss()
            return alert_text
        finally: self.accept_next_alert = True

    def wait_for_page_load(self):
        old_page = self.driver.find_element_by_tag_name('html')
        try:
            self.wait = WebDriverWait(self.driver, 5)
            self.wait.until(
                lambda x: old_page.id != self.driver.find_element_by_tag_name('html').id
            )
            return True
        except TimeoutException:
            return False

    def wait_for_page_title(self, title):
        try:
            self.wait = WebDriverWait(self.driver, 5)
            self.wait.until(
                lambda x: title.lower() in self.driver.title.lower()
            )
            return True
        except TimeoutException:
            return False

    def tearDown(self):
        self.driver.get('about:blank')
        self.driver.delete_all_cookies()
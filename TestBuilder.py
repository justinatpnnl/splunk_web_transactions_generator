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
from .TestConfig import TestSettings
from urllib.request import urlopen
import unittest, re, json, socket
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
        self.results['results']['tests_run'] = len([test for test in self.results['tests'] if test.get('status') != "Skipped"])

def sanitize_string(text):
    # Replace line breaks and multiple spaces with a period
    text = re.sub(r'\n+|\s{2,}', '. ', text.strip())
    # Strip any accidental periods added to existing punctuation
    text = re.sub(r'(\W)\.', r'\1', text)
    return text

def getEnvironmentDetails(driver):
    # GET BROWSER INFO
    # Example Responses
    # Firefox: Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:90.0) Gecko/20100101 Firefox/90.0
    # Google: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36
    ua_string = driver.execute_script("return navigator.userAgent")
    # PARSE UA STRING
    # Example response
    # {
    #     "user_agent": {
    #         "family": "Firefox",
    #         "major": "90",
    #         "minor": "0",
    #         "patch": null
    #     },
    #     "os": {
    #         "family": "Mac OS X",
    #         "major": "10",
    #         "minor": "15",
    #         "patch": null,
    #         "patch_minor": null
    #     },
    #     "device": {
    #         "family": "Mac",
    #         "brand": "Apple",
    #         "model": "Mac"
    #     },
    #     "string": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:90.0) Gecko/20100101 Firefox/90.0"
    # }
    ua = user_agent_parser.Parse(ua_string)
    # GET NODE INFO
    try:
        # Get the Selenium Session ID
        session = driver.session_id
        # Get node information from Session ID
        # Example returned content
        # {
        #     "inactivityTime": 14,
        #     "internalKey": "7bfaf746-9736-4373-99cd-b549f194e202",
        #     "msg": "slot found !",
        #     "proxyId": "http://192.168.1.100:5555",
        #     "session": "55bb0592-cbe0-0e49-9d46-22fd53343f78",
        #     "success": true
        # }
        url = "{0}://{1}:{2}/grid/api/testsession?session={3}".format(TestSettings.get('SeleniumHub', 'protocol'), TestSettings.get('SeleniumHub', 'host'), TestSettings.get('SeleniumHub', 'port'), session)
        response = urlopen(url)
        node = json.loads(response.read())
        response.close()
        # Exctract IP from returned proxyId
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
        # DEBUG LOGS
        self.trace = []
        
        if self.browsers.get(app.get('BROWSER')) == None:
            self.browsers[app['BROWSER']] = launchBrowser(app['BROWSER'])
            self.browser_details[app['BROWSER']] = getEnvironmentDetails(self.browsers[app['BROWSER']])
        
        self.driver = self.browsers[app['BROWSER']]

        self.test = TestResults(self.browser_details[app['BROWSER']], app)

        testCommands = {
            'Open': self.go_to_url,
            'Verify title': self.check_title,
            'Find': self.find_element,
            'FindText': self.find_text_in_element,
            'Click': self.click_element,
            'Type': self.enter_text,
            'Health': self.health_check,
            'HealthCheck': self.health_check_v2,
            'Switch to': self.switch_to,
            'Wait': self.wait_for_it,
            'Get attribute': self.get_current_element_attribute
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
        
        if (screenshot_always or self.test.results['results']['status'] == "Failed") and not app.get('DEBUG', False):
            if screenshot_always:
                self.test.results['screenshot'] = getScreenshot(self.driver)
            else:
                self.test.results['results']['screenshot'] = getScreenshot(self.driver)
            if app['BROWSER'] in ["Chrome","ChromeIncognito"]:
                logs = self.driver.get_log('performance')
                self.test.results['results']['logs'] = [json.loads(log['message'])['message'] for log in logs if json.loads(log['message'])['message']['method'].startswith('Network')]

        if app.get('DEBUG', False): print(*self.trace, sep="\n")
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
        # DISABLE JSON VIEWER FOR HEALTH CHECKS
        profile.set_preference("devtools.jsonview.enabled", False)
        # PREVENTS FAILING ON SELF-SIGNED CERTIFICATES
        capabilities = DesiredCapabilities.FIREFOX.copy()

        driver = webdriver.Remote(hub, capabilities, browser_profile=profile)
        driver.maximize_window()
        driver.set_page_load_timeout(30)

    return driver

class TestSuite(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        self.current_element = False
        self.browsers = {}
        self.browser_details = {}

    @classmethod
    def tearDownClass(self):
        time.sleep(3)
        # Close any open browsers
        for driver in self.browsers.values():
            driver.quit()

    def check_title(self, **info):
        self.trace.append("Start Check Title test")
        info["description"] = "{0} {1} \"{2}\"".format(info["command"], info["assert"], info["title_expected"])
        self.test.TestStart()
        info["title_loaded"] = self.wait_for_specific_page_title(info["title_expected"])
        self.trace.append("Loaded title: {0}".format(info["title_loaded"]))
        try:
            if info["assert"] == "equals": self.assertEquals(info["title_loaded"].lower(), info["title_expected"].lower())
            else: self.assertRegexpMatches(info["title_loaded"].lower(), info["title_expected"].lower())
            
            self.test.TestFinish()
            info['status'] = "Passed"
            self.test.TestResults(info)
            self.trace.append("Check title test passed")
            return True
        except AssertionError:
            self.test.TestFinish()
            info['status'] = "Failed"
            info['error'] = 'Unexpected title: "{0}" instead of "{1}"'.format(info["title_loaded"], info["title_expected"])
            self.test.TestResults(info)
            self.trace.append(info['error'])
            return False
        except:
            self.trace.append("Unknown exception occurred")
            self.test.TestFinish()
            info['status'] = "Failed"
            info['error'] = "Unknown error occurred"
            self.test.TestResults(info)
            return False

    def get_element(self, name, value):
        self.trace.append("Get element with {0} = {1}".format(name, value))
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

    def wait_for_it(self, **info):
        info["description"] = "Wait {0} seconds".format(info["seconds"])
        self.trace.append(info.get("description"))
        self.test.TestStart()
        try:
            time.sleep(int(info.get("seconds")))
            self.test.TestFinish()
            info['status'] = "Passed"
            self.trace.append("Wait completed")
            self.test.TestResults(info)
            return True
        except:
            self.test.TestFinish()
            info['status'] = "Failed"
            self.trace.append("Wait failed")
            self.test.TestResults(info)
            return False

    def get_current_element_attribute(self, **info):
        info["description"] = "Get \"{0}\" attribute of current element".format(info.get("attribute"))
        self.trace.append(info.get("description"))
        self.test.TestStart()
        try:
            info[info.get("attribute")] = self.current_element.get_attribute(info.get("attribute"))
            self.trace.append("Attribute found")
            self.test.TestFinish()
            info['status'] = "Passed"
            self.test.TestResults(info)
            return True
        except:
            self.test.TestFinish()
            info['status'] = "Failed"
            info['error'] = "Unable to get \"{0}\" attribute of current element".format(info["attribute"])
            self.trace.append(info.get("error"))
            self.test.TestResults(info)
            return False

    def find_element(self, **info):
        info["description"] = "{0} element with {1} \"{2}\"".format(info["command"], info["element_name"], info["element_value"])
        self.trace.append(info.get("description"))
        self.test.TestStart()
        try:
            self.current_element = self.get_element(info["element_name"], info["element_value"])
            self.test.TestFinish()
            self.trace.append("find_element test passed")
            info['status'] = "Passed"
            self.test.TestResults(info)
            return True
        except TimeoutException:
            self.test.TestFinish()
            info['status'] = "Failed"
            info['error'] = "Timeout waiting for element with {0}=\"{1}\".".format(info["element_name"], info["element_value"])
            self.trace.append(info.get("error"))
            self.test.TestResults(info)
            return False
        except NoSuchElementException:
            self.test.TestFinish()
            info['status'] = "Failed"
            info['error'] = "Unable to locate element with {0}=\"{1}\".".format(info["element_name"], info["element_value"])
            self.trace.append(info.get("error"))
            self.test.TestResults(info)
            return False
        except:
            self.test.TestFinish()
            info['status'] = "Debug"
            info['error'] = "Unhandled Exception"
            self.trace.append(info.get("error"))
            self.test.TestResults(info)
            return False

    def click_element(self, **info):
        try:
            info["description"] = "{0} element with {1} \"{2}\"".format(info["command"], info["element_name"], info["element_value"])
            self.trace.append(info.get("description"))
            self.test.TestStart()
            self.current_element = self.get_element(info["element_name"], info["element_value"])
            self.trace.append("Element found")
            self.current_element.click()
            self.test.TestFinish()
            info['status'] = "Passed"
            self.trace.append(info.get("status"))
            self.test.TestResults(info)
            return True
        except TimeoutException:
            self.test.TestFinish()
            info['status'] = "Failed"
            info['error'] = "Timeout waiting for element with {0}=\"{1}\".".format(info["element_name"], info["element_value"])
            self.trace.append(info.get("error"))
            self.test.TestResults(info)
            return False
        except NoSuchElementException:
            self.test.TestFinish()
            info['status'] = "Failed"
            info['error'] = "Unable to locate element with {0}=\"{1}\".".format(info["element_name"], info["element_value"])
            self.trace.append(info.get("error"))
            self.test.TestResults(info)
            return False
        except:
            self.test.TestFinish()
            info['status'] = "Debug"
            info['error'] = "Unhandled Exception"
            self.trace.append(info.get("error"))
            self.test.TestResults(info)
            return False

    def find_text_in_element(self, **info):
        try:
            info["description"] = 'Find text "{0}"'.format(info["expected_text"])
            self.trace.append(info.get("description"))
            self.test.TestStart()
            # Check for current_element, otherwise fall back to body text
            if self.current_element: self.trace.append("Current element already available")
            else:
                self.trace.append("No current element, select body")
                self.current_element = self.get_element('xpath', '//*')
            self.trace.append("Element found")
            text = self.current_element.text
            self.trace.append("Element text: {0}".format(text))
            self.trace.append("Expected text: {0}".format(info['expected_text']))
            # Compare results to expected
            if info["assert"] == "equals": self.assertEquals(text.lower(), info["expected_text"].lower())
            else: self.assertRegexpMatches(text.lower(), info["expected_text"].lower())
            self.test.TestFinish()
            info['status'] = "Passed"
            self.trace.append(info.get("status"))
            self.test.TestResults(info)
            return True
        except AssertionError as e:
            self.trace.append("Assertion error: {0}".format(e))
            self.test.TestFinish()
            info['status'] = "Failed"
            info['error'] = 'Unexpected text: "{0}" instead of "{1}"'.format(text, info["expected_text"]) if info['assert'] == "equals" else 'Unexpected text: "{0}" not found in "{1}"'.format(info["expected_text"], text)
            self.test.TestResults(info)
            self.trace.append(info['error'])
            return False
        except TimeoutException:
            self.test.TestFinish()
            info['status'] = "Failed"
            info['error'] = "Timeout waiting for body text using xpath"
            self.trace.append(info.get("error"))
            self.test.TestResults(info)
            return False
        except NoSuchElementException:
            self.test.TestFinish()
            info['status'] = "Failed"
            info['error'] = "Unable to locate body element using xpath"
            self.trace.append(info.get("error"))
            self.test.TestResults(info)
            return False
        except:
            self.test.TestFinish()
            info['status'] = "Debug"
            info['error'] = "Unhandled Exception"
            self.trace.append(info.get("error"))
            self.test.TestResults(info)
            return False

    def enter_text(self, **info):
        try:
            info['description'] = "Enter text \"{0}\"".format(info.get('text'))
            self.trace.append(info.get("description"))
            self.test.TestStart()
            self.current_element.click()
            self.trace.append("Element selected")
            self.current_element.send_keys(info['text'])
            self.trace.append("Text entered")
            self.assertEqual(self.current_element.get_attribute('value'),info['text'])
            self.test.TestFinish()
            info['status'] = "Passed"
            self.trace.append(info.get("status"))
            self.test.TestResults(info)
            return True
        except:
            self.test.TestFinish()
            info['status'] = "Failed"
            info['error'] = "Text entry was not successful"
            self.trace.append(info.get("error"))
            self.test.TestResults(info)
            return False

    def switch_to(self, **info):
        info["description"] = "{0} {1} with name \"{2}\"".format(info["command"], info["element_name"], info["element_value"])
        self.trace.append(info.get("description"))
        self.test.TestStart()
        try:
            if info.get("element_name") == "Frame":
                self.driver.switch_to.default_content()
                frame = self.get_element("name", info.get("element_value"))
                self.driver.switch_to.frame(frame)
            self.test.TestFinish()
            info['status'] = "Passed"
            self.trace.append(info.get("status"))
            self.test.TestResults(info)
            return True
        except:
            self.test.TestFinish()
            info['status'] = "Failed"
            info['error'] = "Unable to locate element: {0}=\"{1}\"".format(info["element_name"], info["element_value"])
            self.trace.append(info.get("error"))
            self.test.TestResults(info)
            return False

    def health_check(self, **info):
        try:
            self.trace.append("Begin health check, capture page source")
            info['description'] = "Evaluate Health Check results"
            self.test.TestStart()
            source = sanitize_string(self.driver.find_element_by_xpath('//*').text)
            self.trace.append("Page source: {0}".format(source))
            self.trace.append("Attempt converting source to JSON")
            try:
                healthcheck = json.loads(source)
                self.trace.append("Successfully converted source to JSON")
            except:
                healthcheck = False
            self.assertIsInstance(healthcheck, dict, "source_conversion_error")
            failed = False
            key = info.get('key') if info.get('key') != None and len(info.get('key')) > 0 else "isHealthy"
            for category in healthcheck:
                if type(healthcheck[category]) == list:
                    for dependency in healthcheck[category]:
                        if type(dependency) == dict:
                            result = dependency.get(key)
                            if result == None:
                                failed = {"error": 'The key "{0}" was not found in the Health Check output'.format(key)}
                            elif str(result).lower() not in ["true", "1"]:
                                failed = dependency
            self.assertEqual(failed, False, "health_check_failed")
            self.test.TestFinish()
            info['status'] = "Passed"
            self.trace.append("Health check passed")
            self.test.TestResults(info)
            return True
        except AssertionError as e:
            msg_list = str(e).split(" : ")
            msg = msg_list if len(msg_list) == 1 else msg_list[1]
            self.trace.append("Assertion error: {0}".format(msg))
            self.test.TestFinish()
            info['status'] = "Failed"

            if msg == "source_conversion_error":
                self.trace.append("Health check failed to parse result: {0}".format(source))
                info['error'] = "The health check did not return a valid JSON object"
            elif msg == "health_check_failed":
                self.trace.append("Health check failed: {0}".format(failed))
                info['error'] = "The health check did not pass"
                info.update(failed)

            self.test.TestResults(info)
            return False
        except:
            self.test.TestFinish()
            info['status'] = "Debug"
            info['error'] = "Failed to parse Health Check results"
            self.trace.append("Health Check Failed with Unhandled Exception")
            self.test.TestResults(info)
            return False

    def health_check_v2(self, **info):
        try:
            self.trace.append("Begin health check, capture page source")
            info['description'] = "Evaluate Health Check results"
            self.test.TestStart()
            source = sanitize_string(self.driver.find_element_by_xpath('//*').text)
            self.trace.append("Page source: {0}".format(source))
            self.trace.append("Attempt converting source to JSON")
            try:
                healthcheck = json.loads(source)
                self.trace.append("Successfully converted source to JSON")
            except:
                healthcheck = False
            self.assertIsInstance(healthcheck, dict, "source_conversion_error")
            failed = False
            key = info.get('key') if info.get('key') != None and len(info.get('key')) > 0 else "isHealthy"
            value = info.get('value') if info.get('value') != None and len(info.get('value')) > 0 else "true"
            self.trace.append("Expected {0}: {1} ({2})".format(key, value, type(value)))
            status = str(healthcheck.get(key))
            self.trace.append("Actual {0}: {1} ({2})".format(key, status, type(status)))
            failed = False
            if status != value:
                self.trace.append("Health status does not match expected value")
                entries = healthcheck.get('entries')
                if isinstance(entries, dict):
                    failed_dependencies = ["{0} ({1}: {2})".format(k, key, v.get(key)) for k, v in entries.items() if isinstance(v, dict) and v.get(key) != value]
                    failed = {"error": "Health check failed for dependencies: {0}".format(', '.join(failed_dependencies))}
                else:
                    failed = {"error": "Health check failed with {0}: {1}".format(key, status)}
            self.assertEqual(failed, False, "health_check_failed")
            self.test.TestFinish()
            info['status'] = "Passed"
            self.trace.append("Health check passed")
            self.test.TestResults(info)
            return True
        except AssertionError as e:
            msg_list = str(e).split(" : ")
            msg = msg_list if len(msg_list) == 1 else msg_list[1]
            self.trace.append("Assertion error: {0}".format(msg))
            self.test.TestFinish()
            info['status'] = "Failed"

            if msg == "source_conversion_error":
                self.trace.append("Health check failed to parse result: {0}".format(source))
                info['error'] = "The health check did not return a valid JSON object"
            elif msg == "health_check_failed":
                self.trace.append("Health check failed: {0}".format(failed))
                info['error'] = "The health check did not pass"
                info.update(failed)
                
            self.test.TestResults(info)
            return False
        except:
            self.test.TestFinish()
            info['status'] = "Debug"
            info['error'] = "Failed to parse Health Check results"
            self.trace.append("Health Check Failed with Unhandled Exception")
            self.test.TestResults(info)
            return False


    def go_to_url(self, **info):
        info['description'] = "Go to url {0}".format(info["url"])
        result = True
        neterror = False
        self.current_element = False
        access_error = 0
        toast_error = 0
        try:
            self.test.TestStart()
            self.trace.append("Go to URL test started")
            self.driver.get(info["url"])
            self.trace.append("Url opened: {0}".format(info["url"]))
            try:
                self.trace.append("Wait for page title")
                page_title = self.wait_for_page_title()
                self.trace.append("Page title: {0}".format(page_title))
                # Detect Microsoft login prompt
                if "login.microsoftonline.com" in self.driver.current_url:
                    try:
                        wait = WebDriverWait(self.driver, 10)
                        # wait for email field and enter email
                        wait.until(EC.element_to_be_clickable((By.XPATH, '//*/input[@type="email"]'))).send_keys(TestSettings.get('UserInfo', 'email'))

                        # Click Next
                        wait.until(EC.element_to_be_clickable((By.XPATH, '//*/input[@type="submit"]'))).click()

                        # Wait for new page to load
                        wait.until(EC.url_contains(info["url"]))
                    except:
                        self.trace.append('Failed to login to SSO page')
                # Selenium does not detect the Chrome the login prompt
                # Workaround: Use basic page source to detect likely authentication issue and manually set access_error
                if not page_title and self.driver.page_source == "<html><head></head><body></body></html>":
                    self.trace.append("Chrome login prompt detected")
                    access_error = "Not authorized"
            # If grabbing the title fails because of an existing alert, dismiss it
            except UnexpectedAlertPresentException:
                self.trace.append("Alert present, preventing title")
                self.trace.append("Attempt dismissing alert")
                self.wait_for_no_alert_present()
                self.trace.append("Alert dismissed")
                page_title = self.wait_for_page_title()
                self.trace.append("Page title: {0}".format(page_title))
                if not page_title:
                    self.trace.append("Page title is blank, get page source text")
                    access_error = sanitize_string(self.driver.find_element_by_xpath('//*').text)
                    self.trace.append("Page source text: {0}".format(access_error))

            info['url_loaded'] = self.driver.current_url
            self.trace.append("Url loaded: {0}".format(info['url_loaded']))
            self.test.TestFinish()
            self.trace.append("Go To URL test finished")

            # Look for access errors in body of page if title is blank after dismissing a prompt
            self.assertEqual(access_error, 0, "access_error")
            self.trace.append("No access error detected")

            # Look for the presence of custom Toast error element being displayed on the page
            try:
                self.trace.append("Check for toast-message class indicating custom error messages")
                toast_error = sanitize_string(self.driver.find_element_by_class_name("toast-message").text)
                self.trace.append("Custom toast-message detected: {0}".format(toast_error))
            except:
                self.trace.append("No custom toast-message detected")
                toast_error = 0

            # Check for custom Toast error
            self.assertEqual(toast_error, 0, "toast_error")

            # Check for an Apology page redirect
            self.assertNotRegexpMatches(self.driver.current_url, r'apology|outage', "apology_page")
            self.trace.append("No apology page detected")
            
            # Check for errors in the page title
            if page_title:
                self.assertNotRegexpMatches(page_title, r'(?:\D|^)[45]\d{2}(?:\D|$)', "title_includes_error_code")
                self.trace.append("No error codes in title")
                self.assertNotRegexpMatches(page_title, r'problem|failed|service\sunavailable|not\savailable|error|denied', "title_includes_error")
                self.trace.append("No error messages in title")

            # Capture neterror if present in Chrome or Firefox
            # Older versions of Chrome did not throw a WebDriverException and need to be caught manually
            try:
                self.trace.append("Check for browser neterror")
                error_div = "main-message" if self.test.results['environment']['browser']['name'] in ["Chrome", "ChromeIncognito"] else "errorLongContent"
                neterror = sanitize_string(self.driver.find_element_by_class_name('neterror').find_element(By.ID, error_div).text)
                self.trace.append("Browser error detected: {}".format(neterror))
            except:
                self.trace.append("No neterror detected")
                neterror = False

            self.assertEqual(neterror, False, "net_error")

            # Blank title
            self.assertNotEqual(page_title, False, "blank_title")
            self.trace.append("No blank title detected")

            # Success
            info['status'] = "Passed"
            self.test.TestResults(info)
            self.trace.append("Go to URL test passed")
        # Handle assertion errors
        except AssertionError as e:
            result = False
            msg_list = str(e).split(" : ")
            msg = msg_list if len(msg_list) == 1 else msg_list[1]
            self.trace.append("Assertion error: {0}".format(msg))

            if access_error:
                self.trace.append("Go to URL test failed with Warning due to Access Error on page: {0}".format(access_error))
                info['status'] = 'Warning'
                info['error'] = access_error
                result = True
                self.test.TestResults(info)

            # Handle "Toast" errors
            elif toast_error:
                try:
                    self.assertNotRegexpMatches(toast_error.lower(), r'(?:\D|^)40[1,3](?:\D|$)|unauthorized|denied', "access_error")
                    info['status'] = 'Failed'
                    info['error'] = toast_error
                    self.trace.append("Go to URL test failed with toast error: {0}".format(toast_error))
                except AssertionError:
                    info['status'] = 'Warning'
                    info['error'] = toast_error
                    result = True
                    self.trace.append("Go to URL test passed with blank title but no errors detected in body")
                self.test.TestResults(info)

            # Handle Chrome neterror
            elif neterror:
                self.trace.append("Go to URL test failed with neterror: {0}".format(neterror))
                info['status'] = 'Failed'
                info['error'] = neterror
                self.test.TestResults(info)

            # Handle blank title
            elif msg == "blank_title":
                # Capture text from the body of the loaded page
                self.trace.append('Attempt to get page source')
                try:
                    error = sanitize_string(self.driver.find_element_by_xpath('//*').text)
                except:
                    error = "failed to get page text"
                self.trace.append("See if body is valid JSON")
                try:
                    error = json.loads(error)
                    self.trace.append("Successfully converted source to JSON")
                except:
                    self.trace.append("Result: {0}".format(error))
                if len(error) == 0:
                    error = "Blank Page Loaded"
                try:
                    # If all of these tests pass, then return an error
                    self.assertNotIsInstance(error, dict, "valid_json_response") # Valid JSON indicates a Health Check
                    self.assertTrue(len(error) < 1000, "large_page_source") # Likely page loaded but page title wasn't caught in time
                    self.assertNotRegexpMatches(error.lower(), r'(?:\D|^)40[1,3](?:\D|$)|unauthorized|denied', "access_error")
                    self.assertRegexpMatches(error.lower(), r'(?:\D|^)[45]\d{2}(?:\D|$)|error|^blank', "no_error_detected") # Check for status codes or errors in the source
                    info['status'] = 'Failed'
                    info['error'] = error
                    self.trace.append("Go to URL test failed with error: {0}".format(error))
                    self.test.TestResults(info)
                except AssertionError as blank:
                    blank_msg_list = str(blank).split(" : ")
                    blank_msg = blank_msg_list if len(blank_msg_list) == 1 else blank_msg_list[1]
                    self.trace.append("Assertion error: {0}".format(blank_msg))
                    result = True
                    if blank_msg == "access_error":
                        info['status'] = 'Warning'
                        info['error'] = error
                        self.trace.append("Go to URL test passed with blank title but no errors detected in body")
                    else:
                        # No page title, but source looks ok
                        info['status'] = "Passed"
                        self.trace.append("Go to URL test passed with blank title but no errors detected in body")
                    self.test.TestResults(info)
                except:
                    self.trace.append("Unhandled Exception")
                    info['status'] = 'Debug'
                    info['error'] = 'An unknown error occured: {0}'.format(error)
                    self.test.TestResults(info)

            # Handle redirect to apology page
            elif msg == "apology_page":
                try:
                    heading = self.driver.find_element_by_tag_name('h1').get_attribute('innerHTML')
                    self.assertRegexpMatches(heading, r'^Planned')
                    info['status'] = 'Warning'
                    info['error'] = heading
                    self.trace.append("Go to URL test failed with Planned Outage apology page: {0}".format(page_title))
                    self.test.TestResults(info)
                except AssertionError:
                    info['status'] = 'Failed'
                    info['error'] = page_title
                    self.trace.append("Go to URL test failed with unplanned apology page: {0}".format(page_title))
                    self.test.TestResults(info)
                except:
                    self.trace.append("Unhandled Exception")
                    info['status'] = 'Debug'
                    info['error'] = 'An unknown error occured'
                    self.test.TestResults(info)

            # Handle errors found in the title
            elif msg in ["title_includes_error", "title_includes_error_code"]:
                try:
                    # Check if the error is related to unauthorized access
                    self.assertNotRegexpMatches(page_title, r'40[13]\D')
                    self.assertNotIn('denied',page_title)
                    info['status'] = 'Failed'
                    info['error'] = page_title
                    self.trace.append("Go to URL test failed due to error in title: {0}".format(page_title))
                    self.test.TestResults(info)
                except AssertionError:
                    self.trace.append("Go to URL test failed with Warning due to Access Error in title: {0}".format(page_title))
                    info['status'] = 'Warning'
                    info['error'] = page_title
                    result = True
                    self.test.TestResults(info)
                except:
                    self.trace.append("Unhandled Exception")
                    info['status'] = 'Debug'
                    info['error'] = 'An unknown error occured: {0}'.format(page_title)
                    self.test.TestResults(info)

            # Handle unknown assertion errors
            else:
                error = 'An unknown error occured: {0}'.format(page_title)
                info['status'] = 'Debug'
                info['error'] = error
                self.trace.append("Go to URL test failed with Unknown Error: {0}".format(page_title))
                self.test.TestResults(info)

        # Handle page timeout
        except TimeoutException:
            self.trace.append("Timeout Exception")
            result = False
            error = 'Timeout: Page did not load within 30 seconds'
            self.test.TestFinish()
            info['status'] = 'Failed'
            # "Blank" page content has a length of 39: <html><head></head><body></body></html>
            content_loaded = len(self.driver.page_source)
            info['bytes_loaded'] = 0 if content_loaded < 40 else content_loaded
            self.trace.append("Bytes loaded: {0}".format(info['bytes_loaded']))
            info['error'] = error
            self.trace.append("Go to URL test failed with TimeoutException")
            self.test.TestResults(info)

        # Handle WebDriver exceptions
        except WebDriverException as e:
            self.trace.append("WebDriver Exception: {0}".format(e.msg))
            result = False
            self.test.TestFinish()
            info['status'] = "Failed"
            try:
                # Capture neterror if present in Chrome or Firefox
                error_div = "main-message" if self.test.results['environment']['browser']['name'] in ["Chrome", "ChromeIncognito"] else "errorLongContent"
                info['error'] = sanitize_string(self.driver.find_element_by_class_name('neterror').find_element(By.ID, error_div).text)
                self.trace.append("Captured neterror from browser")
            except:
                self.trace.append("No neterror, use WebDriverException message")
                info['error'] = sanitize_string(e.msg)
                # In some cases, dismissing a login prompt results in a WebDriverException
                if "user prompt dialog" in info['error']:
                    info['status'] = "Warning"
                    result = True
                    self.trace.append("Login prompt dismissed, setting status to Warning")
            self.trace.append("Go to URL test failed with {0}: {1}".format(info['status'], info['error']))
            self.test.TestResults(info)

        # Handle unknown exceptions
        except:
            self.trace.append("Unhandled Exception")
            result = False
            self.test.TestFinish()
            info['status'] = 'Debug'
            info['error'] = 'An unknown error occured: {0}'.format(page_title)
            self.test.TestResults(info)
        finally:
            return result

    def no_alert_present(self):
        try:
            Alert(self.driver).dismiss()
            return False
        except NoAlertPresentException: return True

    def wait_for_no_alert_present(self):
        try:
            self.wait = WebDriverWait(self.driver, 5)
            self.wait.until(
                lambda x: self.no_alert_present() == True
            )
            return True
        except TimeoutException:
            return False

    # Wait up to 2 seconds for a page title
    def wait_for_page_title(self):
        try:
            self.wait = WebDriverWait(self.driver, 2)
            self.wait.until(
                lambda x: len(self.driver.title) > 0
            )
            return self.driver.title
        except TimeoutException:
            return False

    # Wait up to 5 seconds for a specific page title
    def wait_for_specific_page_title(self, title):
        try:
            self.wait = WebDriverWait(self.driver, 5)
            self.wait.until(
                lambda x: title.lower() in self.driver.title.lower()
            )
            return self.driver.title
        except TimeoutException:
            # Title doesn't contain expected string, but return it after wait
            return self.driver.title

    # Reset after each test
    def tearDown(self):
        self.current_element = False
        self.driver.get('about:blank')
        self.driver.delete_all_cookies()
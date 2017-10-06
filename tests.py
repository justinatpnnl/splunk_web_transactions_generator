from selenium import webdriver
from selenium.webdriver.firefox.firefox_profile import FirefoxProfile
from splunktransactions import Transaction
import re
import unittest
from time import sleep
from selenium.common.exceptions import TimeoutException
from selenium.common.exceptions import NoAlertPresentException
from selenium.webdriver.common.alert import Alert
from HTMLParser import HTMLParser

tests = [
    ## Application Name  |  Test Name  |  URL  |  Expected Title (optional)  |  Server Name (optional)
    ['Google','Google Home Page','https://www.google.com','Google', None],
    ['Yahoo','Yahoo Home Page','https://www.yahoo.com','Testing Title Mismatch', None],
    ['Bing','Bing Home Page','https://www.bing.com',None, None],
]

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

class DynamicTests(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        # Firefox profile object
        profile = FirefoxProfile()
        # Prevent Flash from loading (optional)
        profile.set_preference("plugin.state.flash", 0)
        # Set the modified profile while creating the browser object
        self.driver = webdriver.Firefox(profile)
        self.driver.set_page_load_timeout(30)

    @classmethod
    def tearDownClass(self):
        sleep(2)
        self.driver.quit()


def test_generator(app_name,transaction_name,url,title,server,ip):
    def test(self):
        a=Transaction(self.driver, app_name, transaction_name, url, server, ip)
        try:
            a.TransactionStart()
            self.driver.get(url)
            a.TransactionFinish()
            page_title = self.driver.title.encode('utf-8')
            page_title_lc = page_title.lower()
            self.assertNotRegexpMatches(page_title_lc, r'[4,5]\d\d', 1)
            self.assertNotRegexpMatches(page_title_lc, r'problem|not\savailable|error|denied', 2)
            if title != None:
                self.assertIn(title.lower(), page_title_lc)
            a.TransactionPass()
        except AssertionError as error:
            errornum = error[0][0]
            # Warn on access denied errors
            try:
                self.assertNotRegexpMatches(page_title_lc, r'40[1,3]')
                self.assertNotIn('denied',page_title_lc)
                if len(page_title) == 0:
                    html = self.driver.page_source
                    error = strip_tags(html)
                    if len(error) == 0:
                        error = "Error: Blank Page Loaded"
                    a.TransactionFail(error)
                elif errornum.isdigit():
                    a.TransactionFail(page_title)
                else:
                    a.TransactionFail("Unexpected Title: '%s' (instead of '%s')" % (page_title,title))
            except AssertionError as error:
                a.TransactionWarn(page_title)
        except TimeoutException:
            error = 'Timeout: Page did not load within 30 seconds'
            try:
                alert = False
                while True:
                    Alert(self.driver).dismiss()
                    alert = True
            except NoAlertPresentException:
                a.TransactionFinish()
                if alert == True:
                    a.TransactionWarn('Test account denied access')
                else:
                    a.TransactionFail(error)
        except:
            a.TransactionFinish()
            error = 'An unknown error occured: {0}'.format(page_title)
            a.TransactionFail(error)
            raise

        finally:
            a.TransactionOutput()
    return test


if __name__ == '__main__':
    count = 0

    # Build tests from array
    for test in tests:
        count = count + 1
        test_name = 'test_%03d' % count
        test_case = test_generator(test[0],test[1],test[2],test[3],test[4],None)
        setattr(DynamicTests, test_name, test_case)

unittest.main()

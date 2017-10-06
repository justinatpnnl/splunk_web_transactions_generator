import os
import re
import time
import socket
from user_agents import parse

url_pattern = re.compile(ur'(http(?:s)?:\/\/)(?:\w+:\w+@)?([^\/\:]+)(.*)')

class Transaction():
    def __init__(self, driver, name, transaction_name, url, server=None, ip=None):
        ua = driver.execute_script("return navigator.userAgent")
        user_agent = parse(ua)
        parsed_url = re.search(url_pattern, url)
        self.driver = driver
        self.app_name = name
        self.uri = parsed_url.group(2)
        self.target_url = parsed_url.group(1) + parsed_url.group(2) + parsed_url.group(3)
        self.browser_version=user_agent.browser.version_string
        self.browser=user_agent.browser.family
        self.os=user_agent.os.family
        self.os_version=user_agent.os.version_string
        self.hostname = socket.gethostname()

        if transaction_name == None:
            self.transaction_name = self.uri
        else:
            self.transaction_name = transaction_name

        if ip != None:
            self.ip = ip
        else:
            if server != None:
                test_name = server
            else:
                test_name = self.uri
            try:
                self.ip = socket.gethostbyname(test_name)
            except:
                self.ip = 'unknown'

        if server != None:
            self.server = server
        else:
            try:
                self.server = socket.gethostbyaddr(self.ip)[0]
            except:
                self.server='unknown'

    def TransactionStart(self):
        self.transaction_start_epoch = time.time()
        self.transaction_start = str(time.strftime('%Y-%m-%d %H:%M:%S'))
        self.output = '{0} {1} automated-test app_name="{2}" transaction_name="{3}"'.format(self.transaction_start, self.hostname, self.app_name, self.transaction_name)

    def TransactionFinish(self):
        self.transaction_end_epoch = time.time()
        self.transaction_end = str(time.strftime('%Y-%m-%d %H:%M:%S'))
        self.duration = round(self.transaction_end_epoch - self.transaction_start_epoch, 2)

    def TransactionPass(self):
        self.output += ' result=Passed duration={0}'.format(self.duration)

    def TransactionWarn(self, error):
        self.output += ' result=Warning error="{0}" duration={1}'.format(error, self.duration)

    def TransactionFail(self, error):
        self.output += ' result=Failed error="{0}" duration={1}'.format(error, self.duration)

    def TransactionOutput(self):
        self.actual_url = self.driver.current_url
        self.output += ' browser="{0}" browser_version="{1}" os="{2}" os_version="{3}" ip="{4}" server="{5}" uri="{6}" target_url="{7}" resolved_url="{8}"'.format(self.browser, self.browser_version, self.os, self.os_version, self.ip, self.server, self.uri, self.target_url, self.actual_url)
print self.output

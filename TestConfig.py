import os
import ConfigParser

configfile_path = os.path.join(os.path.dirname(__file__), "settings.conf")
TestSettings = ConfigParser.ConfigParser()

# Create configuration file if it doesn't exist
if not os.path.isfile(configfile_path):
    cfgfile = open(configfile_path, 'w')

    # Add Sections and default settings to the file
    TestSettings.add_section('SeleniumHub')
    TestSettings.set('SeleniumHub', 'protocol', 'http')
    TestSettings.set('SeleniumHub', 'host', 'localhost')
    TestSettings.set('SeleniumHub', 'port', '4444')
    TestSettings.add_section('BrowserSettings')
    TestSettings.set('BrowserSettings', 'sitelist', '')
    TestSettings.write(cfgfile)
    cfgfile.close()
else:
    TestSettings.read(configfile_path)

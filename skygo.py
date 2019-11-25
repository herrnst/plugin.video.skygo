#!/usr/bin/env python
# -*- coding: utf-8 -*-

import base64
import struct
import requests
import json
import re
import datetime
import time
import pickle
import os
import xml.etree.ElementTree as ET
from pyDes import *
from platform import node
import uuid
import xbmc
import xbmcgui
import xbmcplugin
from inputstreamhelper import Helper
from kodi_six.utils import py2_encode


class SkyGo:
    """Sky Go Class"""

    baseUrl = "https://skyticket.sky.de"
    baseServicePath = '/st'
    user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/70.0.3538.110 Safari/537.36'
    sessionId = ''
    LOGIN_STATUS = {'SUCCESS': 'T_100', 'SESSION_INVALID': 'S_218', 'OTHER_SESSION':'T_206'}
    entitlements = []


    def __init__(self, addon_handle, addon, common):

        self.addon_handle = addon_handle
        self.addon = addon
        self.common = common

        datapath = xbmc.translatePath(self.addon.getAddonInfo('profile'))
        self.cookiePath = '{0}COOKIES'.format(datapath)

        platform_props = self.getPlatformProps()
        self.platform = platform_props.get('platform')
        self.license_url = platform_props.get('license_url')
        self.license_type = platform_props.get('license_type')
        self.android_deviceId = platform_props.get('android_deviceid')

        # Create session with old cookies
        self.session = requests.session()
        self.session.headers.update({'User-Agent': self.user_agent})

        if os.path.isfile(self.cookiePath):
            with open(self.cookiePath, 'rb') as f:
                try:
                    cookies = requests.utils.cookiejar_from_dict(pickle.load(f))
                    self.session.cookies = cookies
                except:
                    self.isLoggedIn()
                    # Save the cookies
                    with open(self.cookiePath, 'wb') as f:
                        pickle.dump(requests.utils.dict_from_cookiejar(self.session.cookies), f)
        return


    def isLoggedIn(self):
        """Check if User is still logged in with the old cookies"""
        r = self.session.get('https://www.skygo.sky.de/SILK/services/public/user/getdata?product=SG&platform=web&version=12354')
        # Parse json
        response = r.text[3:-1]
        response = json.loads(response)

        if response['resultMessage'] == 'OK':
            self.sessionId = response['skygoSessionId']
            self.entitlements = response['entitlements']
            xbmc.log('[Sky Go] User still logged in')
            return True
        else:
            xbmc.log('[Sky Go] User not logged in or Session on other device')
            if response['resultCode'] == self.LOGIN_STATUS['SESSION_INVALID']:
                xbmc.log('[Sky Go] Session invalid - Customer Code not found in SilkCache')
                return False
        return False


    def killSessions(self):
        # Kill other sessions
        r = self.session.get('https://www.skygo.sky.de/SILK/services/public/session/kill/web?version=12354&platform=web&product=SG')


    def sendLogin(self, username, password):
        # Try to login
        login = "email={0}".format(username)
        if not re.match(r"^[A-Za-z0-9\.\+_-]+@[A-Za-z0-9\._-]+\.[a-zA-Z]*$", username):
            login = "customerCode={0}".format(username)
        r = self.session.get('https://www.skygo.sky.de/SILK/services/public/session/login?' \
                             'version=12354&platform=web&product=SG&{0}&password={1}&remMe=true' \
                             .format(login, self.decode(password)))
        # Parse json
        return json.loads(r.text[3:-1])


    def login(self, username=None, password=None, forceLogin=False, askKillSession=True):
        if not username and not password:
            username = self.addon.getSetting('email')
            password = self.addon.getSetting('password')

        # If already logged in and active session everything is fine
        if forceLogin or not self.isLoggedIn():
            # remove old cookies
            self.session.cookies.clear_session_cookies()
            response = self.sendLogin(username, password)

            # if login is correct but other session is active ask user if other session should be killed - T_227=SkyGoExtra
            if response['resultCode'] in ['T_206', 'T_227']:
                kill_session = False
                if self.addon.getSetting('autoKillSession') == 'true' or askKillSession == False:
                    kill_session = True

                if not kill_session:
                    kill_session = xbmcgui.Dialog().yesno('Sie sind bereits eingeloggt!',
                        'Sie sind bereits auf einem anderen Gerät oder mit einem anderen Browser eingeloggt.' \
                        ' Wollen Sie die bestehende Sitzung beenden und sich jetzt hier neu anmelden?')

                if kill_session:
                    # Kill all Sessions (including ours)
                    self.killSessions()
                    # Session killed so login again
                    self.sendLogin(username, password)
                    # Activate Session
                    self.isLoggedIn()
                    # Save the cookies
                    with open(self.cookiePath, 'wb') as f:
                        pickle.dump(requests.utils.dict_from_cookiejar(self.session.cookies), f)
                    return True
                return False
            elif response['resultMessage'] == 'KO':
                xbmcgui.Dialog().notification('Sky Go: Login', 'Bitte Login-Daten überprüfen.', icon=xbmcgui.NOTIFICATION_ERROR)
                return False
            elif response['resultCode'] == 'T_100':
                # Activate Session with new test if user is logged in
                self.isLoggedIn()
                return True
        else:
            return True

        # If any case is not matched return login failed
        return False


    def setLogin(self):
        keyboard = xbmc.Keyboard(self.addon.getSetting('email'), 'Kundennummer / E-Mail-Adresse')
        keyboard.doModal()
        if keyboard.isConfirmed() and keyboard.getText():
            email = keyboard.getText()
            password = self.setLoginPW()
            if password != '':
                self.addon.setSetting('email', email)
                password = self.encode(password)

                if self.login(email, password, forceLogin=True, askKillSession=False):
                    self.addon.setSetting('password', password)
                    self.addon.setSetting('login_acc', email)
                    xbmcgui.Dialog().notification('Sky Go: Login', 'Angemeldet als "{0}".'.format(email), icon=xbmcgui.NOTIFICATION_INFO)
                else:
                    self.addon.setSetting('password', '')
                    self.addon.setSetting('login_acc', '')


    def setLoginPW(self):
        keyboard = xbmc.Keyboard('', 'Passwort', True)
        keyboard.doModal(60000)
        if keyboard.isConfirmed() and keyboard.getText() and len(keyboard.getText()) == 4:
            password = keyboard.getText()
            return password
        return ''


    def encode(self, data):
        k = triple_des(self.getmac(), CBC, "\0\0\0\0\0\0\0\0", padmode=PAD_PKCS5)
        d = k.encrypt(data)
        return base64.b64encode(d)


    def decode(self, data):
        if not data:
            return ''
        k = triple_des(self.getmac(), CBC, "\0\0\0\0\0\0\0\0", padmode=PAD_PKCS5)
        d = k.decrypt(base64.b64decode(data))
        return d.decode('utf-8')


    def getmac(self):
        mac = uuid.getnode()
        if (mac >> 40) % 2:
            mac = node()
        return uuid.uuid5(uuid.NAMESPACE_DNS, str(mac)).bytes


    def getPlayInfo(self, id='', url=''):
        ns = {'media': 'http://search.yahoo.com/mrss/', 'skyde': 'http://sky.de/mrss_extensions/'}

        # If no url is given we assume that the url hast to be build with the id
        if url == '':
            url = self.baseUrl + self.baseServicePath + "/multiplatform/web/xml/player_playlist/asset/" + str(id) + ".xml"

        r = requests.get(url)
        tree = ET.ElementTree(ET.fromstring(py2_encode(r.text)))
        root = tree.getroot()
        manifest_url = root.find('channel/item/media:content', ns).attrib['url']
        apix_id = root.find('channel/item/skyde:apixEventId', ns).text
        package_code = root.find('channel/item/skyde:packageCode', ns).text

        return {'manifestUrl': manifest_url, 'apixId': apix_id, 'duration': 0, 'package_code': package_code}


    def getCurrentEvent(self, epg_channel_id):
        # Save date for fure use
        now = datetime.datetime.now()
        current_date = now.strftime("%d.%m.%Y")
        # Get Epg information
        xbmc.log('[Sky Go]  eventlisturl = {0}/epgd{1}/web/eventList/{2}/{3}/'.format(self.baseUrl, self.baseServicePath, current_date, epg_channel_id))
        r = requests.get('{0}/epgd{1}/web/eventList/{2}/{3}/'.format(self.baseUrl, self.baseServicePath, current_date, epg_channel_id))
        events = r.json()[epg_channel_id]
        for event in events:
            start_date = datetime.datetime(*('{0} {1}'.format(time.strptime(event['startDate'], event['startTime'], '%d.%m.%Y %H:%M')[0:6])))
            end_date = datetime.datetime(*('{0} {1}'.format(time.strptime(event['endDate'], event['endTime'], '%d.%m.%Y %H:%M')[0:6])))
            # Check if event is running event
            if start_date < now < end_date:
                return event
        # Return False if no current running event
        return False


    def getEventPlayInfo(self, event_id, epg_channel_id):
        # If not Sky news then get details id else use hardcoded playinfo_url
        if epg_channel_id != '17':
            r = requests.get('{0}/epgd{1}/web/eventDetail/{2}/{3}/'.format(self.baseUrl, self.baseServicePath, event_id, epg_channel_id))
            event_details_link = r.json()['detailPage']
            # Extract id from details link
            p = re.compile('/([0-9]*)\.html', re.IGNORECASE)
            m = re.search(p, event_details_link)
            playlist_id = m.group(1)
            playinfo_url = '{0}{1}/multiplatform/web/xml/player_playlist/asset/{2}.xml'.format(self.baseUrl, self.baseServicePath, playlist_id)
        else:
            playinfo_url = '{0}{1}/multiplatform/web/xml/player_playlist/ssn/127.xml'.format(self.baseUrl + self.baseServicePath)

        return self.getPlayInfo(url=playinfo_url)


    def may_play(self, entitlement):
        return entitlement in self.entitlements


    def getAssetDetails(self, asset_id):
        url = '{0}{1}/multiplatform/web/json/details/asset/{2}.json'.format(self.baseUrl, self.baseServicePath, asset_id)
        r = self.session.get(url)
        if self.common.get_dict_value(r.headers, 'content-type').startswith('application/json'):
            return r.json()['asset']
        else:
            return {}


    def getClipDetails(self, clip_id):
        url = '{0}{1}/multiplatform/web/json/details/clip/{2}.json'.format(self.baseUrl, self.baseServicePath, clip_id)
        r = self.session.get(url)
        return r.json()['detail']


    def get_init_data(self, session_id, apix_id):
        if self.license_type == 'com.microsoft.playready':
            init_data = 'sessionId={0}&apixId={1}&deviceId={2}&platformId=AndP&product=BW&version=1.7.1&DeviceFriendlyName=Android' \
                .format(self.sessionId, apix_id, self.android_deviceId)
        else:
            init_data = 'kid={0}&sessionId={1}&apixId={2}&platformId=&product=BW&channelId='.format('{UUID}', session_id, apix_id)
            init_data = struct.pack('1B', *[30]) + init_data.encode('utf-8')
            init_data = base64.urlsafe_b64encode(init_data)
        return init_data


    def parentalCheck(self, parental_rating, play=False):
        if parental_rating == 0:
            return True

        ask_pin = self.addon.getSetting('js_askforpin')
        max_rating = self.addon.getSetting('js_maxrating')
        if max_rating.isdigit():
            if int(max_rating) < 0:
                return True
            if int(max_rating) < parental_rating:
                if ask_pin == 'false' or not play:
                    return False
                else:
                    dlg = xbmcgui.Dialog()
                    code = dlg.input('PIN Code', type=xbmcgui.INPUT_NUMERIC)
                    if self.encode(code) == password:
                        return True
                    else:
                        return False

        return True


    def getPlatformProps(self):
        props = {}

        if xbmc.getCondVisibility('system.platform.android') and self.addon.getSetting('android_drm_widevine') == 'false':
            props.update({'license_type': 'com.microsoft.playready'})

            android_deviceid = None
            if self.addon.getSetting('android_deviceid'):
                android_deviceid = self.addon.getSetting('android_deviceid')
            else:
                android_deviceid = str(uuid.uuid1())
                self.addon.setSetting('android_deviceid', android_deviceid)

            props.update({'android_deviceid': android_deviceid})
        else:
            props.update({'license_type': 'com.widevine.alpha'})
            props.update({'license_url': 'https://wvguard.sky.de/WidevineLicenser/WidevineLicenser|User-Agent=Mozilla%2F5.0%20(X11%3B%20Linux%20x86_64)%20AppleWebKit%2F537.36%20(KHTML%2C%20like%20Gecko)%20Chrome%2F49.0.2623.87%20Safari%2F537.36&Referer=http%3A%2F%2Fwww.skygo.sky.de%2Ffilm%2Fscifi--fantasy%2Fjupiter-ascending%2Fasset%2Ffilmsection%2F144836.html&Content-Type=|R{SSM}|'})

        return props


    def play(self, manifest_url, package_code, parental_rating=0, info_tag=None, art_tag=None, apix_id=None):
        # Inputstream and DRM
        helper = Helper(protocol='ism', drm='widevine')
        if helper.check_inputstream():
            # Jugendschutz
            if not self.parentalCheck(parental_rating, play=True):
                xbmcgui.Dialog().notification('Sky Go: FSK {0}'.format(parental_rating), 'Keine Berechtigung zum Abspielen dieses Eintrags.', xbmcgui.NOTIFICATION_ERROR, 2000, True)
                xbmc.log('[Sky Go] FSK {0}: Keine Berechtigung zum Abspielen'.format(parental_rating))

            if self.login():
                if self.may_play(package_code):
                    init_data = None

                    # create init data for license acquiring
                    if apix_id:
                        init_data = self.get_init_data(self.sessionId, apix_id)

                    # Prepare new ListItem to start playback
                    li = xbmcgui.ListItem(path=manifest_url)
                    if info_tag:
                        li.setInfo('video', info_tag)
                    if art_tag:
                        li.setArt(art_tag)

                    li.setProperty('inputstreamaddon', 'inputstream.adaptive')
                    li.setProperty('inputstream.adaptive.license_type', self.license_type)
                    li.setProperty('inputstream.adaptive.manifest_type', 'ism')
                    li.setProperty('inputstream.adaptive.license_flags', 'persistent_storage')
                    if self.license_url:
                        li.setProperty('inputstream.adaptive.license_key', self.license_url)
                    if init_data:
                        li.setProperty('inputstream.adaptive.license_data', init_data)

                    # Start Playing
                    xbmcplugin.setResolvedUrl(self.addon_handle, True, li)
                    return
                else:
                    xbmcgui.Dialog().notification('Sky Go: Berechtigung', 'Keine Berechtigung zum Abspielen dieses Eintrags', xbmcgui.NOTIFICATION_ERROR, 2000, True)
                    xbmc.log('[Sky Go] Keine Berechtigung zum Abspielen')
                    xbmc.log('[Sky Go] Berechtigungen = {0}'.format(self.entitlements))
                    xbmc.log('[Sky Go] Geforderte Berechtigung = {0}'.format(package_code))
            else:
                xbmc.log('[Sky Go] Fehler beim Login')

        xbmcplugin.setResolvedUrl(self.addon_handle, False, xbmcgui.ListItem())
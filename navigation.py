#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from kodi_six.utils import py2_encode, py2_decode
import os
import xbmc, xbmcgui, xbmcplugin, xbmcaddon, xbmcvfs
import json
import datetime
import time
import xml.etree.ElementTree as ET
import re
import base64

import watchlist

try:
    import StorageServer
except:
    import storageserverdummy as StorageServer

try:
    import urllib.parse as urlparse
    import urllib.parse as urllib
    from urllib.request import build_opener, urlopen
    from urllib.error import URLError
except:
    import urlparse
    import urllib
    from urllib2 import build_opener, urlopen, URLError


class Navigation:


    def __init__(self, addon, common, skygo):

        self.addon = addon
        self.common = common
        self.skygo = skygo

        # Doc for Caching Function: http://kodi.wiki/index.php?title=Add-on:Common_plugin_cache
        self.assetDetailsCache = StorageServer.StorageServer(py2_encode('{0}.assetdetails').format(self.addon.getAddonInfo('name')), 24 * 30)
        self.TMDBCache = StorageServer.StorageServer(py2_encode('{0}.TMDBdata').format(self.addon.getAddonInfo('name')), 24 * 30)

        self.extMediaInfos = self.addon.getSetting('enable_extended_mediainfos')
        self.icon_file = xbmc.translatePath('{0}/icon.png'.format(self.addon.getAddonInfo('path')))

        # Blacklist: diese nav_ids nicht anzeigen
        # 15 = Snap
        # Live Planer: 154 = Inside Report, 268 = Europa League, 262 = Sky Go Erste Liga, 290 = Audi Star Talk, 159 = X-Treme
        self.nav_blacklist = [15, 35, 154, 268, 262, 290, 159]

        # Jugendschutz
        self.js_showall = self.addon.getSetting('js_showall')


    def getNav(self):
        opener = build_opener()
        opener.addheaders = [('User-Agent', self.skygo.user_agent)]
        feed = opener.open(self.skygo.baseUrl + self.skygo.baseServicePath + '/multiplatform/ipad/json/navigation.xml')
        nav = ET.parse(feed)
        return nav.getroot()


    def liveChannelsDir(self):
        url = self.common.build_url({'action': 'listLiveTvChannelDirs'})
        self.addDir('Livesender', url)


    def watchlistDir(self):
        url = self.common.build_url({'action': 'watchlist'})
        self.addDir('Merkliste', url)


    def rootDir(self):
        nav = self.getNav()
        # Livesender
        self.liveChannelsDir()
        # Navigation der Ipad App
        for item in nav:
            if item.attrib['hide'] == 'true' or item.tag == 'item':
                continue
            url = self.common.build_url({'action': 'listPage', 'id': item.attrib['id']})
            self.addDir(item.attrib['label'], url)

        # Merkliste
        self.watchlistDir()
        # Suchfunktion
        url = self.common.build_url({'action': 'search'})
        self.addDir('Suche', url)

        xbmcplugin.endOfDirectory(self.skygo.addon_handle, cacheToDisc=True)


    def addDir(self, label, url, icon=None):
        li = xbmcgui.ListItem(label)
        li.setArt({'icon': icon if icon else self.icon_file, 'thumb': self.icon_file})
        xbmcplugin.addDirectoryItem(handle=self.skygo.addon_handle, url=url, listitem=li, isFolder=True)


    def showParentalSettings(self):
        fsk_list = ['Deaktiviert', '0', '6', '12', '16', '18']
        dlg = xbmcgui.Dialog()
        code = dlg.input('PIN Code', type=xbmcgui.INPUT_NUMERIC)
        if self.skygo.encode(code) == self.addon.getSetting('password'):
            idx = dlg.select('Wähle maximale FSK Alterstufe', fsk_list)
            if idx >= 0:
                fsk_code = fsk_list[idx]
                if fsk_code == 'Deaktiviert':
                    self.addon.setSetting('js_maxrating', '-1')
                else:
                    self.addon.setSetting('js_maxrating', fsk_list[idx])
            if idx > 0:
                if dlg.yesno('Jugendschutz', 'Sollen Inhalte mit einer Alterseinstufung über ', 'FSK ' + fsk_list[idx] + ' angezeigt werden?'):
                    self.addon.setSetting('js_showall', 'true')
                else:
                    self.addon.setSetting('js_showall', 'false')
        else:
            xbmcgui.Dialog().notification('Sky Go: Jugendschutz', 'Fehlerhafte PIN', xbmcgui.NOTIFICATION_ERROR, 2000, True)


    def getHeroImage(self, data):
        if 'main_picture' in data:
            for pic in data['main_picture']['picture']:
                if pic['type'] == 'hero_img':
                    return self.skygo.baseUrl + pic['path'] + '/' + pic['file'] + '|User-Agent=' + self.skygo.user_agent
        if 'item_image' in data:
            return self.skygo.baseUrl + data['item_image'] + '|User-Agent=' + self.skygo.user_agent
        if 'picture' in data:
            return self.skygo.baseUrl + data['picture'] + '|User-Agent=' + self.skygo.user_agent

        return ''


    def getPoster(self, data):
        if 'name' in data and self.addon.getSetting('enable_customlogos') == 'true':
            img = self.getLocalChannelLogo(data['name'])
            if img:
                return img

        if data.get('dvd_cover', '') != '':
            return self.skygo.baseUrl + data['dvd_cover']['path'] + '/' + data['dvd_cover']['file'] + '|User-Agent=' + self.skygo.user_agent
        if data.get('item_preview_image', '') != '':
            return self.skygo.baseUrl + data['item_preview_image'] + '|User-Agent=' + self.skygo.user_agent
        if data.get('picture', '') != '':
            return self.skygo.baseUrl + data['picture'] + '|User-Agent=' + self.skygo.user_agent
        if data.get('logo', '') != '':
            return self.skygo.baseUrl + data['logo'] + '|User-Agent=' + self.skygo.user_agent

        return ''


    def getChannelLogo(self, data):
        logopath = ''
        if 'channelLogo' in data:
            basepath = data['channelLogo']['basepath'] + '/'
            size = 0
            for logo in data['channelLogo']['logos']:
                logosize = logo['size'][:logo['size'].find('x')]
                if int(logosize) > size:
                    size = int(logosize)
                    logopath = self.skygo.baseUrl + basepath + logo['imageFile'] + '|User-Agent=' + self.skygo.user_agent
        return logopath


    def getLocalChannelLogo(self, channel_name):
        logo_path = self.addon.getSetting('logoPath')
        if not logo_path == '' and xbmcvfs.exists(logo_path):
            dirs, files = xbmcvfs.listdir(logo_path)
            for f in files:
                if f.lower().endswith('.png'):
                    if channel_name.lower().replace(' ', '') == os.path.basename(f).lower().replace('.png', '').replace(' ', ''):
                        return os.path.join(logo_path, f)

        return None


    def search(self):
        dlg = xbmcgui.Dialog()
        term = dlg.input('Suchbegriff', type=xbmcgui.INPUT_ALPHANUM)
        if term == '':
            return
        url = 'https://www.skygo.sky.de/SILK/services/public/search/web?{0}'.format(urllib.urlencode({
            'searchKey': term,
            'version': '12354',
            'platform': 'web',
            'product': 'SG'
        }))

        r = self.skygo.session.get(url)
        if self.common.get_dict_value(r.headers, 'content-type').startswith('application/x-javascript'):
            data = json.loads(r.text[3:len(r.text) - 1])
            listitems = []
            for item in data['assetListResult']:
                url = self.common.build_url({'action': 'playVod', 'vod_id': item['id']})
                listitems.append({'type': 'searchresult', 'label': item['title'], 'url': url, 'data': item})

    #    if data['assetListResult']['hasNext']:
    #        url = self.common.build_url({'action': 'listPage', 'path': ''})
    #        listitems.append({'type': 'path', 'label': 'Mehr...', 'url': url})

            self.listAssets(listitems)

        xbmcplugin.endOfDirectory(self.skygo.addon_handle, cacheToDisc=True)


    def listLiveTvChannelDirs(self):
        channels = ['bundesliga', 'cinema', 'entertainment', 'sport']
        for channel in channels:
            url = self.common.build_url({'action': 'listLiveTvChannels', 'channeldir_name': channel})
            li = xbmcgui.ListItem(label=channel.title())
            li.setArt({'icon': self.icon_file, 'thumb': self.icon_file})
            xbmcplugin.addDirectoryItem(handle=self.skygo.addon_handle, url=url, listitem=li, isFolder=True)

        xbmcplugin.endOfDirectory(self.skygo.addon_handle, cacheToDisc=True)


    def listLiveTvChannels(self, channeldir_name):
        data = self.getlistLiveChannelData(channeldir_name)
        for tab in data:
            if tab['tabName'].lower() == channeldir_name.lower():
                details = self.getLiveChannelDetails(tab.get('eventList'), None)
                self.listAssets(sorted(details.values(), key=lambda k:k['data']['channel']['name']))

        xbmcplugin.endOfDirectory(self.skygo.addon_handle, cacheToDisc=False)


    def getlistLiveChannelData(self, channel=None):
        data = {}
        r = self.skygo.session.get(self.skygo.baseUrl + '/epgd' + self.skygo.baseServicePath + '/ipad/excerpt/')
        if self.common.get_dict_value(r.headers, 'content-type').startswith('application/json'):
            data = r.json()
            for tab in data:
                if tab['tabName'] == 'film':
                    tab['tabName'] = 'cinema'
                elif tab['tabName'] == 'buli':
                    tab['tabName'] = 'bundesliga'

            if channel:
                channel_list = []

                data = [json for json in data if json['tabName'].lower() == channel.lower()]
                for tab in data:
                    for event in tab['eventList']:
                        if event.get('event').get('assetid', None) is None:
                            event['event']['assetid'] = re.search('\/(\d+)\.html', event['event']['detailPage']).group(1) if event['event']['detailPage'].startswith('http') else None
                        if event.get('event').get('cmsid', None) is None:
                            event['event']['cmsid'] = int(re.search('(\d+)', event['event']['image'][event['event']['image'].rfind('_') + 1:]).group(1)) if event['event']['image'].endswith('png') else None

                        channel_list.append(event['channel']['name'])

                r = self.skygo.session.get(self.skygo.baseUrl + '/epgd' + self.skygo.baseServicePath + '/web/excerpt/')
                if self.common.get_dict_value(r.headers, 'content-type').startswith('application/json'):
                    data_web = r.json()
                    data_web = [json for json in data_web if json['tabName'].lower() == channel.lower()]
                    for tab_web in data_web:
                        for event_web in tab_web['eventList']:
                            if event_web['channel']['name'] not in channel_list:
                                for tab in data:
                                    if event_web.get('event').get('assetid', None) is None:
                                        event_web['event']['assetid'] = re.search('\/(\d+)\.html', event_web['event']['detailPage']).group(1) if event_web['event']['detailPage'].startswith('http') else None
                                    if event_web.get('event').get('cmsid', None) is None:
                                        event_web['event']['cmsid'] = int(re.search('(\d+)', event_web['event']['image'][event_web['event']['image'].rfind('_') + 1:]).group(1)) if event_web['event']['image'].endswith('png') else None

                                    msMediaUrl = None
                                    if event_web['channel']['mediaurl'].startswith('http'):
                                        msMediaUrl = event_web['channel']['mediaurl']
                                    elif event_web['event']['assetid']:
                                        media_url = self.getAssetDetailsFromCache(event_web['event']['assetid']).get('media_url')
                                        if media_url and media_url.startswith('http'):
                                            msMediaUrl = media_url

                                    if msMediaUrl:
                                        channel_list.append(event_web['channel']['name'])
                                        event_web['channel']['msMediaUrl'] = msMediaUrl
                                        tab['eventList'].append(event_web)

        if len(data) == 0:
            xbmcgui.Dialog().notification('Sky Go: Datenabruf', 'Es konnten keine Daten geladen werden', xbmcgui.NOTIFICATION_ERROR, 2000, True)

        return sorted(data, key=lambda k: k['tabName'])


    def getLiveChannelDetails(self, eventlist, s_manifest_url=None):
        details = {}
        for event in eventlist:
            url = None
            manifest_url = None

            if event['channel'].get('msMediaUrl', None) and event['channel']['msMediaUrl'].startswith('http'):
                manifest_url = event['channel']['msMediaUrl']
                url = self.common.build_url({'action': 'playLive', 'manifest_url': manifest_url, 'package_code': event['channel']['mobilepc']})
            elif not s_manifest_url and event.get('event').get('assetid'):
                if self.extMediaInfos and self.extMediaInfos == 'true':
                    mediainfo = self.getAssetDetailsFromCache(event['event']['assetid'])
                    if len(mediainfo) > 0:
                        event['mediainfo'] = mediainfo

                url = self.common.build_url({'action': 'playVod', 'vod_id': event['event']['assetid']})

            if not event.get('mediainfo') and self.extMediaInfos and self.extMediaInfos == 'true':
                assetid_match = re.search('\/(\d+)\.html', event['event']['detailPage'])
                if assetid_match:
                    assetid = 0
                    try:
                        assetid = int(assetid_match.group(1))
                    except:
                        pass

                    if assetid > 0:
                        mediainfo = self.getAssetDetailsFromCache(assetid)
                        if len(mediainfo) > 0:
                            event['mediainfo'] = mediainfo
                            if not manifest_url or not manifest_url.startswith('http'):
                                manifest_url = mediainfo.get('media_url')
                            if not manifest_url or not manifest_url.startswith('http'):
                                continue

            if event['event']['detailPage'].startswith("http"):
                detail = event['event']['detailPage']
            else:
                detail = str(event['event']['cmsid'])

            # zeige keine doppelten sender mit gleichem stream - nutze hd falls verfügbar
            if url and detail != '':
                parental_rating = 0
                fskInfo = re.search('(\d+)', event['event']['fskInfo'])
                if fskInfo:
                    try:
                        parental_rating = int(fskInfo.group(1))
                    except:
                        pass
                event['parental_rating'] = {'value': parental_rating}

                if not detail in details.keys():
                    details[detail] = {'type': 'live', 'label': event['channel']['name'], 'url': url, 'data': event}
                elif details[detail]['url'] == '':
                    newlabel = details[detail]['data']['channel']['name']
                    event['channel']['name'] = newlabel
                    details[detail] = {'type': 'live', 'label': newlabel, 'url': url, 'data': event}
                elif details[detail]['data']['channel']['hd'] == 0 and event['channel']['hd'] == 1 and event['channel']['name'].find('+') == -1:
                    details[detail] = {'type': 'live', 'label': event['channel']['name'], 'url': url, 'data': event}

                if s_manifest_url and manifest_url:
                    if s_manifest_url == manifest_url:
                        return {detail: details[detail]}

        return {} if s_manifest_url else details


    def listEpisodesFromSeason(self, series_id, season_id):
        url = self.skygo.baseUrl + self.skygo.baseServicePath + '/multiplatform/web/json/details/series/' + str(series_id) + '_global.json'
        r = self.skygo.session.get(url)
        if self.common.get_dict_value(r.headers, 'content-type').startswith('application/json'):
            data = r.json()['serieRecap']['serie']
            xbmcplugin.setContent(self.skygo.addon_handle, 'episodes')
            for season in data['seasons']['season']:
                if str(season['id']) == str(season_id):
                    for episode in season['episodes']['episode']:
                        # Check Altersfreigabe / Jugendschutzeinstellungen
                        parental_rating = 0
                        if 'parental_rating' in episode:
                            parental_rating = episode['parental_rating']['value']
                            if self.js_showall == 'false':
                                if not self.skygo.parentalCheck(parental_rating, play=False):
                                    continue
                        li = xbmcgui.ListItem()
                        li.setProperty('IsPlayable', 'true')
                        li.addContextMenuItems([
                            ('Aktualisieren', 'RunPlugin({0})'.format(self.common.build_url({'action': 'refresh'}))),
                            self.getWatchlistContextItem({'type': 'Episode', 'data': episode})
                        ], replaceItems=False)
                        info, episode = self.getInfoLabel('Episode', episode)
                        li.setInfo('video', info)
                        li.setLabel(episode.get('li_label') if episode.get('li_label', None) else info['title'])
                        # li = self.addStreamInfo(li, episode)
                        art = {'poster': self.skygo.baseUrl + season['path'] + '|User-Agent=' + self.skygo.user_agent,
                                'fanart': self.getHeroImage(data),
                                'thumb': self.skygo.baseUrl + episode['webplayer_config']['assetThumbnail'] + '|User-Agent=' + self.skygo.user_agent}
                        li.setArt(art)
                        url = self.common.build_url({'action': 'playVod', 'vod_id': episode['id'], 'infolabels': info, 'parental_rating': parental_rating, 'art': art})
                        xbmcplugin.addDirectoryItem(handle=self.skygo.addon_handle, url=url, listitem=li, isFolder=False)

            xbmcplugin.addSortMethod(self.skygo.addon_handle, sortMethod=xbmcplugin.SORT_METHOD_EPISODE)

        xbmcplugin.endOfDirectory(self.skygo.addon_handle, cacheToDisc=True)


    def listSeasonsFromSeries(self, series_id):
        url = self.skygo.baseUrl + self.skygo.baseServicePath + '/multiplatform/web/json/details/series/' + str(series_id) + '_global.json'
        r = self.skygo.session.get(url)
        if self.common.get_dict_value(r.headers, 'content-type').startswith('application/json'):
            data = r.json()['serieRecap']['serie']
            xbmcplugin.setContent(self.skygo.addon_handle, 'tvshows')
            for season in data['seasons']['season']:
                url = self.common.build_url({'action': 'listSeason', 'id': season['id'], 'series_id': data['id']})
                label = '%s - Staffel %02d' % (data['title'], season['nr'])
                li = xbmcgui.ListItem(label=label)
                li.setProperty('IsPlayable', 'false')
                li.setArt({'poster': self.skygo.baseUrl + season['path'] + '|User-Agent=' + self.skygo.user_agent,
                           'fanart': self.getHeroImage(data),
                           'thumb': self.icon_file})
                li.setInfo('video', {'plot': data['synopsis'].replace('\n', '').strip()})
                li.addContextMenuItems([
                    ('Aktualisieren', 'RunPlugin({0})'.format(self.common.build_url({'action': 'refresh'}))),
                    self.getWatchlistContextItem({'type': 'Episode', 'data': season})
                ], replaceItems=False)
                xbmcplugin.addDirectoryItem(handle=self.skygo.addon_handle, url=url, listitem=li, isFolder=True)

        xbmcplugin.endOfDirectory(self.skygo.addon_handle, cacheToDisc=True)


    def getAssets(self, data, key='asset_type'):
        asset_list = []
        for asset in data:
            if asset[key].lower() in ['film', 'episode', 'sport']:
                url = self.common.build_url({'action': 'playVod', 'vod_id': asset['id']})
                asset_list.append({'type': asset[key], 'label': '', 'url': url, 'data': asset})
            elif asset[key].lower() == 'clip':
                url = self.common.build_url({'action': 'playClip', 'id': asset['id']})
                asset_list.append({'type': asset[key], 'label': '', 'url': url, 'data': asset})
            elif asset[key].lower() == 'series':
                url = self.common.build_url({'action': 'listSeries', 'id': asset['id']})
                asset_list.append({'type': asset[key], 'label': asset['title'], 'url': url, 'data': asset})
            elif asset[key].lower() == 'season':
                url = self.skygo.baseUrl + self.skygo.baseServicePath + '/multiplatform/web/json/details/series/' + str(asset['serie_id']) + '_global.json'
                r = self.skygo.session.get(url)
                if self.common.get_dict_value(r.headers, 'content-type').startswith('application/json'):
                    serie = r.json()['serieRecap']['serie']
                    asset['synopsis'] = serie['synopsis']
                    for season in serie['seasons']['season']:
                        if season['id'] == asset['id']:
                            asset['episodes'] = season['episodes']
                    url = self.common.build_url({'action': 'listSeason', 'id': asset['id'], 'series_id': asset['serie_id']})
                    asset_list.append({'type': asset[key], 'label': asset['title'], 'url': url, 'data': asset})

        return asset_list


    def checkForLexic(self, listing):
        if len(listing) == 2:
            if 'ByLexic' in listing[0]['structureType'] and 'ByYear' in listing[1]['structureType']:
                return True

        return False


    def parseListing(self, page, path):
        listitems = []
        curr_page = 1
        page_count = 1
        if 'letters' in page:
            for item in page['letters']['letter']:
                if item['linkable'] is True:
                    url = self.common.build_url({'action': 'listPage', 'path': path.replace('header', str(item['content']) + '_p1')})
                    listitems.append({'type': 'path', 'label': str(item['content']), 'url': url})
        elif 'listing' in page:
            if 'isPaginated' in page['listing']:
                curr_page = page['listing']['currPage']
                page_count = page['listing']['pages']
            if 'asset_listing' in page['listing']:
                listitems = self.getAssets(page['listing']['asset_listing']['asset'])
            elif 'listing' in page['listing']:
                listing_type = page['listing'].get('type', '')
                # SportClips
                if listing_type == 'ClipsListing':
                    listitems = self.getAssets(page['listing']['listing']['item'], key='type')
                # SportReplays
                elif 'asset' in page['listing']['listing']:
                    listitems = self.getAssets(page['listing']['listing']['asset'])
                elif 'item' in page['listing']['listing']:
                    if isinstance(page['listing']['listing']['item'], list):
                        # Zeige nur A-Z Sortierung
                        if self.checkForLexic(page['listing']['listing']['item']):
                            path = page['listing']['listing']['item'][0]['path'].replace('header.json', 'sort_by_lexic_p1.json')
                            self.listPath(path)
                            return []
                        for item in page['listing']['listing']['item']:
                            if not 'asset_type' in item and 'path' in item:
                                url = self.common.build_url({'action': 'listPage', 'path': item['path']})
                                listitems.append({'type': 'listPage', 'label': item['title'], 'url': url})
                    else:
                        self.listPath(page['listing']['listing']['item']['path'])

        if curr_page < page_count:
            url = self.common.build_url({'action': 'listPage', 'path': path.replace('_p' + str(curr_page), '_p' + str(curr_page + 1))})
            listitems.append({'type': 'path', 'label': 'Mehr...', 'url': url})

        return listitems


    def buildLiveEventTag(self, event_info):
        tag = ''
        dayDict = {'Monday': 'Montag', 'Tuesday': 'Dienstag', 'Wednesday': 'Mittwoch', 'Thursday': 'Donnerstag', 'Friday': 'Freitag', 'Saturday': 'Samstag', 'Sunday': 'Sonntag'}
        if event_info != '':
            now = datetime.datetime.now()

            strStartTime = '%s %s' % (event_info['start_date'], event_info['start_time'])
            strEndTime = '%s %s' % (event_info['end_date'], event_info['end_time'])
            start_time = datetime.datetime.fromtimestamp(time.mktime(time.strptime(strStartTime, "%Y/%m/%d %H:%M")))
            end_time = datetime.datetime.fromtimestamp(time.mktime(time.strptime(strEndTime, "%Y/%m/%d %H:%M")))

            if (now >= start_time) and (now <= end_time):
                tag = '[COLOR red][Live][/COLOR]'
            elif start_time.date() == datetime.datetime.today().date():
                tag = '[COLOR blue][Heute ' + event_info['start_time'] + '][/COLOR]'
            elif start_time.date() == (datetime.datetime.today() + datetime.timedelta(days=1)).date():
                tag = '[COLOR blue][Morgen ' + event_info['start_time'] + '][/COLOR]'
            else:
                day = start_time.strftime('%A')
                if not day in dayDict.values():
                    day = day.replace(day, dayDict[day])[0:2]
                tag = '[COLOR blue][' + day + ', ' + start_time.strftime("%d.%m %H:%M]") + '[/COLOR]'

        return tag


    def getInfoLabel(self, asset_type, item_data):
        data = item_data
        if data.get('mediainfo'):
            data = data.get('mediainfo')
        elif data.get('id') and self.extMediaInfos and self.extMediaInfos == 'true':
            asset = self.getAssetDetailsFromCache(data.get('id'))
            if len(asset) > 0:
                data = asset

        info = {}
        info['title'] = data.get('title', '')
        info['originaltitle'] = data.get('original_title', '')
        if data.get('year_of_production', '') != '':
            info['year'] = data.get('year_of_production', '')
        info['plot'] = data.get('synopsis', '').replace('\n', '').strip()
        if info['plot'] == '':
            info['plot'] = data.get('description', '').replace('\n', '').strip()
        if data.get('technical_event', {}).get('on_air', {}).get('end_date', '') != '':
            string_end_date = data.get('technical_event', {}).get('on_air', {}).get('end_date', '')
            split_end_date = string_end_date.split('/')
            if len(split_end_date) == 3:
                info['plot'] = 'Verfügbar bis {0}.{1}.{2}\n\n{3}'.format(split_end_date[2], split_end_date[1], split_end_date[0], info.get('plot', ''))
        info['duration'] = data.get('lenght', 0) * 60
        if data.get('main_trailer', {}).get('trailer', {}).get('url', '') != '':
            info['trailer'] = data.get('main_trailer', {}).get('trailer', {}).get('url', '')
        if data.get('cast_list', {}).get('cast', {}) != '':
            cast_list = []
            castandrole_list = []
            for cast in data.get('cast_list', {}).get('cast', {}):
                if cast['type'] == 'Darsteller':
                    if cast['character'] != '':
                        char = re.search('(.*)\(', cast['content']).group(1).strip() if re.search('(.*)\(', cast['content']) else ''
                        castandrole_list.append((char, cast['character']))
                    else:
                        cast_list.append(cast['content'])
                elif cast['type'] == 'Regie':
                    info['director'] = cast['content']
            if len(castandrole_list) > 0:
                info['castandrole'] = castandrole_list
            else:
                info['cast'] = cast_list
        if data.get('genre', {}) != '':
            category_list = []
            for category in data.get('genre', {}):
                if 'content' in data.get('genre', {}).get(category, {}) and not data.get('genre', {}).get(category, {}).get('content', {}) in category_list:
                    category_list.append(data.get('genre', {}).get(category, {}).get('content', {}))
            info['genre'] = ", ".join(category_list)

        if asset_type == 'Sport' and data.get('current_type', '') == 'Live':
            # LivePlanner listing
            info['title'] = self.buildLiveEventTag(data['technical_event']['on_air']) + ' ' + info['title']
            info['plot'] = data.get('title', '')
        if asset_type == 'Clip':
            info['title'] = data['item_title']
            info['plot'] = data.get('teaser_long', '')
            info['genre'] = data.get('item_category_name', '')
        if asset_type == 'live':
            if item_data['channel']['name'].startswith("Sky Sport"):
                info['title'] = item_data['event'].get('subtitle', '')
            if info['title'] == '':
                info['title'] = item_data['event'].get('title', '')
            info['plot'] = data.get('synopsis', '').replace('\n', '').strip() if data.get('synopsis', '') != '' else item_data['event'].get('subtitle', '')
            if not item_data['channel']['name'].startswith('Sky Sport'):
                if 'mediainfo' in item_data:
                    info['title'] = data.get('title', '')
                    info['plot'] = data.get('synopsis', '').replace('\n', '').strip()
                else:
                    if item_data['channel']['name'].lower().find('cinema') >= 0 or item_data['channel']['color'].lower() == 'film':
                        info['title'] = item_data.get('event', '').get('title', '')
                        data['title'] = info['title']
                        info['plot'] = item_data.get('event', '').get('subtitle', '')
                        asset_type = 'Film'
                    else:
                        info['title'] = '[COLOR blue]{0}[/COLOR] {1}'.format(item_data.get('event', '').get('title', ''), item_data['event'].get('subtitle', ''))
                    info['duration'] = item_data.get('event', '').get('length', 0) * 60
                if data.get('type', '') == 'Film':
                    asset_type = 'Film'
                elif data.get('type', '') == 'Episode':
                    asset_type = 'Episode'
                    info['plot'] = data.get('synopsis', '').replace('\n', '').strip()
                    info['title'] = '[COLOR blue]{0}[/COLOR] {1}'.format(data.get('serie_title', ''), data.get('title', ''))
            if self.addon.getSetting('channel_name_first') == 'true':
                item_data['li_label'] = '[COLOR orange]{0}[/COLOR] {1}'.format(item_data['channel']['name'], info['title'])
            else:
                item_data['li_label'] = '{0} [COLOR orange]{1}[/COLOR]'.format(info['title'], item_data['channel']['name'])

            info['plot'] = '{0} - {1}\n\n{2}'.format(item_data.get('event').get('startTime'), item_data.get('event').get('endTime'), info['plot'])
        if asset_type == 'searchresult':
            if self.extMediaInfos and self.extMediaInfos == 'false':
                info['plot'] = data.get('description', '')
                info['year'] = data.get('year', '')
                info['genre'] = data.get('category', '')
            if data.get('type', {}) == 'Film':
                asset_type = 'Film'
            elif data.get('type', '') == 'Episode':
                asset_type = 'Episode'
                info['plot'] = 'Folge: {0}\n\n{1}'.format(data.get('title', ''), data.get('synopsis', '').replace('\n', '').strip())
                info['title'] = data.get('title', '')
                item_data['li_label'] = '{0:01d}x{1:02d}. {2}'.format(data.get('season_nr', ''), data.get('episode_nr', ''), data.get('serie_title', ''))
        if asset_type == 'Film':
            info['mediatype'] = 'movie'
            if self.addon.getSetting('lookup_tmdb_data') == 'true' and not data.get('title', '') == '':
                title = py2_encode(data.get('title', ''))
                xbmc.log(py2_encode('Searching Rating and better Poster for "{0}" at tmdb.com').format(title))
                if data.get('year_of_production', '') != '':
                    TMDb_Data = self.getTMDBDataFromCache(title, info['year'])
                else:
                    TMDb_Data = self.getTMDBDataFromCache(title)

                if len(TMDb_Data) > 0:
                    if TMDb_Data.get('rating'):
                        info['rating'] = TMDb_Data['rating']
                        info['plot'] = 'User-Rating: {0} / 10 (from TMDb) \n\n{1}'.format(info['rating'], info['plot'])
                        xbmc.log("Result of get Rating: {0}".format(TMDb_Data['rating']))
                    if TMDb_Data.get('poster_path'):
                        item_data['TMDb_poster_path'] = TMDb_Data['poster_path']
                        xbmc.log("Path to TMDb Picture: {0}".format(TMDb_Data['poster_path']))
        if asset_type == 'Series':
            info['year'] = data.get('year_of_production_start', '')
        if asset_type == 'Episode':
            info['mediatype'] = 'episode'
            info['episode'] = data.get('episode_nr', '')
            info['season'] = data.get('season_nr', '')
            info['tvshowtitle'] = data.get('serie_title', '')
            if info['title'] == '':
                info['title'] = data.get('episode_nr', 0)
                item_data['li_label'] = '{0} - S{1:02d}E{2:02d}'.format(data.get('serie_title', ''), data.get('season_nr', 0), data.get('episode_nr', 0))

        return info, item_data


    def getWatchlistContextItem(self, item, delete=False):
        label = 'Zur Merkliste hinzufügen'
        action = 'watchlistAdd'
        asset_type = item['type']
        ids = []
        if delete:
            label = 'Von Merkliste entfernen'
            action = 'watchlistDel'
        if asset_type == 'searchresult':
            asset_type = item['data']['contentType']
        if delete == False and asset_type == 'Episode' and len(item.get('data').get('episodes', {})) > 0:
            for episode in item.get('data').get('episodes').get('episode'):
                ids.append(str(episode.get('id')))
        else:
            ids.append(str(item['data']['id']))

        url = self.common.build_url({'action': action, 'id': ','.join(ids), 'assetType': asset_type})
        return (label, 'RunPlugin(' + url + ')')


    def listAssets(self, asset_list, isWatchlist=False):
        for item in asset_list:
            isPlayable = False
            additional_params = {}
            li = xbmcgui.ListItem(label=item['label'])
            if item['type'] in ['Film', 'Episode', 'Sport', 'Clip', 'Series', 'live', 'searchresult', 'Season']:
                isPlayable = True
                # Check Altersfreigabe / Jugendschutzeinstellungen
                parental_rating = 0
                if 'parental_rating' in item['data']:
                    parental_rating = item['data']['parental_rating']['value']
                    if self.js_showall == 'false':
                        if not self.skygo.parentalCheck(parental_rating, play=False):
                            continue
                info, item['data'] = self.getInfoLabel(item['type'], item['data'])
                li.setInfo('video', info)
                additional_params.update({'infolabels': info, 'parental_rating': parental_rating})
                li.setLabel(item.get('data').get('li_label') if item.get('data').get('li_label', None) else info['title'])
                # if item['type'] not in ['Series', 'Season']:
                #    li = self.addStreamInfo(li, item['data'])

            if item['type'] in ['Film']:
                xbmcplugin.setContent(self.skygo.addon_handle, 'movies')
            elif item['type'] in ['Series', 'Season']:
                xbmcplugin.setContent(self.skygo.addon_handle, 'tvshows')
                isPlayable = False
            elif item['type'] in ['Episode']:
                xbmcplugin.setContent(self.skygo.addon_handle, 'episodes')
            elif item['type'] in ['Sport', 'Clip']:
                xbmcplugin.setContent(self.skygo.addon_handle, 'files')
            elif item['type'] == 'searchresult':
                xbmcplugin.setContent(self.skygo.addon_handle, 'movies')
            elif item['type'] == 'live':
                xbmcplugin.setContent(self.skygo.addon_handle, 'files')
                if 'TMDb_poster_path' in item['data'] or ('mediainfo' in item['data'] and not item['data']['channel']['name'].startswith('Sky Sport')):
                    xbmcplugin.setContent(self.skygo.addon_handle, 'movies')

            contextmenuitems = []
            if item['type'] in ['Film', 'Series', 'Season', 'Episode', 'live']:
                contextmenuitems.append(('Aktualisieren', 'RunPlugin({0})'.format(self.common.build_url({'action': 'refresh'}))))

            # add contextmenu item for watchlist to playable content - not for live and clip content
            if isPlayable and not item['type'] in ['live', 'Clip']:
                contextmenuitems.append(self.getWatchlistContextItem(item, isWatchlist))
            elif item['type'] == 'Season':
                contextmenuitems.append(self.getWatchlistContextItem({'type': 'Episode', 'data': item['data']}, False))

            if len(contextmenuitems) > 0:
                li.addContextMenuItems(contextmenuitems)

            li.setProperty('IsPlayable', str(isPlayable).lower())

            art = self.getArt(item)
            if len(art) > 0:
                additional_params.update({'art': art})
                li.setArt(art)

            parsed_url = urlparse.urlparse(item['url'])
            params = dict(urlparse.parse_qsl(parsed_url.query))
            params.update(additional_params)
            url = self.common.build_url(params)

            xbmcplugin.addDirectoryItem(handle=self.skygo.addon_handle, url=url, listitem=li, isFolder=(not isPlayable))


    def listPath(self, path):
        page = {}
        path = path.replace('ipad', 'web')
        r = self.skygo.session.get(self.skygo.baseUrl + path)
        if self.common.get_dict_value(r.headers, 'content-type').startswith('application/json'):
            page = r.json()
        else:
            xbmcplugin.endOfDirectory(self.skygo.addon_handle, cacheToDisc=True)
            return False
        if 'sort_by_lexic_p' in path:
            url = self.common.build_url({'action': 'listPage', 'path': path[0:path.index('sort_by_lexic_p')] + 'header.json'})
            self.addDir('[A-Z]', url)

        listitems = self.parseListing(page, path)
        self.listAssets(listitems)

        xbmcplugin.endOfDirectory(self.skygo.addon_handle, cacheToDisc=True)


    def getPageItems(self, nodes, page_id):
        listitems = []
        for section in nodes.iter('section'):
            if section.attrib['id'] == page_id:
                for item in section:
                    if int(item.attrib['id']) in self.nav_blacklist:
                        continue
                    listitems.append(item)

        return listitems


    def getParentNode(self, nodes, page_id):
        for item in nodes.iter('section'):
            if item.attrib['id'] == page_id:
                return item
        return None


    def listPage(self, page_id):
        nav = self.getNav()
        items = self.getPageItems(nav, page_id)
        if len(items) == 1:
            if 'path' in items[0].attrib:
                self.listPath(items[0].attrib['path'])
                return
        for item in items:
            url = ''
            if item.tag == 'item':
                url = self.common.build_url({'action': 'listPage', 'path': item.attrib['path']})
            elif item.tag == 'section':
                url = self.common.build_url({'action': 'listPage', 'id': item.attrib['id']})

            self.addDir(item.attrib['label'], url)

        xbmcplugin.endOfDirectory(self.skygo.addon_handle, cacheToDisc=True)


    def getAssetDetailsFromCache(self, asset_id):
        return self.assetDetailsCache.cacheFunction(self.skygo.getAssetDetails, asset_id)


    def getTMDBDataFromCache(self, title, year=None, attempt=1, content='movie'):
        return self.TMDBCache.cacheFunction(self.getTMDBData, title, year, attempt, content)


    def getTMDBData(self, title, year=None, attempt=1, content='movie'):
        # This product uses the TMDb API but is not endorsed or certified by TMDb.
        rating = None
        poster_path = None
        tmdb_id = None
        splitter = [' - ', ': ', ', ']
        tmdb_api = base64.b64decode('YTAwYzUzOTU0M2JlMGIwODE4YmMxOTRhN2JkOTVlYTU=')  # ApiKey Linkinsoldier
        lang = 'de'
        # str_year = year if year else ''
        title = re.sub('(\(.*\))', '', title).strip()

        if attempt > 3:
            return {}

        try:
            # Define the moviedb Link zu download the json
            url = 'https://api.themoviedb.org/3/search/{0}?{1}'.format(content, urllib.urlencode({
                'api_key': tmdb_api,
                'language': lang,
                'query': title,
                'year': year if year else ''
            }))
            # Download and load the corresponding json
            data = json.load(urlopen(url))

            if data['total_results'] > 0:
                if data['total_results'] > 1:
                    results = [r for r in data['results'] if py2_encode(r.get('title')) == title]
                    if len(results) == 1:
                        result = results[0]
                    else:
                        result = data['results'][0]
                else:
                    result = data['results'][0]

                if result['vote_average']:
                    rating = float(result['vote_average'])
                if result['poster_path']:
                    poster_path = 'https://image.tmdb.org/t/p/w500{0}'.format(result['poster_path'])
                tmdb_id = result['id']
            elif year is not None:
                attempt += 1
                xbmc.log(py2_encode('Try again - without release year - to find Title: {0}').format(title))
                return self.getTMDBData(title, None, attempt)
            elif py2_decode(title).find('-') > -1:
                attempt += 1
                title = title.split('-')[0].strip()
                xbmc.log(py2_encode('Try again - find Title: {0}').format(title))
                return self.getTMDBData(title, None, attempt)
            else:
                xbmc.log(py2_encode('No movie found with Title: {0}').format(title))

        except URLError as e:
            xbmc.log('Error reason: {0}'.format(e))

            if '429' or 'timed out' in e:
                attempt += 1
                xbmc.log('Attempt #{0} - Too many requests - Pause 5 sec'.format(attempt))
                xbmc.sleep(5000)
                if attempt < 4:
                    return self.getTMDBData(title, year, attempt)

            return {'tmdb_id': tmdb_id, 'title': title, 'rating': rating , 'poster_path': poster_path}
        return {'tmdb_id': tmdb_id, 'title': title, 'rating': rating , 'poster_path': poster_path}


    def addStreamInfo(self, listitem, data):
        if 'channel' in data and data.get('channel').get('name').startswith('Sky Sport'):
            listitem.addStreamInfo('video', {'codec': 'h264', 'width': 1280, 'height': 720})
        else:
            if 'mediainfo' in data:
                data = data.get('mediainfo')
            if 'hd' in data:
                if data.get('hd') == 'yes':
                    listitem.addStreamInfo('video', {'codec': 'h264', 'width': 1280, 'height': 720})
                else:
                    listitem.addStreamInfo('video', {'codec': 'h264', 'width': 960, 'height': 540})

        listitem.addStreamInfo('audio', {'codec': 'aac', 'channels': 2})

        return listitem


    def clearCache(self):
        try:
            self.assetDetailsCache.delete("%")
            self.TMDBCache.delete("%")
            xbmcgui.Dialog().notification('Sky Go: Cache', 'Leeren des Caches erfolgreich', xbmcgui.NOTIFICATION_INFO, 2000, True)
        except:
            xbmcgui.Dialog().notification('Sky Go: Cache', 'Leeren des Caches fehlgeschlagen', xbmcgui.NOTIFICATION_ERROR, 2000, True)


    def getArt(self, item):
        art = {}

        if item['type'] in ['Film', 'Episode', 'Sport', 'Clip', 'Series', 'live', 'searchresult', 'Season']:
            art.update({'poster': self.getPoster(item['data']), 'fanart': self.getHeroImage(item['data'])})
        if item['type'] in ['Film']:
            if self.addon.getSetting('lookup_tmdb_data') == 'true' and 'TMDb_poster_path' in item['data']:
                poster_path = item['data']['TMDb_poster_path']
            else:
                poster_path = self.getPoster(item['data'])
            art.update({'poster': poster_path})
        elif item['type'] in ['Sport', 'Clip']:
            thumb = self.getHeroImage(item['data'])
            art.update({'thumb': thumb})
            if item.get('data').get('current_type', '') == 'Live':
                art.update({'poster': thumb})
        elif item['type'] == 'searchresult':
            if self.addon.getSetting('lookup_tmdb_data') == 'true' and 'TMDb_poster_path' in item['data']:
                poster_path = item['data']['TMDb_poster_path']
            else:
                poster_path = self.getPoster(item['data'])
            art.update({'poster': poster_path})
        elif item['type'] == 'live':
            poster = self.skygo.baseUrl + item['data']['event']['image'] if item['data']['channel']['name'].find('News') == -1 else self.getChannelLogo(item['data']['channel'])
            fanart = self.skygo.baseUrl + item['data']['event']['image'] if item['data']['channel']['name'].find('News') == -1 else self.skygo.baseUrl + '/bin/Picture/817/C_1_Picture_7179_content_4.jpg'
            thumb = poster

            if 'TMDb_poster_path' in item['data'] or ('mediainfo' in item['data'] and not item['data']['channel']['name'].startswith('Sky Sport')):
                if 'TMDb_poster_path' in item['data']:
                    poster = item['data']['TMDb_poster_path']
                else:
                    poster = self.getPoster(item['data']['mediainfo'])
                thumb = poster
                xbmcplugin.setContent(self.skygo.addon_handle, 'movies')

            art.update({'poster':  poster + '|User-Agent=' + self.skygo.user_agent, 'fanart': fanart + '|User-Agent=' + self.skygo.user_agent, 'thumb': thumb + '|User-Agent=' + self.skygo.user_agent})

        return art
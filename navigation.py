#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import xbmc, xbmcgui, xbmcplugin, xbmcaddon, xbmcvfs

import urllib2
import json
import datetime
import _strptime
import time
import xml.etree.ElementTree as ET
import resources.lib.common as common
import watchlist
import re
import urllib
import urlparse
import base64

try:
    import StorageServer
except:
    import storageserverdummy as StorageServer

addon = xbmcaddon.Addon()

# Doc for Caching Function: http://kodi.wiki/index.php?title=Add-on:Common_plugin_cache
assetDetailsCache = StorageServer.StorageServer(addon.getAddonInfo('name') + '.assetdetails', 24 * 30)
TMDBCache = StorageServer.StorageServer(addon.getAddonInfo('name') + '.TMDBdata', 24 * 30)

extMediaInfos = addon.getSetting('enable_extended_mediainfos')
icon_file = xbmc.translatePath(addon.getAddonInfo('path') + '/icon.png').decode('utf-8')
skygo = None

# Blacklist: diese nav_ids nicht anzeigen
# 15 = Snap
# Live Planer: 154 = Inside Report, 268 = Europa League, 262 = Sky Go Erste Liga, 290 = Audi Star Talk, 159 = X-Treme
nav_blacklist = [15, 35, 154, 268, 262, 290, 159]

# Jugendschutz
js_showall = addon.getSetting('js_showall')


def getNav():
    opener = urllib2.build_opener()
    opener.addheaders = [('User-Agent', skygo.user_agent)]
    feed = opener.open(skygo.baseUrl + skygo.baseServicePath + '/multiplatform/ipad/json/navigation.xml')
    nav = ET.parse(feed)
    return nav.getroot()


def liveChannelsDir():
    url = common.build_url({'action': 'listLiveTvChannelDirs'})
    addDir('Livesender', url)


def watchlistDir():
    url = common.build_url({'action': 'watchlist'})
    addDir('Merkliste', url)


def rootDir():
    nav = getNav()
    # Livesender
    liveChannelsDir()
    # Navigation der Ipad App
    for item in nav:
        if item.attrib['hide'] == 'true' or item.tag == 'item':
            continue
        url = common.build_url({'action': 'listPage', 'id': item.attrib['id']})
        addDir(item.attrib['label'], url)

    # Merkliste
    watchlistDir()
    # Suchfunktion
    url = common.build_url({'action': 'search'})
    addDir('Suche', url)

    xbmcplugin.endOfDirectory(skygo.addon_handle, cacheToDisc=True)


def addDir(label, url, icon=icon_file):
    li = xbmcgui.ListItem(label)
    li.setArt({'icon': icon, 'thumb': icon_file})
    xbmcplugin.addDirectoryItem(handle=skygo.addon_handle, url=url, listitem=li, isFolder=True)


def showParentalSettings():
    fsk_list = ['Deaktiviert', '0', '6', '12', '16', '18']
    dlg = xbmcgui.Dialog()
    code = dlg.input('PIN Code', type=xbmcgui.INPUT_NUMERIC)
    if skygo.encode(code) == addon.getSetting('password'):
        idx = dlg.select('Wähle maximale FSK Alterstufe', fsk_list)
        if idx >= 0:
            fsk_code = fsk_list[idx]
            if fsk_code == 'Deaktiviert':
                addon.setSetting('js_maxrating', '-1')
            else:
                addon.setSetting('js_maxrating', fsk_list[idx])
        if idx > 0:
            if dlg.yesno('Jugendschutz', 'Sollen Inhalte mit einer Alterseinstufung über ', 'FSK ' + fsk_list[idx] + ' angezeigt werden?'):
                addon.setSetting('js_showall', 'true')
            else:
                addon.setSetting('js_showall', 'false')
    else:
        xbmcgui.Dialog().notification('Sky Go: Jugendschutz', 'Fehlerhafte PIN', xbmcgui.NOTIFICATION_ERROR, 2000, True)


def getHeroImage(data):
    if 'main_picture' in data:
        for pic in data['main_picture']['picture']:
            if pic['type'] == 'hero_img':
                return skygo.baseUrl + pic['path'] + '/' + pic['file'] + '|User-Agent=' + skygo.user_agent
    if 'item_image' in data:
        return skygo.baseUrl + data['item_image'] + '|User-Agent=' + skygo.user_agent
    if 'picture' in data:
        return skygo.baseUrl + data['picture'] + '|User-Agent=' + skygo.user_agent

    return ''


def getPoster(data):
    if 'name' in data and addon.getSetting('enable_customlogos') == 'true':
        img = getLocalChannelLogo(data['name'])
        if img:
            return img

    if data.get('dvd_cover', '') != '':
        return skygo.baseUrl + data['dvd_cover']['path'] + '/' + data['dvd_cover']['file'] + '|User-Agent=' + skygo.user_agent
    if data.get('item_preview_image', '') != '':
        return skygo.baseUrl + data['item_preview_image'] + '|User-Agent=' + skygo.user_agent
    if data.get('picture', '') != '':
        return skygo.baseUrl + data['picture'] + '|User-Agent=' + skygo.user_agent
    if data.get('logo', '') != '':
        return skygo.baseUrl + data['logo'] + '|User-Agent=' + skygo.user_agent

    return ''


def getChannelLogo(data):
    logopath = ''
    if 'channelLogo' in data:
        basepath = data['channelLogo']['basepath'] + '/'
        size = 0
        for logo in data['channelLogo']['logos']:
            logosize = logo['size'][:logo['size'].find('x')]
            if int(logosize) > size:
                size = int(logosize)
                logopath = skygo.baseUrl + basepath + logo['imageFile'] + '|User-Agent=' + skygo.user_agent
    return logopath


def getLocalChannelLogo(channel_name):
    logo_path = addon.getSetting('logoPath')
    if not logo_path == '' and xbmcvfs.exists(logo_path):
        dirs, files = xbmcvfs.listdir(logo_path)
        for f in files:
            if f.lower().endswith('.png'):
                if channel_name.lower().replace(' ', '') == os.path.basename(f).lower().replace('.png', '').replace(' ', ''):
                    return os.path.join(logo_path, f)

    return None


def search():
    dlg = xbmcgui.Dialog()
    term = dlg.input('Suchbegriff', type=xbmcgui.INPUT_ALPHANUM)
    if term == '':
        return
    term = term.replace(' ', '+')
    url = 'https://www.skygo.sky.de/SILK/services/public/search/web?searchKey=' + term + '&version=12354&platform=web&product=SG'
    r = skygo.session.get(url)
    if common.get_dict_value(r.headers, 'content-type').startswith('application/json'):
        data = json.loads(r.text[3:len(r.text) - 1])
        listitems = []
        for item in data['assetListResult']:
            url = common.build_url({'action': 'playVod', 'vod_id': item['id']})
            listitems.append({'type': 'searchresult', 'label': item['title'], 'url': url, 'data': item})

#    if data['assetListResult']['hasNext']:
#        url = common.build_url({'action': 'listPage', 'path': ''})
#        listitems.append({'type': 'path', 'label': 'Mehr...', 'url': url})

        listAssets(listitems)

    xbmcplugin.endOfDirectory(skygo.addon_handle, cacheToDisc=True)


def listLiveTvChannelDirs():
    channels = ['bundesliga', 'cinema', 'entertainment', 'sport']
    for channel in channels:
        url = common.build_url({'action': 'listLiveTvChannels', 'channeldir_name': channel})
        li = xbmcgui.ListItem(label=channel.title(), iconImage=icon_file, thumbnailImage=icon_file)
        xbmcplugin.addDirectoryItem(handle=skygo.addon_handle, url=url, listitem=li, isFolder=True)

    xbmcplugin.endOfDirectory(skygo.addon_handle, cacheToDisc=True)


def listLiveTvChannels(channeldir_name):
    if addon.getSetting('show_refresh') == 'true':
        url = common.build_url({'action': 'refresh'})
        li = xbmcgui.ListItem(label='Aktualisieren', iconImage=icon_file, thumbnailImage=icon_file)
        xbmcplugin.addDirectoryItem(handle=skygo.addon_handle, url=url, listitem=li, isFolder=False)

    data = getlistLiveChannelData(channeldir_name)
    for tab in data:
        if tab['tabName'].lower() == channeldir_name.lower():
            details = getLiveChannelDetails(tab.get('eventList'), None)
            listAssets(sorted(details.values(), key=lambda k:k['data']['channel']['name']))

    xbmcplugin.endOfDirectory(skygo.addon_handle, cacheToDisc=False)


def getlistLiveChannelData(channel=None):
    data = {}
    r = skygo.session.get(skygo.baseUrl + '/epgd' + skygo.baseServicePath + '/ipad/excerpt/')
    if common.get_dict_value(r.headers, 'content-type').startswith('application/json'):
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

            r = skygo.session.get(skygo.baseUrl + '/epgd' + skygo.baseServicePath + '/web/excerpt/')
            if common.get_dict_value(r.headers, 'content-type').startswith('application/json'):
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
                                    try:
                                        media_url = getAssetDetailsFromCache(event_web['event']['assetid']).get('media_url', None)
                                        if media_url and media_url.startswith('http'):
                                            msMediaUrl = media_url
                                    except:
                                        pass

                                if msMediaUrl:
                                    channel_list.append(event_web['channel']['name'])
                                    event_web['channel']['msMediaUrl'] = msMediaUrl
                                    tab['eventList'].append(event_web)

    if len(data) == 0:
        xbmcgui.Dialog().notification('Sky Go: Datenabruf', 'Es konnten keine Daten geladen werden', xbmcgui.NOTIFICATION_ERROR, 3000, True)

    return sorted(data, key=lambda k: k['tabName'])


def getLiveChannelDetails(eventlist, s_manifest_url=None):
    details = {}
    for event in eventlist:
        url = None
        manifest_url = None

        if event['channel'].get('msMediaUrl', None) and event['channel']['msMediaUrl'].startswith('http'):
            manifest_url = event['channel']['msMediaUrl']
            url = common.build_url({'action': 'playLive', 'manifest_url': manifest_url, 'package_code': event['channel']['mobilepc']})
        elif s_manifest_url is None and event['event'].get('assetid', None):
            try:
                if event['event']['assetid'] > 0 and extMediaInfos and extMediaInfos == 'true':
                    mediainfo = getAssetDetailsFromCache(event['event']['assetid'])
                    if mediainfo:
                        event['mediainfo'] = mediainfo
            except:
                pass

            url = common.build_url({'action': 'playVod', 'vod_id': event['event']['assetid']})

        if 'mediainfo' not in event and extMediaInfos and extMediaInfos == 'true':
            assetid_match = re.search('\/(\d+)\.html', event['event']['detailPage'])
            if assetid_match:
                assetid = 0
                try:
                    assetid = int(assetid_match.group(1))
                except:
                    pass
                try:
                    if assetid > 0:
                        mediainfo = getAssetDetailsFromCache(assetid)
                        if mediainfo:
                            event['mediainfo'] = mediainfo
                            if not manifest_url or not manifest_url.startswith('http'):
                                manifest_url = mediainfo['media_url']
                            if not manifest_url or not manifest_url.startswith('http'):
                                continue
                except:
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

            if s_manifest_url:
                if s_manifest_url == manifest_url:
                    return {detail: details[detail]}

    return {} if s_manifest_url else details


def listEpisodesFromSeason(series_id, season_id):
    url = skygo.baseUrl + skygo.baseServicePath + '/multiplatform/web/json/details/series/' + str(series_id) + '_global.json'
    r = skygo.session.get(url)
    if common.get_dict_value(r.headers, 'content-type').startswith('application/json'):
        data = r.json()['serieRecap']['serie']
        xbmcplugin.setContent(skygo.addon_handle, 'episodes')
        for season in data['seasons']['season']:
            if str(season['id']) == str(season_id):
                for episode in season['episodes']['episode']:
                    # Check Altersfreigabe / Jugendschutzeinstellungen
                    parental_rating = 0
                    if 'parental_rating' in episode:
                        parental_rating = episode['parental_rating']['value']
                        if js_showall == 'false':
                            if not skygo.parentalCheck(parental_rating, play=False):
                                continue
                    li = xbmcgui.ListItem()
                    li.setProperty('IsPlayable', 'true')
                    li.addContextMenuItems(getWatchlistContextItem({'type': 'Episode', 'data': episode}), replaceItems=False)
                    info, episode = getInfoLabel('Episode', episode)
                    li.setInfo('video', info)
                    li.setLabel(episode.get('li_label') if episode.get('li_label', None) else info['title'])
                    # li = addStreamInfo(li, episode)
                    art = {'poster': skygo.baseUrl + season['path'] + '|User-Agent=' + skygo.user_agent,
                            'fanart': getHeroImage(data),
                            'thumb': skygo.baseUrl + episode['webplayer_config']['assetThumbnail'] + '|User-Agent=' + skygo.user_agent}
                    li.setArt(art)
                    url = common.build_url({'action': 'playVod', 'vod_id': episode['id'], 'infolabels': info, 'parental_rating': parental_rating, 'art': art})
                    xbmcplugin.addDirectoryItem(handle=skygo.addon_handle, url=url, listitem=li, isFolder=False)

        xbmcplugin.addSortMethod(skygo.addon_handle, sortMethod=xbmcplugin.SORT_METHOD_EPISODE)

    xbmcplugin.endOfDirectory(skygo.addon_handle, cacheToDisc=True)


def listSeasonsFromSeries(series_id):
    url = skygo.baseUrl + skygo.baseServicePath + '/multiplatform/web/json/details/series/' + str(series_id) + '_global.json'
    r = skygo.session.get(url)
    if common.get_dict_value(r.headers, 'content-type').startswith('application/json'):
        data = r.json()['serieRecap']['serie']
        xbmcplugin.setContent(skygo.addon_handle, 'tvshows')
        for season in data['seasons']['season']:
            url = common.build_url({'action': 'listSeason', 'id': season['id'], 'series_id': data['id']})
            label = '%s - Staffel %02d' % (data['title'], season['nr'])
            li = xbmcgui.ListItem(label=label)
            li.setProperty('IsPlayable', 'false')
            li.setArt({'poster': skygo.baseUrl + season['path'] + '|User-Agent=' + skygo.user_agent,
                       'fanart': getHeroImage(data),
                       'thumb': icon_file})
            li.setInfo('video', {'plot': data['synopsis'].replace('\n', '').strip()})
            li.addContextMenuItems(getWatchlistContextItem({'type': 'Episode', 'data': season}, False), replaceItems=False)
            xbmcplugin.addDirectoryItem(handle=skygo.addon_handle, url=url, listitem=li, isFolder=True)

    xbmcplugin.endOfDirectory(skygo.addon_handle, cacheToDisc=True)


def getAssets(data, key='asset_type'):
    asset_list = []
    for asset in data:
        if asset[key].lower() in ['film', 'episode', 'sport']:
            url = common.build_url({'action': 'playVod', 'vod_id': asset['id']})
            asset_list.append({'type': asset[key], 'label': '', 'url': url, 'data': asset})
        elif asset[key].lower() == 'clip':
            url = common.build_url({'action': 'playClip', 'id': asset['id']})
            asset_list.append({'type': asset[key], 'label': '', 'url': url, 'data': asset})
        elif asset[key].lower() == 'series':
            url = common.build_url({'action': 'listSeries', 'id': asset['id']})
            asset_list.append({'type': asset[key], 'label': asset['title'], 'url': url, 'data': asset})
        elif asset[key].lower() == 'season':
            url = skygo.baseUrl + skygo.baseServicePath + '/multiplatform/web/json/details/series/' + str(asset['serie_id']) + '_global.json'
            r = skygo.session.get(url)
            if common.get_dict_value(r.headers, 'content-type').startswith('application/json'):
                serie = r.json()['serieRecap']['serie']
                asset['synopsis'] = serie['synopsis']
                for season in serie['seasons']['season']:
                    if season['id'] == asset['id']:
                        asset['episodes'] = season['episodes']
                url = common.build_url({'action': 'listSeason', 'id': asset['id'], 'series_id': asset['serie_id']})
                asset_list.append({'type': asset[key], 'label': asset['title'], 'url': url, 'data': asset})

    return asset_list


def checkForLexic(listing):
    if len(listing) == 2:
        if 'ByLexic' in listing[0]['structureType'] and 'ByYear' in listing[1]['structureType']:
            return True

    return False


def parseListing(page, path):
    listitems = []
    curr_page = 1
    page_count = 1
    if 'letters' in page:
        for item in page['letters']['letter']:
            if item['linkable'] is True:
                url = common.build_url({'action': 'listPage', 'path': path.replace('header', str(item['content']) + '_p1')})
                listitems.append({'type': 'path', 'label': str(item['content']), 'url': url})
    elif 'listing' in page:
        if 'isPaginated' in page['listing']:
            curr_page = page['listing']['currPage']
            page_count = page['listing']['pages']
        if 'asset_listing' in page['listing']:
            listitems = getAssets(page['listing']['asset_listing']['asset'])
        elif 'listing' in page['listing']:
            listing_type = page['listing'].get('type', '')
            # SportClips
            if listing_type == 'ClipsListing':
                listitems = getAssets(page['listing']['listing']['item'], key='type')
            # SportReplays
            elif 'asset' in page['listing']['listing']:
                listitems = getAssets(page['listing']['listing']['asset'])
            elif 'item' in page['listing']['listing']:
                if isinstance(page['listing']['listing']['item'], list):
                    # Zeige nur A-Z Sortierung
                    if checkForLexic(page['listing']['listing']['item']):
                        path = page['listing']['listing']['item'][0]['path'].replace('header.json', 'sort_by_lexic_p1.json')
                        listPath(path)
                        return []
                    for item in page['listing']['listing']['item']:
                        if not 'asset_type' in item and 'path' in item:
                            url = common.build_url({'action': 'listPage', 'path': item['path']})
                            listitems.append({'type': 'listPage', 'label': item['title'], 'url': url})
                else:
                    listPath(page['listing']['listing']['item']['path'])

    if curr_page < page_count:
        url = common.build_url({'action': 'listPage', 'path': path.replace('_p' + str(curr_page), '_p' + str(curr_page + 1))})
        listitems.append({'type': 'path', 'label': 'Mehr...', 'url': url})

    return listitems


def buildLiveEventTag(event_info):
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


def getInfoLabel(asset_type, item_data):
    data = item_data
    if 'mediainfo' in data:
        data = data['mediainfo']
    elif extMediaInfos and extMediaInfos == 'true':
        asset = getAssetDetailsFromCache(data['id'])
        if asset:
            data = asset

    info = {}
    info['title'] = data.get('title', '')
    info['originaltitle'] = data.get('original_title', '')
    if not data.get('year_of_production', '') == '':
        info['year'] = data.get('year_of_production', '')
    info['plot'] = data.get('synopsis', '').replace('\n', '').strip()
    if info['plot'] == '':
        info['plot'] = data.get('description', '').replace('\n', '').strip()
    if data.get('on_air', {}).get('end_date', '') != '':
        string_end_date = data.get('on_air', {}).get('end_date', '')
        split_end_date = string_end_date.split('/')
        if len(split_end_date) == 3:
            info['plot'] = '%s bis %s.%s.%s\n\n%s' % ('Verfügbar'.decode('utf-8'), split_end_date[2], split_end_date[1], split_end_date[0], info.get('plot') if info.get('plot', None) is not None else '')
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
        info['title'] = buildLiveEventTag(data['technical_event']['on_air']) + ' ' + info['title']
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
                    info['title'] = '[COLOR blue]%s |[/COLOR] %s' % (item_data.get('event', '').get('title', ''), item_data['event'].get('subtitle', ''))
                info['duration'] = item_data.get('event', '').get('length', 0) * 60
            if data.get('type', '') == 'Film':
                asset_type = 'Film'
            elif data.get('type', '') == 'Episode':
                asset_type = 'Episode'
                info['plot'] = data.get('synopsis', '').replace('\n', '').strip()
                info['title'] = '[COLOR blue]%s |[/COLOR] %s' % (data.get('serie_title', ''), data.get('title', ''))
        if addon.getSetting('channel_name_first') == 'true':
            item_data['li_label'] = '[COLOR orange][%s][/COLOR] %s' % (item_data['channel']['name'], info['title'])
        else:
            item_data['li_label'] = '%s [COLOR orange][%s][/COLOR]' % (info['title'], item_data['channel']['name'])

        info['plot'] = item_data.get('event').get('startTime') + ' - ' + item_data.get('event').get('endTime') + "\n\n" + info['plot']
    if asset_type == 'searchresult':
        if extMediaInfos and extMediaInfos == 'false':
            info['plot'] = data.get('description', '')
            info['year'] = data.get('year', '')
            info['genre'] = data.get('category', '')
        if data.get('type', {}) == 'Film':
            asset_type = 'Film'
        elif data.get('type', '') == 'Episode':
            asset_type = 'Episode'
            info['plot'] = 'Folge: ' + data.get('title', '') + '\n\n' + data.get('synopsis', '').replace('\n', '').strip()
            info['title'] = data.get('title', '')
            item_data['li_label'] = '%1dx%02d. %s' % (data.get('season_nr', ''), data.get('episode_nr', ''), data.get('serie_title', ''))
    if asset_type == 'Film':
        info['mediatype'] = 'movie'
        if addon.getSetting('lookup_tmdb_data') == 'true' and not data.get('title', '') == '':
            title = data.get('title', '').encode("utf-8")
            xbmc.log('Searching Rating and better Poster for %s at tmdb.com' % title.upper())
            if not data.get('year_of_production', '') == '':
                TMDb_Data = getTMDBDataFromCache(title, info['year'])
            else:
                TMDb_Data = getTMDBDataFromCache(title)

            if len(TMDb_Data) > 0:
                if TMDb_Data.get('rating', None):
                    info['rating'] = str(TMDb_Data['rating'])
                    info['plot'] = 'User-Rating: ' + info['rating'] + ' / 10 (from TMDb) \n\n' + info['plot']
                    xbmc.log("Result of get Rating: %s" % (TMDb_Data['rating']))
                if TMDb_Data.get('poster_path', None):
                    item_data['TMDb_poster_path'] = TMDb_Data['poster_path']
                    xbmc.log("Path to TMDb Picture: %s" % (TMDb_Data['poster_path']))
    if asset_type == 'Series':
        info['year'] = data.get('year_of_production_start', '')
    if asset_type == 'Episode':
        info['mediatype'] = 'episode'
        info['episode'] = data.get('episode_nr', '')
        info['season'] = data.get('season_nr', '')
        info['tvshowtitle'] = data.get('serie_title', '')
        if info['title'] == '':
            info['title'] = data.get('episode_nr', 0)
            item_data['li_label'] = '%s - S%02dE%02d' % (data.get('serie_title', ''), data.get('season_nr', 0), data.get('episode_nr', 0))

    return info, item_data


def getWatchlistContextItem(item, delete=False):
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

    url = common.build_url({'action': action, 'id': ','.join(ids), 'assetType': asset_type})
    return [(label, 'RunPlugin(' + url + ')')]


def listAssets(asset_list, isWatchlist=False):
    for item in asset_list:
        isPlayable = False
        additional_params = {}
        li = xbmcgui.ListItem(label=item['label'], iconImage=icon_file)
        if item['type'] in ['Film', 'Episode', 'Sport', 'Clip', 'Series', 'live', 'searchresult', 'Season']:
            isPlayable = True
            # Check Altersfreigabe / Jugendschutzeinstellungen
            parental_rating = 0
            if 'parental_rating' in item['data']:
                parental_rating = item['data']['parental_rating']['value']
                if js_showall == 'false':
                    if not skygo.parentalCheck(parental_rating, play=False):
                        continue
            info, item['data'] = getInfoLabel(item['type'], item['data'])
            li.setInfo('video', info)
            additional_params.update({'infolabels': info, 'parental_rating': parental_rating})
            li.setLabel(item.get('data').get('li_label') if item.get('data').get('li_label', None) else info['title'])
            # if item['type'] not in ['Series', 'Season']:
            #    li = addStreamInfo(li, item['data'])

        if item['type'] in ['Film']:
            xbmcplugin.setContent(skygo.addon_handle, 'movies')
        elif item['type'] in ['Series', 'Season']:
            xbmcplugin.setContent(skygo.addon_handle, 'tvshows')
            isPlayable = False
        elif item['type'] in ['Episode']:
            xbmcplugin.setContent(skygo.addon_handle, 'episodes')
        elif item['type'] in ['Sport', 'Clip']:
            xbmcplugin.setContent(skygo.addon_handle, 'files')
        elif item['type'] == 'searchresult':
            xbmcplugin.setContent(skygo.addon_handle, 'movies')
        elif item['type'] == 'live':
            xbmcplugin.setContent(skygo.addon_handle, 'files')
            if 'TMDb_poster_path' in item['data'] or ('mediainfo' in item['data'] and not item['data']['channel']['name'].startswith('Sky Sport')):
                xbmcplugin.setContent(skygo.addon_handle, 'movies')

        # add contextmenu item for watchlist to playable content - not for live and clip content
        if isPlayable and not item['type'] in ['live', 'Clip']:
            li.addContextMenuItems(getWatchlistContextItem(item, isWatchlist), replaceItems=False)
        elif item['type'] == 'Season':
            li.addContextMenuItems(getWatchlistContextItem({'type': 'Episode', 'data': item['data']}, False), replaceItems=False)

        li.setProperty('IsPlayable', str(isPlayable).lower())

        art = getArt(item)
        if len(art) > 0:
            additional_params.update({'art': art})
            li.setArt(art)

        parsed_url = urlparse.urlparse(item['url'])
        params = dict(urlparse.parse_qsl(parsed_url.query))
        params.update(additional_params)
        url = common.build_url(params)

        xbmcplugin.addDirectoryItem(handle=skygo.addon_handle, url=url, listitem=li, isFolder=(not isPlayable))


def listPath(path):
    page = {}
    path = path.replace('ipad', 'web')
    r = skygo.session.get(skygo.baseUrl + path)
    if common.get_dict_value(r.headers, 'content-type').startswith('application/json'):
        page = r.json()
    else:
        xbmcplugin.endOfDirectory(skygo.addon_handle, cacheToDisc=True)
        return False
    if 'sort_by_lexic_p' in path:
        url = common.build_url({'action': 'listPage', 'path': path[0:path.index('sort_by_lexic_p')] + 'header.json'})
        addDir('[A-Z]', url)

    listitems = parseListing(page, path)
    listAssets(listitems)

    xbmcplugin.endOfDirectory(skygo.addon_handle, cacheToDisc=True)


def getPageItems(nodes, page_id):
    listitems = []
    for section in nodes.iter('section'):
        if section.attrib['id'] == page_id:
            for item in section:
                if int(item.attrib['id']) in nav_blacklist:
                    continue
                listitems.append(item)

    return listitems


def getParentNode(nodes, page_id):
    for item in nodes.iter('section'):
        if item.attrib['id'] == page_id:
            return item
    return None


def listPage(page_id):
    nav = getNav()
    items = getPageItems(nav, page_id)
    if len(items) == 1:
        if 'path' in items[0].attrib:
            listPath(items[0].attrib['path'])
            return
    for item in items:
        url = ''
        if item.tag == 'item':
            url = common.build_url({'action': 'listPage', 'path': item.attrib['path']})
        elif item.tag == 'section':
            url = common.build_url({'action': 'listPage', 'id': item.attrib['id']})

        addDir(item.attrib['label'], url)

    xbmcplugin.endOfDirectory(skygo.addon_handle, cacheToDisc=True)


def getAssetDetailsFromCache(asset_id):
    return assetDetailsCache.cacheFunction(skygo.getAssetDetails, asset_id)


def getTMDBDataFromCache(title, year=None, attempt=1, content='movie'):
    return TMDBCache.cacheFunction(getTMDBData, title, year, attempt, content)


def getTMDBData(title, year=None, attempt=1, content='movie'):
    # This product uses the TMDb API but is not endorsed or certified by TMDb.
    rating = None
    poster_path = None
    tmdb_id = None
    splitter = [' - ', ': ', ', ']
    tmdb_api = base64.b64decode('YTAwYzUzOTU0M2JlMGIwODE4YmMxOTRhN2JkOTVlYTU=')  # ApiKey Linkinsoldier
    Language = 'de'
    str_year = '&year=' + str(year) if year else ''
    title = re.sub('(\(.*\))', '', title).strip()
    movie = urllib.quote_plus(title)

    if attempt > 3:
        return {}

    try:
        # Define the moviedb Link zu download the json
        host = 'https://api.themoviedb.org/3/search/%s?api_key=%s&language=%s&query=%s%s' % (content, tmdb_api, Language, movie, str_year)
        # Download and load the corresponding json
        data = json.load(urllib2.urlopen(host))

        if data['total_results'] > 0:
            result = data['results'][0]
            if result['vote_average']:
                rating = float(result['vote_average'])
            if result['poster_path']:
                poster_path = 'https://image.tmdb.org/t/p/w500' + str(result['poster_path'])
            tmdb_id = result['id']
        elif year is not None:
            attempt += 1
            xbmc.log('Try again - without release year - to find Title: %s' % title)
            return getTMDBData(title, None, attempt)
        elif title.find('-') > -1:
            attempt += 1
            title = title.split('-')[0].strip()
            xbmc.log('Try again - find Title: %s' % title)
            return getTMDBData(title, None, attempt)
        else:
            xbmc.log('No movie found with Title: %s' % title)

    except (urllib2.URLError), e:
        xbmc.log('Error reason: %s' % e)

        if '429' or 'timed out' in e:
            attempt += 1
            xbmc.log('Attempt #%s - Too many requests - Pause 5 sec' % attempt)
            xbmc.sleep(5000)
            if attempt < 4:
                return getTMDBData(title, year, attempt)

        return {'tmdb_id': tmdb_id, 'title': title, 'rating': rating , 'poster_path': poster_path}
    return {'tmdb_id': tmdb_id, 'title': title, 'rating': rating , 'poster_path': poster_path}


def addStreamInfo(listitem, data):
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


def clearCache():
    try:
        assetDetailsCache.delete("%")
        TMDBCache.delete("%")
        xbmcgui.Dialog().notification('Sky Go: Cache', 'Leeren des Caches erfolgreich', xbmcgui.NOTIFICATION_INFO, 2000, True)
    except:
        xbmcgui.Dialog().notification('Sky Go: Cache', 'Leeren des Caches fehlgeschlagen', xbmcgui.NOTIFICATION_ERROR, 2000, True)


def getArt(item):
    art = {}

    if item['type'] in ['Film', 'Episode', 'Sport', 'Clip', 'Series', 'live', 'searchresult', 'Season']:
        art.update({'poster': getPoster(item['data']), 'fanart': getHeroImage(item['data'])})
    if item['type'] in ['Film']:
        if addon.getSetting('lookup_tmdb_data') == 'true' and 'TMDb_poster_path' in item['data']:
            poster_path = item['data']['TMDb_poster_path']
        else:
            poster_path = getPoster(item['data'])
        art.update({'poster': poster_path})
    elif item['type'] in ['Sport', 'Clip']:
        thumb = getHeroImage(item['data'])
        art.update({'thumb': thumb})
        if item.get('data').get('current_type', '') == 'Live':
            art.update({'poster': thumb})
    elif item['type'] == 'searchresult':
        if addon.getSetting('lookup_tmdb_data') == 'true' and 'TMDb_poster_path' in item['data']:
            poster_path = item['data']['TMDb_poster_path']
        else:
            poster_path = getPoster(item['data'])
        art.update({'poster': poster_path})
    elif item['type'] == 'live':
        poster = skygo.baseUrl + item['data']['event']['image'] if item['data']['channel']['name'].find('News') == -1 else getChannelLogo(item['data']['channel'])
        fanart = skygo.baseUrl + item['data']['event']['image'] if item['data']['channel']['name'].find('News') == -1 else skygo.baseUrl + '/bin/Picture/817/C_1_Picture_7179_content_4.jpg'
        thumb = poster

        if 'TMDb_poster_path' in item['data'] or ('mediainfo' in item['data'] and not item['data']['channel']['name'].startswith('Sky Sport')):
            if 'TMDb_poster_path' in item['data']:
                poster = item['data']['TMDb_poster_path']
            else:
                poster = getPoster(item['data']['mediainfo'])
            thumb = poster
            xbmcplugin.setContent(skygo.addon_handle, 'movies')

        art.update({'poster':  poster + '|User-Agent=' + skygo.user_agent, 'fanart': fanart + '|User-Agent=' + skygo.user_agent, 'thumb': thumb + '|User-Agent=' + skygo.user_agent})

    return art
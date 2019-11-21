#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import resources.lib.common as common
import navigation as nav

skygo = None

base_url = 'https://www.skygo.sky.de/SILK/services/public/watchlist/'


def rootDir():
    url = common.build_url({'action': 'watchlist', 'list': 'Film'})
    nav.addDir('Filme', url)

    url = common.build_url({'action': 'watchlist', 'list': 'Episode'})
    nav.addDir('Episoden', url)

    url = common.build_url({'action': 'watchlist', 'list': 'Sport'})
    nav.addDir('Sport', url)

    xbmcplugin.endOfDirectory(skygo.addon_handle, cacheToDisc=False)


def listWatchlist(asset_type, page=0):
    skygo.login()
    url = base_url + 'get?type=' + asset_type + '&page=' + str(page) + '&pageSize=8'
    r = skygo.session.get(url)
    data = json.loads(r.text[3:len(r.text) - 1])

    listitems = []
    if data.get('watchlist'):
        for item in data.get('watchlist'):
            if item.get('assetId'):
                try:
                    asset = skygo.getAssetDetails(item.get('assetId'))
                    for asset_details in nav.getAssets([asset]):
                        listitems.append(asset_details)
                except:
                    xbmc.log('[Sky Go] watchlist details could not be found for item {0}'.format(item))

        if data['hasNext']:
            url = common.build_url({'action': 'watchlist', 'list': asset_type, 'page': page + 1})
            listitems.append({'type': 'path', 'label': 'Mehr...', 'url': url})

    nav.listAssets(listitems, isWatchlist=True)

    xbmcplugin.endOfDirectory(skygo.addon_handle, cacheToDisc=True)


def addToWatchlist(asset_id, asset_type):
    skygo.login()
    url = base_url + 'add?assetId=' + asset_id + '&type=' + asset_type + '&version=12354&platform=web&product=SG&catalog=sg'
    r = skygo.session.get(url)
    res = json.loads(r.text[3:len(r.text) - 1])
    if res['resultMessage'] == 'OK':
        xbmcgui.Dialog().notification('Sky Go: Merkliste', asset_type + ' zur Merkliste hinzugefügt', xbmcgui.NOTIFICATION_INFO, 2000, True)
    else:
        xbmcgui.Dialog().notification('Sky Go: Merkliste', asset_type + ' konnte nicht zur Merkliste hinzugefügt werden', xbmcgui.NOTIFICATION_ERROR, 2000, True)


def deleteFromWatchlist(asset_id):
    url = base_url + 'delete?assetId=' + asset_id + '&version=12354&platform=web&product=SG&catalog=sg'
    r = skygo.session.get(url)
    res = json.loads(r.text[3:len(r.text) - 1])
    if res['resultMessage'] == 'OK':
        xbmc.executebuiltin('Container.Refresh')
    else:
        xbmcgui.Dialog().notification('Sky Go: Merkliste', 'Eintrag konnte nicht von der Merkliste entfernt werden', xbmcgui.NOTIFICATION_ERROR, 2000, True)
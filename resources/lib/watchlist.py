#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import json
import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin


class Watchlist:

    base_url = 'https://www.skygo.sky.de/SILK/services/public/watchlist/'


    def __init__(self, common, nav, skygo):

        self.common = common
        self.nav = nav
        self.skygo = skygo


    def rootDir(self):
        url = self.common.build_url({'action': 'watchlist', 'list': 'Film'})
        self.nav.addDir('Filme', url)

        url = self.common.build_url({'action': 'watchlist', 'list': 'Episode'})
        self.nav.addDir('Episoden', url)

        url = self.common.build_url({'action': 'watchlist', 'list': 'Sport'})
        self.nav.addDir('Sport', url)

        xbmcplugin.endOfDirectory(self.common.addon_handle, cacheToDisc=False)


    def listWatchlist(self, asset_type, page=0):
        self.skygo.login()
        url = '{0}get?type={1}&page={2}&pageSize=8'.format(self.base_url, asset_type, page)
        r = self.skygo.session.get(url)
        data = json.loads(r.text[3:len(r.text) - 1])

        listitems = []
        if data.get('watchlist'):
            for item in data.get('watchlist'):
                if item.get('assetId'):
                    asset = self.nav.getAssetDetailsFromCache(item.get('assetId'))
                    if len(asset) > 0:
                        for asset_details in self.nav.getAssets([asset]):
                            listitems.append(asset_details)
                    else:
                        xbmc.log('[Sky Go] watchlist details could not be found for item {0}'.format(item))

            if data['hasNext']:
                url = self.common.build_url({'action': 'watchlist', 'list': asset_type, 'page': page + 1})
                listitems.append({'type': 'path', 'label': 'Mehr...', 'url': url})

        self.nav.listAssets(listitems, isWatchlist=True)

        xbmcplugin.endOfDirectory(self.common.addon_handle, cacheToDisc=True)


    def addToWatchlist(self, asset_id, asset_type):
        self.skygo.login()
        url = '{0}add?assetId={1}&type={2}&version=12354&platform=web&product=SG&catalog=sg'.format(self.base_url, asset_id, asset_type)
        r = self.skygo.session.get(url)
        res = json.loads(r.text[3:len(r.text) - 1])
        if res['resultMessage'] == 'OK':
            xbmcgui.Dialog().notification('Sky Go: Merkliste', '{0} zur Merkliste hinzugefügt'.format(asset_type), xbmcgui.NOTIFICATION_INFO, 2000, True)
        else:
            xbmcgui.Dialog().notification('Sky Go: Merkliste', '{0} konnte nicht zur Merkliste hinzugefügt werden'.format(asset_type), xbmcgui.NOTIFICATION_ERROR, 2000, True)


    def deleteFromWatchlist(self, asset_id):
        url = '{0}delete?assetId={1}&version=12354&platform=web&product=SG&catalog=sg'.format(self.base_url, asset_id)
        r = self.skygo.session.get(url)
        res = json.loads(r.text[3:len(r.text) - 1])
        if res['resultMessage'] == 'OK':
            xbmc.executebuiltin('Container.Refresh')
        else:
            xbmcgui.Dialog().notification('Sky Go: Merkliste', 'Eintrag konnte nicht von der Merkliste entfernt werden', xbmcgui.NOTIFICATION_ERROR, 2000, True)
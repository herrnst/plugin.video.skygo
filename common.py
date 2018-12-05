#!/usr/bin/env python
# -*- coding: utf-8 -*-

import urllib
import xbmcaddon, xbmc

base_url = "plugin://" + xbmcaddon.Addon().getAddonInfo('id')


def build_url(query):
    query.update({'ZZ': ''})
    return '%s?%s' % (base_url, urllib.urlencode(query))
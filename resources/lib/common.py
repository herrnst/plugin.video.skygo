#!/usr/bin/env python
# -*- coding: utf-8 -*-

import urllib
import xbmcaddon

base_url = "plugin://" + xbmcaddon.Addon().getAddonInfo('id')


def build_url(query):
    query.update({'ZZ': ''})
    return base_url + '?' + urllib.urlencode(query)
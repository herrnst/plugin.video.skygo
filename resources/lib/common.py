#!/usr/bin/env python
# -*- coding: utf-8 -*-

import urllib
import xbmcaddon
from collections import OrderedDict

base_url = "plugin://" + xbmcaddon.Addon().getAddonInfo('id')


def build_url(query):
    query.update({'zz': ''})
    query = OrderedDict(query.items())
    return base_url + '?' + urllib.urlencode(query)